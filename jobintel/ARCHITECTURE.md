# JOBINTEL Platform Architecture

JOBINTEL is engineered as a **modular pipeline separated by explicit JSON data contracts** so the same intelligence logic powers both conversational AI agent workflows (`SKILL.md`) and a standalone web/API JOBINTEL platform.

---

## 1. Architectural Separation: Why CV Analysis ≠ Job Search

A common anti-pattern in AI career tools is coupling raw CV text parsing directly inside search prompts. That forces every search iteration to re-read unstructured CV text, prevents deterministic auditing, and locks the system to file uploads.

JOBINTEL enforces a hard contract boundary:

```text
  Inputs                                   Contract Boundary                          Downstream Pipeline
  ──────                                   ─────────────────                          ───────────────────
  • PDF / DOCX / Image CV ──► Engine 1 ──┐
  • Supporting Certificates ──► (CV/OCR) ├► CandidateProfile JSON ──► [GATE 1] ──► Engine 2 (Search Strategy)
  • Web Intake Form ─────────────────────┤   (schemas/candidate_               │       ├──► [GATE 2] Transparency
  • Partner / ATS Webhook ───────────────┘    profile.schema.json)             │       ├──► Engine 3 (Discovery & Verify)
                                                                               │       ├──► Engine 4 (Evidence Matching)
                                                                               └───────┴──► Engine 5 (Docs & Tracker)
```

Because **Engines 2–5 accept only `CandidateProfile`**, an eventual JOBINTEL SaaS/API platform can:
- Run Engine 1 asynchronously when a user uploads a CV and save the editable `CandidateProfile` to Postgres/JSONB.
- Let candidates fill or update their profile directly via structured web forms.
- (Future, not implemented here) Re-run vacancy discovery (Engine 3) and evidence matching (Engine 4) on a schedule against confirmed profiles without re-parsing CVs. This repository contains no scheduler.

---

## 2. Data Contracts (`schemas/`)

| Schema File | Producer | Consumer(s) | Key Invariants |
|---|---|---|---|
| `candidate_profile.schema.json` | Engine 1 / Intake Form / External API | Gate 1, Engines 2, 4, 5 | Separates `verified_facts`, `inferred_capabilities`, `adjacent_career_paths`, and `ambiguities_to_confirm`. Includes `profile_status` (`draft` vs `confirmed`). |
| `market_pack.schema.json` | Market Config Author | Engines 2, 3, 4, 5 | Encodes country regions/cities, priority tiers, portals, statutory licensing & qualification authorities (e.g., ZAQA, EIZ, HPCZ, ZICA, SAQA), timezone, currency, and scam rules. |
| `search_strategy.schema.json` | Engine 2 (`generate_search_queries.py`) | Gate 2, Engine 3 | Explicitly traces every generated job title, keyword, and Boolean query back to the CV evidence or preference that triggered it (`rationale`). |
| `vacancy.schema.json` | Engine 3 (`dedupe_vacancies.py`) | Engine 4, Engine 5 | Enforces `verification_status`, `source_url`, `dedupe_key`, `deadline_iso`, `remote_geo_policy`, and extracted `mandatory_requirements` / `eligibility_constraints`. |
| `match_result.schema.json` | Engine 4 | Gate 3, Engine 5 | Enforces three non-overlapping arrays: `verified_requirements_met`, `inferred_transferable_skills`, and `missing_qualifications_and_blockers`. |

---

## 3. Mapping Engines to a Standalone JOBINTEL Backend

| JOBINTEL Skill Module | Recommended Platform Service / Worker |
|---|---|
| `scripts/extract_cv_text.py` + `engines/01_cv_analysis.md` | **Ingestion & Profile Extraction Service:** OCR/PDF parser + LLM structured extraction -> creates `CandidateProfile (draft)` -> triggers Gate 1 confirmation UI. |
| `markets/*.json` | **Market Registry Service:** Versioned JSON/DB store of African and remote job boards, statutory bodies, and regional aliases. |
| `engines/02_search_strategy.md` + `scripts/generate_search_queries.py` | **Strategy Builder API:** Deterministic query expansion + LLM title/adjacency enrichment -> surfaces Gate 2 transparency panel to user. |
| `engines/03_vacancy_discovery.md` + `scripts/dedupe_vacancies.py` | **Crawler / Verification Worker (future service; the skill today relies on the host's search and fetch tools):** search + full-page fetcher + deadline/scam/geo verifier + deduplicator. |
| `engines/04_evidence_matching.md` | **Evidence Matcher:** Deterministic hard-blocker pre-filter + LLM 3-bucket requirement alignment -> outputs explainable `MatchEvaluation`. |
| `engines/05_application_docs.md` + `scripts/render_pdf_pack.py` | **Document Studio:** HTML/WeasyPrint & DOCX generator + automated PyMuPDF 1-page overflow & fact-boundary auditor. |
| `engines/06_tracker_sync.md` + `scripts/build_tracker.py` | **Tracker & Cloud Sync (future service; today a new .xlsx is built locally and any cloud sync depends on a host connector):** idempotent DB/Sheets/Drive sync with paced batches to respect cloud API limits. |

---

## 4. Operational Lessons Built into JOBINTEL

The following production edge cases are explicitly handled in the engine specs and Python scripts:

1. **Deduplication Beyond URLs:** Aggregators and employer portals frequently republish the same role under different URLs. `dedupe_vacancies.py` normalizes company legal suffixes (`Limited`, `Ltd`, `Zambia`, `PLC`), strips punctuation and location suffixes in titles, and uses vacancy reference numbers when both records have one (equal refs from the same employer are duplicates; different refs are different vacancies), falling back to employer + title + location when a reference is missing.
2. **Snippet Trap Prevention:** Search snippets routinely omit critical disqualifiers buried in the body (e.g., *"Age 18–25 only"*, *"ZAQA certification is a must"*, *"combine CV + certificates into 1 PDF"*, *"Remote – US timezones only"*). Engine 3 mandates full-page inspection whenever accessible and flags snippet-only records as `partially_verified`.
3. **1-Page Visual PDF Overflow Guard:** Tailored CVs and cover letters easily spill onto an awkward 2-line second page. `render_pdf_pack.py` inspects rendered bounding boxes with PyMuPDF (`y_bottom <= page_height - footer_margin`) and fails loud if any document exceeds its target page count or leaks unverified placeholder text.
4. **Cloud Connector Rate-Limit & Serialization Safety:** Cloud Drive connectors often throttle rapid concurrent binary uploads, and spreadsheet APIs vary in 2D array handling. Engine 6 specifies idempotent pre-checks, `.xlsx` native conversion or structured batch updates, and resumable/paced uploads.
5. **Availability States:** A vacancy is `verified_open`, `likely_open`, `uncertain`, `expired` or `removed`, each with stored evidence and a check date. A missing deadline can never produce `verified_open`; a failed fetch is `uncertain`, never `removed`. See `engines/03_vacancy_discovery.md`.
