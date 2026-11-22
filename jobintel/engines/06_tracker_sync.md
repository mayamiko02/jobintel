# Engine 5B — Tracker & Cloud Workspace Sync Engine

**Input Contract:** `VerifiedVacancy[]` + `MatchEvaluation[]` + `Excluded & Audit Log` + optional active cloud connectors (`Google Sheets`, `Google Drive`).

---

## 1. Unified 3-Tab Application Tracker Schema

`scripts/build_tracker.py` **builds a new** `.xlsx` workbook from a payload. It does not read or merge an existing workbook. Merging into an existing tracker is a separate step: read the existing rows, run `dedupe_vacancies.py` or the equivalent check, and append only new roles. Syncing to Google Sheets requires an active Google Sheets/Drive connector (see `docs/TOOLS.md`); without one, hand over the `.xlsx` or CSV and say so.


1. **Tab 1 — `Vacancy Tracker`:**
   - Columns (the 11 required columns come first, in this order, so trackers stay compatible): `Company | Job Title | Industry/Category | Location/Province | Employment Type | Experience Level | Application Link / Email | Deadline | Date Posted | Source | Status`, followed by the extras `Fit Tier | Match Summary | Availability | Next Action / Notes`.
   - `Availability` holds `verified_open` or `likely_open`. Only those two states are tracked as recommendations; `uncertain`, `expired` and `removed` go to Tab 3.
   - Validated `Status` dropdown: `Not Applied`, `Applied`, `Assessment`, `Interview`, `Rejected`, `Offer`.
   - Default new verified rows to `Not Applied`.
   - Highlight urgent deadlines (within 0–3 days of today's date) clearly.
2. **Tab 2 — `Search Summary & Breakdown`:**
   - Executive KPIs (total reviewed, verified open, strong/possible/stretch breakdown, excluded count) + dynamic count formulas by Fit Tier, Location/Province, and Career Domain.
3. **Tab 3 — `Excluded & Audit Log`:**
   - Transparent record of every expired, scam-flagged, out-of-scope remote, duplicate, or hard-ineligible vacancy with date checked and explicit exclusion reason.

---

## 2. Idempotent Update & Cloud Connector Safety Rules

1. **Never Duplicate a Central Tracker:** Always search/list existing spreadsheets in Drive/Sheets first (using the configured tracker title, e.g. `Job Hunt <Year> – <Market>`). If one exists, read its current rows and **preserve every existing candidate `Status` and manual `Notes`**, adding only genuinely new roles (`dedupe_key`) or refreshing updated deadlines.
2. **Multi-Field Deduplication:** Check `(normalized_company, normalized_title, location, vacancy_ref)` — never rely on URL alone.
3. **Google Sheets Reliability Tip:** When uploading a newly built formatted `.xlsx` tracker to Google Drive for conversion to a native Google Sheet (`target_mime_type="application/vnd.google-apps.spreadsheet"`), verify sheet locale/timezone (`get_spreadsheet`) and re-apply dropdown data validations if needed. If modifying existing rows via Sheets API, verify exact array serialization schemas before writing.
4. **Google Drive Upload Resilience (connector-specific; only if the connector offers these operations):**
   - Organize folders cleanly by priority/deadline tier (`00_Application_Master_Guide`, `01_Urgent_...`, `02_...`, etc.).
   - For bulk PDF/DOCX uploads (20–100+ files), cloud connectors frequently enforce sliding binary upload rate limits. Prefer **`initiate_resumable_upload` + direct HTTP PUT streaming** (using `X-Goog-Upload-Offset` and `X-Goog-Upload-Command: upload, finalize` with exact byte size) or small paced batches (~8–12 files with pauses) and verify final folder counts with `list_files`.
5. **Honest Reporting Rule:** Never claim a file, sheet, or email draft was created or updated unless the tool call succeeded and was verified.
