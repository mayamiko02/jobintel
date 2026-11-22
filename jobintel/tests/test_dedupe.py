import unittest

from _helpers import vac
from dedupe_vacancies import (
    audit_and_dedupe,
    compute_dedupe_key,
    is_duplicate,
    normalize_company,
    normalize_location,
    normalize_ref,
    normalize_title,
)

TODAY = "2026-11-21"


class TestNormalisation(unittest.TestCase):
    def test_company_suffix_and_punctuation_variants(self):
        variants = ["Acme Ltd", "ACME Limited", "Acme Zambia Limited", "Acme, Ltd.", "The Acme Group", "Acme (Zambia) PLC"]
        self.assertEqual({normalize_company(v) for v in variants}, {"acme"})

    def test_ampersand_and_and(self):
        self.assertEqual(normalize_company("Smith & Sons Ltd"), normalize_company("Smith and Sons Limited"))
        self.assertEqual(normalize_title("Sales & Marketing Officer"), normalize_title("Sales and Marketing Officer"))

    def test_title_location_hint_removed(self):
        self.assertEqual(normalize_title("Sales Officer - Lusaka"), normalize_title("Sales Officer"))
        self.assertEqual(normalize_title("Sales Officer (Ndola)"), normalize_title("Sales Officer"))
        self.assertEqual(normalize_title("Sales   Officer!!"), "sales officer")

    def test_location_variants(self):
        self.assertEqual(normalize_location("Lusaka, Lusaka Province"), normalize_location("lusaka"))
        self.assertEqual(normalize_location("Lusaka City"), "lusaka")
        self.assertEqual(normalize_location(None), "")

    def test_reference_variants(self):
        self.assertEqual(normalize_ref("ZTA 06"), normalize_ref("zta-06"))
        self.assertEqual(normalize_ref("HR/VA/2026/14"), normalize_ref("hrva 2026 14"))
        self.assertEqual(normalize_ref(None), "")

    def test_empty_inputs_do_not_crash(self):
        self.assertEqual(normalize_company(None), "")
        self.assertEqual(normalize_title(""), "")
        self.assertIsInstance(compute_dedupe_key("", "", "", None), str)


class TestReferencePriority(unittest.TestCase):
    def test_same_reference_same_employer_is_duplicate_even_if_title_differs(self):
        a = vac(ref="ZTA 06", title="Marketing Officer")
        b = vac(ref="zta-06", title="Marketing Officer (Re-advertised)")
        self.assertTrue(is_duplicate(a, b))

    def test_different_references_are_distinct_even_with_identical_title_and_place(self):
        a = vac(ref="REF-001")
        b = vac(ref="REF-002")
        self.assertFalse(is_duplicate(a, b))

    def test_same_reference_different_employer_is_not_duplicate(self):
        a = vac(company="Acme Ltd", ref="HR-01")
        b = vac(company="Beta Ltd", ref="HR-01")
        self.assertFalse(is_duplicate(a, b))

    def test_reference_on_one_side_only_falls_back_to_employer_title_location(self):
        a = vac(ref="REF-001")
        b = vac(ref=None)
        self.assertTrue(is_duplicate(a, b))
        c = vac(ref=None, title="Graphic Designer")
        self.assertFalse(is_duplicate(a, c))


class TestFallbackWhenReferencesMissing(unittest.TestCase):
    def test_different_source_urls_do_not_matter(self):
        a = vac(source_url="https://board-a.example/job/1", source="board-a")
        b = vac(source_url="https://board-b.example/vacancy?id=999", source="board-b")
        self.assertTrue(is_duplicate(a, b))

    def test_punctuation_and_suffix_variations(self):
        a = vac(company="Acme Ltd.", title="Sales & Marketing Officer - Lusaka")
        b = vac(company="ACME Zambia Limited", title="Sales and Marketing Officer")
        self.assertTrue(is_duplicate(a, b))

    def test_different_location_is_distinct(self):
        self.assertFalse(is_duplicate(vac(city="Lusaka"), vac(city="Ndola")))

    def test_empty_location_is_unknown_not_a_mismatch(self):
        self.assertTrue(is_duplicate(vac(city=""), vac(city="Lusaka")))

    def test_different_title_is_distinct(self):
        self.assertFalse(is_duplicate(vac(title="Marketing Officer"), vac(title="Marketing Manager")))

    def test_missing_company_never_matches(self):
        self.assertFalse(is_duplicate(vac(company=""), vac(company="")))

    def test_location_given_as_plain_string(self):
        a = vac()
        a["location"] = "Lusaka"
        self.assertTrue(is_duplicate(a, vac()))


class TestAuditPipeline(unittest.TestCase):
    def test_duplicates_collapse_and_best_source_kept(self):
        weak = vac(source="aggregator", verification_status="partially_verified_snippet", application_link_or_email="https://agg.example/x")
        strong = vac(source="employer", application_link_or_email="hr@acme.example")
        res = audit_and_dedupe([weak, strong], TODAY)
        self.assertEqual(res["active_count"], 1)
        self.assertEqual(res["active_vacancies"][0]["source"], "employer")
        self.assertEqual(res["excluded_count"], 1)

    def test_distinct_references_both_kept(self):
        res = audit_and_dedupe([vac(ref="A-1"), vac(ref="A-2")], TODAY)
        self.assertEqual(res["active_count"], 2)

    def test_input_order_does_not_change_outcome(self):
        a = vac(source="x", verification_status="partially_verified_snippet", application_link_or_email="https://x.example")
        b = vac(source="y")
        r1 = audit_and_dedupe([a, b], TODAY)
        r2 = audit_and_dedupe([b, a], TODAY)
        self.assertEqual(r1["active_vacancies"][0]["source"], r2["active_vacancies"][0]["source"])

    def test_dedupe_key_uses_reference_when_present(self):
        k1 = compute_dedupe_key("Acme Ltd", "Marketing Officer", "Lusaka", "R-1")
        k2 = compute_dedupe_key("Acme Limited", "Different Title", "Ndola", "r 1")
        self.assertEqual(k1, k2)
        k3 = compute_dedupe_key("Acme Ltd", "Marketing Officer", "Lusaka", None)
        self.assertNotEqual(k1, k3)


if __name__ == "__main__":
    unittest.main()
