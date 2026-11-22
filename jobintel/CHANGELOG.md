# Changelog

## 1.1.0 - Pre-release engineering review and merge

This release merges two independently built JOBINTEL packages and applies a pre-release review. The base is the package with six engines, five schemas, six market packs, scripts and tests. Strengths of the second package (a lighter, document-first version) were merged in.

### Fixed
- **Duplicate detection (`scripts/dedupe_vacancies.py`).** Rewritten as pairwise matching. When both records have a reference number, the references decide (equal ref and same employer is a duplicate; different refs are different vacancies, even with identical employer, title and location). When a reference is missing on either side, it falls back to normalised employer + title + location. Source URLs and source names never matter. Improved normalisation: `&` and `and`, employer suffixes (`Ltd`, `Limited`, `Zambia`, `Group`, `PLC`...), punctuation, `Province`/`City` words in locations, reference punctuation. An empty location is treated as unknown. Duplicates keep the strongest evidence, independent of input order.
- **Contradictory verification rules.** Replaced the earlier open/closed wording with one table of five availability states (`verified_open`, `likely_open`, `uncertain`, `expired`, `removed`), each with explicit evidence criteria. A missing deadline can never produce `verified_open`. A failed fetch is `uncertain`, never `removed`. `is_currently_open` is now derived and checked for consistency.
- `build_tracker.py` no longer claims to update trackers. It builds a new workbook; merging is documented as a separate agent step. The 11 required columns now come first and in a fixed order, followed by Fit Tier, Match Summary, Availability and Notes.
- Removed or reworded claims that implied capabilities that do not exist: nightly or scheduled re-runs, automatic cloud sync, automated visual template cloning, and compatibility with named agent runners. Platform-roadmap items in `ARCHITECTURE.md` are now labelled as future.
- All scripts now return a clean error and exit code 2 on unreadable or malformed input instead of a traceback. The fallback validator checks types, and `validate_contract.py` rejects non-object input and unknown artifact kinds.
- `.gitignore` strengthened (see Added).

### Added
- `availability_status` and `availability_evidence` in the vacancy schema, validator checks, sample fixture, tracker column and dedupe audit log.
- `docs/TOOLS.md`: which capabilities need web search, page fetching, spreadsheets, email, a scheduler or optional Python libraries, whether each is implemented in this repo, and what to do when it is missing. States plainly that there is no scheduler, email sender or submitter.
- `docs/INSTALL.md`: prerequisites, installation, first run, script usage, exit codes, adding a country, limitations and privacy.
- Test suite: 81 tests across `test_dedupe.py` (reference priority, missing references, different source URLs, punctuation and suffix variants), `test_availability.py`, `test_validation.py`, `test_malformed.py` (bad JSON, wrong types, missing files, bad dates, unsupported files, all CLIs) and `test_repo_hygiene.py` (no candidate files, no real-looking emails or phone numbers, `.gitignore` verified with real `git`), plus the existing suite.
- `.gitignore`: covers document, spreadsheet, image, archive and secret formats; common candidate directory names (uploads, cvs, resumes, profiles, trackers, applications, output, extracted); common file-name patterns (cv, resume, cover letter, certificate, transcript, profile, tracker, application pack); with an explicit allow-list for fictional fixtures and project files. A test proves it blocks private files and does not block real project files.
- Market pack provenance: each Zambia portal, regulator, eligibility pattern and scam flag is tagged `observed` (seen in a live session on a stated date), `reported` (stated by the original author, not re-checked) or `provisional`. The market schema supports it. Kenya, South Africa, Nigeria, Ghana and Remote Africa packs are marked provisional.

### Merged in from the second package
- Credential classification rules: short courses are not formal qualifications, in-progress study stays in progress, accreditation is `unknown` until stated, freelance work is labelled, titles are not evidence.
- Authenticity checks split into hard flags (exclude) and soft flags (warn and hold sensitive documents), including patterns seen in practice: shared contact emails across employers, agency adverts on unrelated domains, commission-only land sales, free-webmail contacts.
- Matching rules: an unmet mandatory requirement caps the fit at Stretch; never match on title alone; report conflicting requirements instead of choosing; show eligibility restrictions up front.
- Title vocabulary and seniority cautions (for example "Executive" can be an entry or mid title).
- Unattended-run behaviour (proceed on the draft, label it unconfirmed, never send or submit) and graceful degradation when tools are missing.
- Plain-text default for pasteable drafts, honouring the candidate's output preference.
- Zambia corrections: Great Zambia Jobs (greatzambiajobs.com) and Go Zambia Jobs (gozambiajobs.com) are separate sites and were conflated; UNjobs automated fetching is refused by robots rules; ZIM added as an observed membership requirement.
- Zambia observations on search quality: stale snippet ages, very long employer lists on category pages, education metadata that contradicts advert text.

### Not changed (preserved as requested)
CV-analysis engine and its separation from the search engines, the candidate-profile schema, the three confirmation gates, dynamic search-strategy generation, evidence-based matching rules, and the modular country architecture.

### Known limitations
- PDF generation and its audit need `weasyprint` and `pymupdf`. They were not installed where this release was tested, so that test path was not exercised. The HTML rendering path was.
- Search, fetch, spreadsheet sync, email and scheduling depend on the host and are not tested here.
- Market packs other than Zambia are unverified; Zambia is only partly verified.
- Runner compatibility beyond the `SKILL.md` convention is untested.
