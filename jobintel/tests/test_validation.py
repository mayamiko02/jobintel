import copy
import unittest

from _helpers import ROOT, load
from validate_contract import SCHEMA_MAP, validate_artifact

PROFILES = ["nurse_lusaka_profile.json", "civil_engineer_copperbelt_profile.json", "software_dev_nairobi_profile.json"]


class TestProfileValidation(unittest.TestCase):
    def test_all_example_profiles_valid_and_gate1_ready(self):
        for name in PROFILES:
            data = load(f"examples/{name}")
            self.assertEqual(validate_artifact("profile", data, require_confirmed_gate1=True), [], name)

    def test_missing_required_key_reported(self):
        data = load(f"examples/{PROFILES[0]}")
        key = next(iter(k for k in ("identity", "work_experience", "skills") if k in data))
        del data[key]
        errs = validate_artifact("profile", data)
        self.assertTrue(errs and any(key in e for e in errs))

    def test_wrong_type_reported(self):
        data = load(f"examples/{PROFILES[0]}")
        data["work_experience"] = "not a list"
        self.assertTrue(validate_artifact("profile", data))

    def test_draft_blocks_gate1(self):
        data = load(f"examples/{PROFILES[0]}")
        data["profile_status"] = "draft"
        errs = validate_artifact("profile", data, require_confirmed_gate1=True)
        self.assertTrue(any("Gate 1 blocked" in e for e in errs))

    def test_unresolved_ambiguity_blocks_gate1(self):
        data = load(f"examples/{PROFILES[0]}")
        data["ambiguities_to_confirm"] = [{"field": "relocation", "question": "?", "resolved": False}] + data.get("ambiguities_to_confirm", [])
        errs = validate_artifact("profile", data, require_confirmed_gate1=True)
        self.assertTrue(any("unresolved" in e for e in errs))


class TestOtherArtifacts(unittest.TestCase):
    def test_all_markets_valid(self):
        for f in (ROOT / "markets").glob("*.json"):
            import json
            self.assertEqual(validate_artifact("market", json.loads(f.read_text(encoding="utf-8"))), [], f.name)

    def test_zambia_market_has_provenance_on_every_portal(self):
        z = load("markets/zambia.json")
        self.assertEqual(z["provenance"]["status"], "partially_verified")
        for p in z["portals"]:
            self.assertIn(p.get("provenance"), {"observed", "reported", "provisional"}, p["name"])
            if p["provenance"] == "observed":
                self.assertTrue(p.get("observed_on"), p["name"])

    def test_non_zambia_markets_are_marked_provisional(self):
        for name in ("kenya", "south_africa", "nigeria", "ghana", "remote_africa"):
            self.assertEqual(load(f"markets/{name}.json")["provenance"]["status"], "provisional", name)

    def test_match_bucket_overlap_and_blocker_rules(self):
        m = load("examples/sample_verified_vacancy.json")["match_evaluation"]
        self.assertEqual(validate_artifact("match", m), [])
        bad = copy.deepcopy(m)
        bad["fit_tier"] = "Strong Fit"
        bad["missing_qualifications_and_blockers"] = [{"gap": "Licence", "severity": "hard_blocker", "mitigation_or_action": "x"}]
        self.assertTrue(any("hard_blocker" in e for e in validate_artifact("match", bad)))

    def test_every_schema_file_is_wired_and_loadable(self):
        import json
        for kind, fname in SCHEMA_MAP.items():
            schema = json.loads((ROOT / "schemas" / fname).read_text(encoding="utf-8"))
            self.assertEqual(schema.get("type"), "object", kind)


if __name__ == "__main__":
    unittest.main()
