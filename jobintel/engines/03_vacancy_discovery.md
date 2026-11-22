# Engine 3 — Multi-Source Vacancy Discovery & Verification Engine

**Input Contract:** `SearchStrategy` JSON + `MarketPack` JSON + current local date/timezone.
**Output Contract:** Array of `VerifiedVacancy` records (`schemas/vacancy.schema.json`) + structured `Excluded & Audit Log`.

**Tools this engine needs:** web search and a page fetcher (see `docs/TOOLS.md`). Without them the engine cannot verify anything; it must say so and stop at a manual search plan instead of producing "verified" records.

---

## Step 1: Multi-Channel Search Execution

Execute the approved `SearchStrategy.boolean_queries` broadly across the available search tools and connectors:
1. Local job boards listed in `MarketPack.portals` (`reliability_tier: high` first).
2. Official corporate career pages and ATS platforms (Sage HR, Workday, Greenhouse, Lever, SmartRecruiters, custom employer portals).
3. NGO, UN, multilateral and donor-funded programme portals.
4. Public-sector, parastatal, university and regulatory announcements.

Also page through category and "latest vacancies" listing pages, which surface many roles that keyword queries miss. Do not stop after one query or an arbitrary hit count while promising channels in `SearchStrategy.source_channels` remain unsearched. List channels that could not be reached (blocked, login wall, robots restriction) in the report. Never work around a site's access restrictions.

Search-result ages ("posted 2 days ago") and cached snippets are frequently stale. Treat them as leads, never as evidence of availability.

## Step 2: Mandatory Full-Page Verification (Never Snippet-Only)

For every candidate vacancy, **fetch the full listing URL** whenever accessible and capture, or mark `"Not specified"`:
1. **Identity:** employer (the real employer, not only the posting site), exact title, duty station, city/province, employment type.
2. **Dates:** date posted and closing date/time. Compare against **today's date in `MarketPack.timezone`**. Respect afternoon cutoffs (for example `17:00 CAT`).
3. **Application mechanism:** URL, form or email, the exact required subject line, drop-off alternatives, reference number.
4. **Hidden eligibility and submission constraints:** statutory/accreditation mandates, age or demographic clauses, formatting mandates (single combined PDF, NRC copy, salary expectation), and remote geographic policy (never assume "Remote" is open to the candidate's country).
5. **Authenticity checks** (see below).

If the full page cannot be fetched (login wall, timeout, PDF viewer), set `verification_status = "partially_verified_snippet"`, record `fetch_failed` or `snippet_only` in `availability_evidence.basis`, and say exactly what is unverified. Never label a snippet-only hit `verified_full_ad`.

## Step 3: Availability States (single source of truth)

Every vacancy gets exactly one `availability_status` plus an `availability_evidence` block (`checked_at`, `basis[]`, `recency_days`). Availability decays; always store the check date. The default recency window is **30 days** unless the market pack or candidate sets another.

| State | Required evidence (all must hold) | Counts as open? | What happens |
|---|---|---|---|
| `verified_open` | Full page fetched (or employer ATS page) on `checked_at` **and** an explicit closing date on or after today in the market timezone (if today, the cutoff time has not passed) **and** no "closed/filled" banner **and** an application route is present | Yes | Match, track, recommend |
| `likely_open` | No contradiction, but one pillar of `verified_open` is missing: either (a) full page fetched, **no closing date stated**, `date_posted` within the recency window and no closed banner; or (b) a future closing date seen only on an aggregator copy or a snippet, with the full ad not confirmed | Yes, labelled "likely open" | Match and track with the label and the reason; remind the candidate to confirm before relying on it |
| `uncertain` | No closing date **and** no recent dated posting; or only a snippet; or conflicting dates; or the fetch failed (timeout, block, error) so nothing could be confirmed | No | Not matched or tracked as a recommendation. Listed in the report under "could not verify" with the reason |
| `expired` | Closing date (and cutoff time) has passed, or the page states the vacancy is closed, filled or no longer accepting applications | No | Excluded & Audit Log |
| `removed` | A successful server response affirmatively shows the listing is gone: HTTP 404/410, a "no longer available" message, or a redirect to a generic listing index, confirmed by a second attempt. A timeout or block is **not** `removed`; that is `uncertain` | No | Excluded & Audit Log |

Rules that resolve earlier ambiguity:
- A missing deadline can never produce `verified_open`. Its ceiling is `likely_open`.
- A stale or relative age in search results never upgrades a state.
- `is_currently_open` is derived: true only for `verified_open` and `likely_open`. `scripts/validate_contract.py` rejects records where the two disagree.
- If dates conflict (for example the page and the aggregator differ), use the employer's own page; if that is unavailable, state `uncertain` with `conflicting_dates`.
- Re-check before the tracker shows a vacancy again after more than a few days, and always before the candidate applies.

## Step 4: Authenticity and Risk Flags

Check every vacancy against `MarketPack.scam_red_flags` and these general rules.

**Hard flags: exclude (`excluded_scam_or_unverified`):**
- Any fee for application, interview, training, medicals, uniforms or placement.
- Guaranteed job or income, or an implausible salary.
- Requests for bank, card, mobile-money or password details at application stage.
- No identifiable employer and no way to verify one.
- Apply links that lead somewhere unrelated or dead (`apply_link_dead`).

**Soft flags: include with a plain warning and hold sensitive documents until verified:**
- Free webmail as the only contact for an employer that should have its own domain.
- A third-party recruiter or agency whose domain is unrelated, so the end employer is unclear.
- ID-document copies requested at first application.
- Commission-only pay presented as a job.
- Several adverts under different employer names sharing one contact email.
- Inconsistent fields (for example both "Contractor" and "Full-time"), vague duties, or copied text.
- Gender, age or similar restrictions. Record them as eligibility facts; the candidate decides.

Quick checks: does the employer have a web presence and consistent address? Does the same job appear on the employer's own site? Does the contact domain belong to the employer?

## Step 5: De-duplication and Audit Logging

```bash
python3 scripts/dedupe_vacancies.py raw_vacancies.json --market markets/<market>.json --today YYYY-MM-DD --out clean_vacancies.json
```

Rules (implemented and tested in `scripts/dedupe_vacancies.py`):
1. **Both records have a reference number:** duplicates only if the normalised references match and the employers match. Different references mean different vacancies, even with the same title and employer.
2. **A reference is missing on either side:** fall back to normalised employer + title + location. An empty location on either side counts as unknown, not as a mismatch.
3. Source URL, source name, punctuation, `&` versus `and`, company suffixes (`Limited`, `Ltd`, `Zambia`, `PLC`, `Group`...) and trailing location hints in titles never decide anything.
4. Keep the record with the strongest evidence: full ad first, then better availability, then the employer's own page or email, then a reference number.
5. The script also derives availability from the record's own fields, downgrades unsupported `verified_open` claims and routes `uncertain`, `expired` and `removed` items into the audit log with the reason.

The script never fetches pages. It can only apply the rules to evidence the agent already collected.
