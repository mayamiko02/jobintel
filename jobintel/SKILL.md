---
name: jobintel
description: CV-first AI employment intelligence skill for analysing any candidate CV, generating a transparent search strategy, discovering and verifying real open vacancies across African markets (starting with Zambia) and remote roles, scoring evidence-based matches, generating tailored single-page PDF/DOCX application packs, and maintaining a deduplicated job application tracker. Use whenever a user uploads a CV/resume, provides candidate profile JSON, asks to find/verify jobs, tailor CVs/cover letters, or set up a job search tracker.
version: 1.1.0
license: MIT
metadata:
  author: jobintel
  primary_market: ZM
  supported_markets:
    - ZM
    - KE
    - ZA
    - NG
    - GH
    - REMOTE_AFRICA
  requires_confirmation_gates: true
  auto_submit: false
---

# JOBINTEL — CV-First Employment Intelligence Skill

JOBINTEL is a **modular, CV-first employment intelligence workflow**. It never relies on a hardcoded job-search prompt or a predefined occupation. Instead, every workflow begins by building or accepting a structured `CandidateProfile` grounded strictly in candidate evidence, confirming it with the candidate, deriving a transparent multi-channel search strategy, verifying live vacancies from full job postings, scoring matches across verified vs. inferred vs. missing evidence, and optionally generating tailored application packs and synced trackers.

## Non-Negotiable Principles

1. **Strict CV & Evidence Truthfulness:** Never fabricate qualifications, employment dates, employers, metrics, salary expectations, age, licenses, or software proficiency. Every factual profile claim must carry an evidence source (`cv`, `certificate`, `candidate_confirmed`, or `inferred`).
2. **Engine Decoupling:** Keep the **CV-Analysis Engine** (`engines/01_cv_analysis.md`) strictly decoupled from the **Search & Matching Engines** (`engines/02..04`). Downstream engines operate exclusively on `schemas/candidate_profile.schema.json` — enabling JOBINTEL to accept profiles from an uploaded CV, a manually filled intake form, or an external web/API platform without modification.
3. **Three Mandatory Human Gates:**
   - **Gate 1 — Candidate Confirmation:** Present the extracted profile, inferred transferable skills, seniority assessment, and missing/ambiguous details; obtain confirmation/edits before searching.
   - **Gate 2 — Search Transparency:** Display generated primary titles, adjacent titles, industry categories, keywords, Boolean queries, priority locations, and portals so the candidate understands why vacancies will be retrieved.
   - **Gate 3 — Evidence-Based Match Review:** Clearly separate **Verified Requirements**, **Inferred Transferable Skills**, and **Missing Qualifications / Hard Blockers** for every vacancy. Never manufacture a match.
4. **Full-Listing Verification:** Never rely on search-result snippets alone when the full posting URL can be fetched. Verify closing deadlines against the market's local timezone, geographic eligibility (especially for `"Remote"` roles), statutory body / accreditation requirements, and scam red flags.
5. **Human-in-the-Loop Submissions:** Never submit applications, fill forms, or email employers on the candidate's behalf without explicit per-action authorization.

---

6. **Honest Tooling:** JOBINTEL has no crawler, scheduler, email client or spreadsheet service of its own. Live search, page fetching, spreadsheet sync, email and scheduling depend on tools the host session provides (`docs/TOOLS.md`). Check the tool list first, tell the candidate what is and is not possible, and never imply a scheduler or integration exists when it has not been used successfully in this session.
7. **Unattended Runs:** If nobody can answer a gate, proceed on the draft, put an `UNCONFIRMED PROFILE` line at the top of every output and list the assumptions made. Never submit, send or share documents unattended.

## Modular Execution Workflow

Load each module progressively as you advance through the pipeline:

### Stage 1 — CV & Candidate Intelligence (`Engine 1`)
- **Read:** `engines/01_cv_analysis.md` and `schemas/candidate_profile.schema.json`
- **Optional Tool:** `python3 scripts/extract_cv_text.py <cv_file>` (supports PDF, DOCX, TXT/MD; extract certificates too if provided)
- **Skip condition:** If the caller already supplies a validated `CandidateProfile` JSON from an intake form or external platform with `profile_status == "confirmed"`, validate with `scripts/validate_contract.py` and proceed to Stage 2.
- **Output:** Draft `CandidateProfile` JSON + flagged `ambiguous_or_missing` questions (location preferences, relocation openness, remote/shift boundaries, credential verification status such as ZAQA/SAQA/EIZ/HPCZ, notice period, age/demographic constraints only if explicitly relevant to local postings).
- **MANDATORY STOP -> GATE 1:** Render `templates/gate1_profile_confirmation.md` (or use structured clarification questions if supported) and wait for the candidate to confirm or edit before proceeding.

### Stage 2 — Search Strategy Generation (`Engine 2`)
- **Read:** `engines/02_search_strategy.md`, `schemas/search_strategy.schema.json`, and the target market file in `markets/<country>.json` (default `markets/zambia.json` + `markets/remote_africa.json` if open to remote).
- **Optional Tool:** `python3 scripts/generate_search_queries.py <confirmed_profile.json> <market.json>`
- **Output:** `SearchStrategy` JSON containing core job titles, alternative & adjacent titles, industry categories, skill/tool keywords, Boolean search strings, evidence-backed seniority band, geographic priority tiers, and portal routing.
- **MANDATORY STOP / TRANSPARENCY BRIEF -> GATE 2:** Render `templates/gate2_search_transparency.md` showing the candidate *why* and *how* vacancies will be searched. Let them add/drop titles, locations, or salary/shift constraints if desired before launching searches.

### Stage 3 — Multi-Source Vacancy Discovery & Verification (`Engine 3`)
- **Read:** `engines/03_vacancy_discovery.md` and `schemas/vacancy.schema.json`
- **Actions:**
  1. Execute searches across web search tools, official career pages, NGO/multilateral boards, and market-specific job portals listed in `markets/<country>.json`.
  2. Fetch full job descriptions for candidate listings; extract exact deadlines, location/province, employment type, reference IDs, statutory/accreditation clauses, demographic clauses, and direct apply links/emails.
  3. Assign each vacancy an `availability_status` (`verified_open`, `likely_open`, `uncertain`, `expired`, `removed`) with evidence, using the criteria in `engines/03_vacancy_discovery.md`. Only `verified_open` and `likely_open` proceed to matching.
  4. Run deduplication (`python3 scripts/dedupe_vacancies.py`): reference numbers decide when both records have one; otherwise normalized employer + title + location. Never by URL alone.
  5. Route uncertain, expired, removed, scam-flagged, unverifiable, or hard-ineligible roles into the **Excluded & Audit Log** with clear reasons.

### Stage 4 — Evidence-Based Matching (`Engine 4`)
- **Read:** `engines/04_evidence_matching.md` and `schemas/match_result.schema.json`
- **Actions:**
  1. Evaluate every verified vacancy strictly against the confirmed `CandidateProfile` across three separated evidence buckets:
     - `verified_requirements_met` (directly backed by CV/certificate facts)
     - `inferred_transferable_skills` (clearly labeled reasoning, never disguised as direct experience)
     - `missing_qualifications_and_blockers` (hard qualification, experience, license, accreditation, age, or location gaps)
  2. Assign fit classification: `Strong Fit`, `Possible Fit`, `Stretch`, or `Excluded`.
- **CHECKPOINT -> GATE 3:** Present the ranked shortlist and transparent match breakdown (`12-point Search Report`). Ask which fit tiers or specific roles the candidate wants tailored application packs for.

### Stage 5 — Tailored Application Packs & Tracker Sync (`Engine 5`)
- **Read:** `engines/05_application_docs.md` and `engines/06_tracker_sync.md`
- **Tools:**
  - `python3 scripts/render_pdf_pack.py` — requires WeasyPrint and PyMuPDF. Generates a 1-page tailored CV PDF, a matching 1-page cover letter, a 2-page merged pack, and runs page-count, overflow and placeholder-leakage checks, using the built-in templates in `templates/`. Matching the look of a candidate's own styled PDF ("visual template cloning") is a manual agent procedure described in `engines/05_application_docs.md`; the script does not do it automatically.
  - `python3 scripts/build_tracker.py` — builds a **new** 3-tab `.xlsx` workbook (`Vacancy Tracker`, `Search Summary & Breakdown`, `Excluded & Audit Log`). It does not merge into an existing tracker; merging is an agent step (`engines/06_tracker_sync.md`).
- **Cloud Sync (only when the host provides active Google Sheets / Google Drive tools; see `docs/TOOLS.md`):**
  - Check for an existing tracker before creating a new one; preserve existing candidate `Status` values on updates.
  - Use resumable or paced uploads to respect cloud API rate limits.
  - Present the master guide and priority packs cleanly without sending any external emails or submissions.

---

## Directory Index

| Folder / File | Purpose |
|---|---|
| `schemas/` | Draft 2020-12 JSON Schemas separating CV analysis, strategy, vacancies, matching, and market configs |
| `engines/` | Step-by-step instructions and guardrails for each modular stage |
| `markets/` | Country & regional market packs (`zambia.json` flagship + `kenya`, `south_africa`, `nigeria`, `ghana`, `remote_africa`) |
| `templates/` | HTML/CSS PDF templates, Gate 1 & Gate 2 presentation templates, and per-role checklist template |
| `scripts/` | Python CLI utilities for CV extraction, contract validation, Boolean generation, deduplication, PDF rendering/auditing, and Excel tracker generation |
| `examples/` | Fictional multi-profession test fixtures (Healthcare, Civil Engineering, Software/Data) proving occupation-agnostic operation |
| `tests/` | Automated tests (`python3 -m unittest discover -s tests`) |
| `docs/` | `INSTALL.md` (setup, usage, limitations) and `TOOLS.md` (which capabilities need external tools) |
| `CHANGELOG.md` | Release notes |
