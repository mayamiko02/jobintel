import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _helpers import ROOT, load, vac
from dedupe_vacancies import audit_and_dedupe, is_duplicate
from generate_search_queries import build_search_strategy
from validate_contract import validate_artifact

SCRIPTS = ROOT / "scripts"


def run(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True)


class TestMalformedInputsInProcess(unittest.TestCase):
    def test_non_object_inputs_are_reported_not_raised(self):
        for bad in (None, [], "text", 42, [1, 2]):
            for kind in ("profile", "market", "strategy", "vacancy", "match"):
                errs = validate_artifact(kind, bad)
                self.assertTrue(errs and "expected a JSON object" in errs[0], (kind, bad))

    def test_unknown_kind(self):
        self.assertTrue(any("unknown artifact kind" in e for e in validate_artifact("nope", {})))

    def test_empty_object_fails_every_kind(self):
        for kind in ("profile", "market", "strategy", "vacancy", "match"):
            self.assertTrue(validate_artifact(kind, {}), kind)

    def test_dedupe_rejects_non_list_and_non_object_records(self):
        with self.assertRaises(TypeError):
            audit_and_dedupe({"a": 1}, "2026-11-21")
        with self.assertRaises(TypeError):
            audit_and_dedupe(["x"], "2026-11-21")

    def test_dedupe_rejects_bad_date(self):
        with self.assertRaises(ValueError):
            audit_and_dedupe([], "21/11/2026")

    def test_dedupe_empty_list(self):
        res = audit_and_dedupe([], "2026-11-21")
        self.assertEqual((res["active_count"], res["excluded_count"]), (0, 0))

    def test_dedupe_tolerates_missing_fields(self):
        res = audit_and_dedupe([{}], "2026-11-21")
        self.assertEqual(res["active_count"], 0)  # no evidence => uncertain => excluded, not a crash
        self.assertFalse(is_duplicate({}, {}))

    def test_strategy_requires_confirmed_profile(self):
        profile = load("examples/nurse_lusaka_profile.json")
        profile["profile_status"] = "draft"
        with self.assertRaises(ValueError):
            build_search_strategy(profile, load("markets/zambia.json"))

    def test_strategy_with_minimal_confirmed_profile_does_not_crash(self):
        strat = build_search_strategy({"profile_status": "confirmed"}, load("markets/zambia.json"))
        self.assertIn("boolean_queries", strat)


class TestMalformedInputsCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def test_validate_missing_file(self):
        r = run("validate_contract.py", "profile", str(self.dir / "absent.json"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("cannot read", r.stderr)

    def test_validate_invalid_json(self):
        r = run("validate_contract.py", "profile", self.write("bad.json", "{not json"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("not valid JSON", r.stderr)

    def test_validate_wrong_top_level_type(self):
        r = run("validate_contract.py", "profile", self.write("arr.json", "[1,2,3]"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("expected a JSON object", r.stdout)

    def test_validate_unknown_kind_is_rejected_by_argparse(self):
        r = run("validate_contract.py", "banana", self.write("x.json", "{}"))
        self.assertNotEqual(r.returncode, 0)

    def test_dedupe_cli_bad_json_and_bad_date(self):
        r = run("dedupe_vacancies.py", self.write("bad.json", "[oops"))
        self.assertEqual(r.returncode, 2)
        r2 = run("dedupe_vacancies.py", self.write("ok.json", "[]"), "--today", "tomorrow")
        self.assertEqual(r2.returncode, 2)
        r3 = run("dedupe_vacancies.py", self.write("obj.json", '{"a":1}'))
        self.assertEqual(r3.returncode, 2)

    def test_dedupe_cli_happy_path(self):
        path = self.write("v.json", json.dumps([vac(), vac(source="other")]))
        r = run("dedupe_vacancies.py", path, "--today", "2026-11-21")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["active_count"], 1)

    def test_unicode_and_odd_text_survive(self):
        v = vac(company="Café Müller Ltd", title="Chargé d'affaires — Lusaka")
        res = audit_and_dedupe([v], "2026-11-21")
        self.assertEqual(res["active_count"], 1)


if __name__ == "__main__":
    unittest.main()


class TestOtherScriptsCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def w(self, name, text):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def test_generate_queries_bad_inputs_exit_2(self):
        market = str(ROOT / "markets" / "zambia.json")
        self.assertEqual(run("generate_search_queries.py", str(self.dir / "none.json"), market).returncode, 2)
        self.assertEqual(run("generate_search_queries.py", self.w("b.json", "{x"), market).returncode, 2)
        self.assertEqual(run("generate_search_queries.py", self.w("a.json", "[]"), market).returncode, 2)

    def test_generate_queries_rejects_unconfirmed_profile(self):
        draft = load("examples/nurse_lusaka_profile.json")
        draft["profile_status"] = "draft"
        r = run("generate_search_queries.py", self.w("d.json", json.dumps(draft)), str(ROOT / "markets" / "zambia.json"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("Gate 1", r.stderr)

    def test_extract_cv_text_unsupported_and_missing(self):
        self.assertEqual(run("extract_cv_text.py", self.w("cv.xyz", "hi")).returncode, 2)
        self.assertEqual(run("extract_cv_text.py", str(self.dir / "missing.txt")).returncode, 2)

    def test_extract_cv_text_plain_text(self):
        r = run("extract_cv_text.py", self.w("cv.txt", "Jane Example\njane@example.test\nhttps://example.test/portfolio\n" * 5))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertIn("jane@example.test", out["extracted_emails"])

    def test_build_tracker_bad_payload_exit_2(self):
        out = str(self.dir / "t.xlsx")
        self.assertEqual(run("build_tracker.py", "--input", self.w("b.json", "{x"), "--out", out).returncode, 2)
        self.assertEqual(run("build_tracker.py", "--input", self.w("l.json", "[]"), "--out", out).returncode, 2)

    def test_render_pdf_pack_bad_spec_exit_2(self):
        r = run("render_pdf_pack.py", "--spec", self.w("b.json", "{x"), "--out-dir", str(self.dir / "o"))
        self.assertEqual(r.returncode, 2)
