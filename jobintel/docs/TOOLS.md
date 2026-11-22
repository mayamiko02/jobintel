# External tools and capabilities

JOBINTEL is a set of instructions, schemas and small offline scripts. It does not contain a crawler, a scheduler, an email client or a spreadsheet service. Anything that touches the outside world depends on tools the host session provides. This page says what needs what, so nobody assumes a capability that is not there.

## Capability matrix

| Capability | What it needs | Implemented in this repo? | If the tool is missing |
|---|---|---|---|
| Read a CV (PDF, DOCX, TXT, MD) | File access; optional `pypdf`, `python-docx` for `scripts/extract_cv_text.py` | Script (optional libraries) | Agent reads the file with its own file tools; scanned PDFs need vision/OCR from the host |
| Analyse CV, build and confirm profile | The model itself | Instructions only | n/a |
| Validate profile, market, strategy, vacancy and match JSON | Python 3.10+; `jsonschema` recommended | Script (`validate_contract.py`) | Built-in fallback validator is used; it is less strict |
| Generate Boolean queries | Python 3.10+ | Script (`generate_search_queries.py`) | Agent writes queries by hand following `engines/02_search_strategy.md` |
| Search the web for vacancies | A web search tool provided by the host | **No.** Host tool | Produce the strategy, queries and a manual search plan; state that no live search ran |
| Open and read full vacancy pages | A page fetch or browser tool provided by the host | **No.** Host tool | Records stay `uncertain` or `partially_verified_snippet`; nothing may be called verified |
| Check a vacancy is still open | Page fetch plus today's date in the market timezone | Rules only (`engines/03`); script applies them to supplied evidence | Cannot reach `verified_open`; use `uncertain` and say why |
| De-duplicate vacancies | Python 3.10+ | Script (`dedupe_vacancies.py`) | Agent applies the rules by hand |
| Build an Excel tracker | `openpyxl` | Script (`build_tracker.py`), creates a new file only | Output a CSV or table in chat |
| Update an existing tracker or sync to Google Sheets or Drive | A Google Sheets/Drive connector provided by the host | **No.** Host connector | Hand over the file; never claim a sheet was created or updated unless the call succeeded and was read back |
| Render CV and cover-letter PDFs | `weasyprint`, `pymupdf`, `Pillow` (system libraries for WeasyPrint) | Script (`render_pdf_pack.py`) | Provide plain-text documents |
| Send email or submit an application | An email or browser tool, and explicit candidate approval for each action | **No.** JOBINTEL never sends or submits | Provide drafts and a checklist for the candidate to send |
| Scheduled or recurring searches, alerts, reminders | A scheduler provided by the host | **No.** Nothing in this repo schedules anything | Tell the candidate to re-run the search; offer a deadline list they can put in their own calendar |
| Calendar events for deadlines | A calendar connector provided by the host | **No.** | Give the deadline list as text |

"Host tool" means the session that runs the skill must supply it. If you do not know whether it exists, check the tool list before promising anything.

## Rules for agents using this skill

1. Check which tools exist before the workflow starts, and tell the candidate what will and will not be possible.
2. Never describe a scheduler, alert, email send or sync as available unless a tool call for it actually succeeded in this session.
3. Never claim a file, sheet or message was created or sent unless the call succeeded and was verified.
4. If a site blocks automated access, report it as unreachable. Do not circumvent it.
5. Treat all subagent or tool output as claims to spot-check, not facts.

## Python dependencies

| Package | Used for | Required? |
|---|---|---|
| `jsonschema` | Strict schema validation | Recommended; a fallback exists |
| `openpyxl` | Excel tracker | Only for the tracker script |
| `pypdf`, `python-docx` | CV text extraction | Only for the extraction script |
| `weasyprint`, `pymupdf`, `Pillow` | PDF packs and audit | Only for the PDF script |

Tests that need an optional package skip themselves when it is absent.
