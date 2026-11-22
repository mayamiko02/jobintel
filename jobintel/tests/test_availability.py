import unittest
from datetime import date

from _helpers import load, vac
from dedupe_vacancies import audit_and_dedupe, derive_availability
from validate_contract import validate_artifact

TODAY = date(2026, 11, 21)


class TestAvailabilityStates(unittest.TestCase):
    def test_verified_open_needs_full_ad_and_future_deadline(self):
        state, _ = derive_availability(vac(deadline_iso="2026-12-05"), TODAY)
        self.assertEqual(state, "verified_open")

    def test_deadline_today_is_still_open(self):
        state, _ = derive_availability(vac(deadline_iso="2026-11-21"), TODAY)
        self.assertEqual(state, "verified_open")

    def test_deadline_passed_is_expired(self):
        state, reason = derive_availability(vac(deadline_iso="2026-11-20"), TODAY)
        self.assertEqual(state, "expired")
        self.assertIn("2026-11-20", reason)

    def test_future_deadline_from_snippet_only_is_likely_open_not_verified(self):
        state, _ = derive_availability(vac(verification_status="partially_verified_snippet"), TODAY)
        self.assertEqual(state, "likely_open")

    def test_no_deadline_never_verified_open(self):
        v = vac(deadline_iso=None, date_posted="2026-11-15")
        state, _ = derive_availability(v, TODAY)
        self.assertEqual(state, "likely_open")

    def test_no_deadline_and_old_posting_is_uncertain(self):
        state, _ = derive_availability(vac(deadline_iso=None, date_posted="2026-08-01"), TODAY)
        self.assertEqual(state, "uncertain")

    def test_no_deadline_and_no_date_is_uncertain(self):
        state, _ = derive_availability(vac(deadline_iso=None), TODAY)
        self.assertEqual(state, "uncertain")

    def test_snippet_only_without_deadline_is_uncertain(self):
        state, _ = derive_availability(vac(deadline_iso=None, date_posted="2026-11-18", verification_status="partially_verified_snippet"), TODAY)
        self.assertEqual(state, "uncertain")

    def test_unsupported_verified_open_claim_is_downgraded(self):
        v = vac(deadline_iso=None, availability_status="verified_open", date_posted="2026-11-18")
        state, reason = derive_availability(v, TODAY)
        self.assertEqual(state, "likely_open")
        self.assertIn("downgraded", reason)
        v2 = vac(verification_status="partially_verified_snippet", availability_status="verified_open")
        self.assertEqual(derive_availability(v2, TODAY)[0], "uncertain")

    def test_explicit_removed_is_kept(self):
        state, _ = derive_availability(vac(availability_status="removed", deadline_iso=None), TODAY)
        self.assertEqual(state, "removed")

    def test_unparseable_deadline_is_uncertain(self):
        state, _ = derive_availability(vac(deadline_iso="next Friday"), TODAY)
        self.assertEqual(state, "uncertain")

    def test_is_currently_open_is_derived(self):
        res = audit_and_dedupe(
            [vac(), vac(company="B", deadline_iso="2026-10-01"), vac(company="C", deadline_iso=None)],
            "2026-11-21",
        )
        self.assertEqual(res["active_count"], 1)
        states = {e["company"]: e["availability_status"] for e in res["excluded_log"]}
        self.assertEqual(states, {"B": "expired", "C": "uncertain"})
        self.assertTrue(res["active_vacancies"][0]["is_currently_open"])


class TestVacancySchemaConsistency(unittest.TestCase):
    def setUp(self):
        self.v = load("examples/sample_verified_vacancy.json")["vacancy"]

    def test_sample_is_valid(self):
        self.assertEqual(validate_artifact("vacancy", self.v), [])

    def test_open_flag_must_match_state(self):
        self.v["availability_status"] = "expired"
        errs = validate_artifact("vacancy", self.v)
        self.assertTrue(any("inconsistency" in e for e in errs))

    def test_verified_open_requires_deadline(self):
        self.v["deadline_iso"] = None
        errs = validate_artifact("vacancy", self.v)
        self.assertTrue(any("deadline" in e for e in errs))

    def test_state_requires_evidence(self):
        del self.v["availability_evidence"]
        errs = validate_artifact("vacancy", self.v)
        self.assertTrue(any("availability_evidence" in e for e in errs))

    def test_unknown_state_rejected(self):
        self.v["availability_status"] = "maybe"
        self.assertTrue(validate_artifact("vacancy", self.v))


if __name__ == "__main__":
    unittest.main()
