#!/usr/bin/env python3
"""Automated verification tests for JOBINTEL schemas, Gate checks, multi-profession query generation, deduplication, tracker build, and PDF audit."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_contract import validate_artifact  # noqa: E402
from generate_search_queries import build_search_strategy  # noqa: E402
from dedupe_vacancies import audit_and_dedupe, compute_dedupe_key  # noqa: E402


class TestJobIntel(unittest.TestCase):
    def test_all_markets_valid(self):
        markets_dir = ROOT / "markets"
        files = list(markets_dir.glob("*.json"))
        self.assertGreaterEqual(len(files), 6)
        for mf in files:
            data = json.loads(mf.read_text(encoding="utf-8"))
            errs = validate_artifact("market", data)
            self.assertEqual(errs, [], f"{mf.name} failed validation: {errs}")

    def test_gate1_blocks_unconfirmed_or_unresolved_profile(self):
        profile = json.loads((ROOT / "examples" / "nurse_lusaka_profile.json").read_text(encoding="utf-8"))
        # Confirmed fixture should pass Gate 1
        self.assertEqual(validate_artifact("profile", profile, require_confirmed_gate1=True), [])

        # Draft profile must fail Gate 1
        draft = json.loads(json.dumps(profile))
        draft["profile_status"] = "draft"
        errs = validate_artifact("profile", draft, require_confirmed_gate1=True)
        self.assertTrue(any("Gate 1 blocked" in e for e in errs))

        # Unresolved ambiguity must fail Gate 1
        ambig = json.loads(json.dumps(profile))
        ambig["ambiguities_to_confirm"][0]["resolved"] = False
        errs2 = validate_artifact("profile", ambig, require_confirmed_gate1=True)
        self.assertTrue(any("unresolved ambiguity" in e for e in errs2))

    def test_multi_profession_strategy_diversity(self):
        """Confirm JOBINTEL is CV-driven and produces radically different strategies for Nurse, Civil Engineer, and Software Dev."""
        zm = json.loads((ROOT / "markets" / "zambia.json").read_text(encoding="utf-8"))
        ke = json.loads((ROOT / "markets" / "kenya.json").read_text(encoding="utf-8"))

        nurse = json.loads((ROOT / "examples" / "nurse_lusaka_profile.json").read_text(encoding="utf-8"))
        civil = json.loads((ROOT / "examples" / "civil_engineer_copperbelt_profile.json").read_text(encoding="utf-8"))
        swe = json.loads((ROOT / "examples" / "software_dev_nairobi_profile.json").read_text(encoding="utf-8"))

        s_nurse = build_search_strategy(nurse, zm)
        s_civil = build_search_strategy(civil, zm)
        s_swe = build_search_strategy(swe, ke)

        for strat in (s_nurse, s_civil, s_swe):
            self.assertEqual(validate_artifact("strategy", strat), [])

        nurse_blob = json.dumps(s_nurse)
        civil_blob = json.dumps(s_civil)
        swe_blob = json.dumps(s_swe)

        self.assertIn("NMCZ", nurse_blob)
        self.assertIn("Lusaka", nurse_blob)
        self.assertNotIn("AutoCAD", nurse_blob)

        self.assertIn("EIZ", civil_blob)
        self.assertIn("AutoCAD", civil_blob)
        self.assertNotIn("NMCZ", civil_blob)

        self.assertIn("Python", swe_blob)
        self.assertIn("Nairobi", swe_blob)
        self.assertIn("Remote", swe_blob)  # Triggered only because swe opted into remote_local_hours

    def test_dedupe_and_expiry_audit(self):
        zm = json.loads((ROOT / "markets" / "zambia.json").read_text(encoding="utf-8"))
        sample = json.loads((ROOT / "examples" / "sample_verified_vacancy.json").read_text(encoding="utf-8"))["vacancy"]

        dup_aggregator = json.loads(json.dumps(sample))
        dup_aggregator["company"] = "Zambia Community Health Initiative Limited"
        dup_aggregator["source_url"] = "https://aggregator.example/dup-job"
        dup_aggregator["verification_status"] = "partially_verified_snippet"
        dup_aggregator["application_link_or_email"] = "https://aggregator.example/apply"

        expired = json.loads(json.dumps(sample))
        expired["vacancy_id"] = "vac-expired-1"
        expired["job_title"] = "Expired Project Officer"
        expired["deadline_iso"] = "2026-10-01"

        res = audit_and_dedupe([dup_aggregator, sample, expired], today_iso="2026-11-21", market=zm)
        self.assertEqual(res["active_count"], 1)
        self.assertEqual(res["excluded_count"], 2)
        # Kept the verified_full_ad version over the aggregator snippet
        self.assertEqual(res["active_vacancies"][0]["verification_status"], "verified_full_ad")
        self.assertEqual(
            compute_dedupe_key("Acme Corp Ltd", "Sales Officer - Lusaka", "Lusaka"),
            compute_dedupe_key("Acme Corp Limited", "Sales Officer", "lusaka"),
        )

    def test_sample_vacancy_and_match_evidence_rules(self):
        bundle = json.loads((ROOT / "examples" / "sample_verified_vacancy.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_artifact("vacancy", bundle["vacancy"]), [])
        self.assertEqual(validate_artifact("match", bundle["match_evaluation"]), [])

        # Hard blocker + Strong Fit must be flagged as inconsistent
        bad_match = json.loads(json.dumps(bundle["match_evaluation"]))
        bad_match["fit_tier"] = "Strong Fit"
        bad_match["missing_qualifications_and_blockers"] = [
            {"gap": "Active license missing", "severity": "hard_blocker", "mitigation_or_action": "Skip"}
        ]
        errs = validate_artifact("match", bad_match)
        self.assertTrue(any("hard_blocker" in e for e in errs))

    def test_tracker_xlsx_and_pdf_pack_if_libs_installed(self):
        import importlib.util
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            if importlib.util.find_spec("openpyxl"):
                from build_tracker import build_xlsx
                payload = {
                    "tracker_title": "JOBINTEL Demo Tracker",
                    "vacancies": [
                        {
                            "company": "Zambia Community Health Initiative",
                            "job_title": "Community Health & M&E Officer",
                            "category": "Public Health & NGO",
                            "fit_tier": "Possible Fit",
                            "match_summary": "Meets NMCZ + 4 yrs ANC/DHIS2; KoboToolbox missing.",
                            "location": "Lusaka",
                            "employment_type": "Fixed-Term",
                            "experience_level": "Mid-level",
                            "application_link_or_email": "careers@example.test",
                            "deadline": "2026-12-05",
                            "date_posted": "2026-11-18",
                            "source": "Direct Portal",
                            "status": "Not Applied",
                            "notes": "Combine PDF + NMCZ + NRC",
                        }
                    ],
                    "excluded_log": [
                        {"company": "Old Co", "job_title": "Clerk", "reason": "Expired", "source_url": "https://old.test"}
                    ],
                }
                xlsx_out = build_xlsx(payload, tmp / "tracker.xlsx")
                self.assertTrue(xlsx_out.exists() and xlsx_out.stat().st_size > 2000)

            from render_pdf_pack import render_html_from_spec, render_pack
            spec = {
                "output_slug": "Thandiwe_Banda_Health_Officer",
                "candidate": {
                    "full_name": "THANDIWE BANDA",
                    "location": "Lusaka, Zambia",
                    "phone": "+260 970 000 111",
                    "email": "thandiwe.banda.example@invalid.test",
                },
                "cv": {
                    "headline": "Registered Nurse & Community Health Coordinator",
                    "summary": "Registered Nurse with 4 years of clinical ANC/ART care and DHIS2 health indicator reporting across Lusaka clinics.",
                    "skills": ["Outpatient Triage", "HIV/ART Adherence", "Maternal & Child Health", "DHIS2 & SmartCare Reporting", "Cold-Chain Audits"],
                    "education": [
                        {"title": "Diploma in Registered Nursing", "institution": "Lusaka School of Nursing (Fictional)", "year": "2021"},
                        {"title": "Active NMCZ Registration", "institution": "NMCZ-DEMO-2026", "year": "2026"},
                    ],
                    "languages": ["English (Fluent)", "Bemba (Fluent)", "Nyanja (Conversational)"],
                    "experience": [
                        {
                            "role_title": "Registered Nurse",
                            "employer": "Chilenje Urban Health Centre (Fictional)",
                            "period": "2023 – Present",
                            "location": "Lusaka",
                            "bullets": [
                                "Managed antenatal care, outpatient triage, and HIV/ART adherence counselling.",
                                "Compiled weekly clinic immunization tallies and monthly DHIS2 reports with zero cold-chain stockout alerts.",
                            ],
                        },
                        {
                            "role_title": "Clinical Nursing Assistant",
                            "employer": "Kafue Mission Hospital (Fictional)",
                            "period": "2022 – 2023",
                            "location": "Kafue",
                            "bullets": [
                                "Supported maternal ward admissions, vitals monitoring, and medical consumables stock logs."
                            ],
                        },
                    ],
                },
                "cover_letter": {
                    "date_line": "21 November 2026",
                    "recipient": "The Hiring Manager\nZambia Community Health Initiative (Fictional)",
                    "subject_line": "RE: Application - Community Health & M&E Officer (Ref: ZHA-LSK-2026-14)",
                    "opening_paragraph": "I am writing to apply for the Community Health & M&E Officer position in Lusaka.",
                    "alignment_paragraph": "With an active NMCZ nursing registration and four years of clinical ANC/ART and DHIS2 reporting experience, I bring practical frontline public-health execution.",
                    "highlights": [
                        "Clinical & Outreach Delivery: Managed ANC, triage, and ART counselling in Lusaka.",
                        "Health Data Quality: Submitted monthly DHIS2 indicators and maintained clean vaccine cold-chain audits."
                    ],
                    "closing_paragraph": "While my background has centered on DHIS2 and Excel rather than KoboToolbox, my data accuracy foundations transfer directly.",
                    "disclosure_note": "Verified Diploma in Registered Nursing & active NMCZ registration attached alongside NRC copy."
                },
                "audit_forbidden_tokens": ["PowerBI", "PhD"],
            }
            cv_html, cl_html = render_html_from_spec(spec)
            self.assertIn("THANDIWE BANDA", cv_html)
            self.assertNotIn("{{", cv_html)
            self.assertNotIn("{{", cl_html)

            if importlib.util.find_spec("weasyprint") and importlib.util.find_spec("fitz"):
                report = render_pack(spec, tmp / "pdfs")
                self.assertTrue(report["passed"], f"PDF audit failed: {report}")


if __name__ == "__main__":
    unittest.main()
