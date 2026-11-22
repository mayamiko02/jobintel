# jobintel

An AI-powered employment intelligence skill for discovering, verifying, matching, and tracking job opportunities across Africa — beginning with Zambia.

JOBINTEL is **CV-first and occupation-agnostic**. Rather than running a fixed job-search prompt for one profession, it inspects any candidate's CV (or structured profile payload), extracts strictly verified credentials alongside inferred transferable skills and adjacent career paths, confirms the profile with the candidate, builds a transparent multi-channel search strategy, verifies open vacancies from original listings, scores matches with full evidence separation, and produces tailored single-page application packs plus a deduplicated tracker.

---

## Core Design Principles

1. **Decoupled Architecture (`CV Engine` ≠ `Search Engine`):**
   - **Engine 1 (CV Analysis)** converts raw CVs/certificates into a portable `CandidateProfile` JSON contract (`schemas/candidate_profile.schema.json`).
   - **Engines 2–5 (Strategy, Discovery, Matching, Docs, Tracker)** consume only `CandidateProfile` + a `MarketPack` (`markets/*.json`).
   - Any frontend form, ATS, or standalone **JOBINTEL platform** can supply `CandidateProfile` JSON directly without touching the search, verification, or matching pipeline.
2. **Three Mandatory Human-in-the-Loop Gates:**
   - **Gate 1 — Candidate Confirmation:** Review extracted history, inferred adjacent paths, and missing/ambiguous items before searching.
   - **Gate 2 — Search Transparency:** Inspect generated job titles, industry categories, keywords, Boolean queries, locations, and portals so you know *why* vacancies are retrieved.
   - **Gate 3 — Evidence-Based Match Review:** Inspect **Verified Requirements**, **Inferred Transferable Skills**, and **Missing Qualifications / Hard Blockers** side-by-side. Matches are never fabricated.
3. **Evidence-Based Availability:** every vacancy is `verified_open`, `likely_open`, `uncertain`, `expired` or `removed`, with stored evidence and a check date (`engines/03_vacancy_discovery.md`).
4. **Market-Aware Verification Across Africa:**
   - Ships with a deep **Zambia (`markets/zambia.json`)** pack (all 10 provinces, local boards, NGO/multilateral/public portals, regulator awareness, timezone and anti-scam heuristics). Each portal, regulator and pattern is tagged `observed`, `reported` or `provisional`, so you can see what was checked in a live session and what still needs verification. The **Kenya, South Africa, Nigeria, Ghana and Remote Africa** packs are provisional and unverified. A template (`markets/_template_market.json`) helps you add any country.
5. **Application Packs & Trackers:**
   - Drafts tailored application documents (1-page PDFs when the optional rendering libraries are installed, otherwise plain text), per-role submission checklists and a 3-sheet Excel tracker. Google Sheets/Drive sync is only possible when the host session provides a connector. JOBINTEL has **no scheduler and never auto-submits or emails employers**.

---

## Repository Structure

```text
jobintel/
├── SKILL.md                  # Main AI Agent Skill specification & workflow orchestration
├── ARCHITECTURE.md           # Platform integration & decoupled JSON contract architecture
├── schemas/                  # JSON Schemas (CandidateProfile, SearchStrategy, Vacancy, MatchResult, MarketPack)
├── engines/                  # 6 modular engine playbooks (CV Analysis -> Tracker Sync)
├── markets/                  # Pluggable country & regional market configs (ZM flagship + KE, ZA, NG, GH, Remote)
├── templates/                # WeasyPrint HTML/CSS PDF templates + Gate UI templates + checklist template
├── scripts/                  # Runnable Python CLI tools (extract, validate, query-gen, dedupe, PDF audit, xlsx builder)
├── docs/                     # INSTALL.md (setup, usage, limitations) and TOOLS.md (external tool requirements)
├── examples/                 # Fictional multi-profession fixtures (Nurse, Civil Engineer, Software Dev)
├── tests/                    # Automated test suite
└── CHANGELOG.md              # Release notes
```

---

> Setup, prerequisites and limitations: [docs/INSTALL.md](docs/INSTALL.md). What needs external tools: [docs/TOOLS.md](docs/TOOLS.md).

## Quick Start

### 1. Use as an AI Agent Skill
Clone or install this repository into your agent's skills directory (built to the open `SKILL.md` convention; it has not been tested on every runner, so check yours):

```bash
git clone https://github.com/mayamiko02/jobintel.git
```

Then prompt your agent with a candidate's CV (or a `CandidateProfile` JSON):
> *"Run JOBINTEL on this CV for Zambia, prioritising Lusaka and Copperbelt, and confirm my extracted profile before searching."*

### 2. Run the Python CLI Utilities & Test Suite

```bash
cd jobintel
python3 -m unittest discover -s tests -v
```

Optional dependencies for full PDF/DOCX/Excel generation:

```bash
pip install -r scripts/requirements.txt
```

Individual tools:

```bash
# 1. Extract text and embedded URLs from a CV (PDF/DOCX/TXT)
python3 scripts/extract_cv_text.py path/to/cv.pdf --out /tmp/cv_extracted.json

# 2. Validate a CandidateProfile JSON & check Gate 1 readiness
python3 scripts/validate_contract.py profile examples/nurse_lusaka_profile.json

# 3. Generate transparent Boolean queries & portal routing for a market
python3 scripts/generate_search_queries.py examples/civil_engineer_copperbelt_profile.json markets/zambia.json

# 4. Deduplicate and availability-audit vacancy records
python3 scripts/dedupe_vacancies.py vacancies_raw.json --market markets/zambia.json --out vacancies_clean.json

# 5. Build a new 3-sheet Excel (.xlsx) tracker (does not merge into an existing one)
python3 scripts/build_tracker.py --input tracker_payload.json --out "Job_Hunt_Tracker.xlsx"

# 6. Render & audit 1-page CV + Cover Letter + Merged PDF pack
python3 scripts/render_pdf_pack.py --spec pack_spec.json --out-dir ./output_pack
```

---

## Adding a New Country or Regional Market

Copy `markets/_template_market.json` to `markets/<country_slug>.json`, fill in local administrative regions, portals, statutory/licensing bodies, currency, timezone, and scam/disqualifier patterns, then validate:

```bash
python3 scripts/validate_contract.py market markets/<country_slug>.json
```

---

## Privacy & Ethical Safeguards

- **Zero personal files or PII** are stored in this repository. All bundled examples use completely fictional personas.
- JOBINTEL **never** fabricates credentials, overrides mandatory eligibility gaps silently, or submits applications without explicit human approval.

## License

MIT — see [LICENSE](LICENSE).
