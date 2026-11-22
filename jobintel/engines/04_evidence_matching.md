# Engine 4 — Evidence-Based Matching Engine

**Input Contract:** Confirmed `CandidateProfile` + `VerifiedVacancy[]` whose `availability_status` is `verified_open` or `likely_open` (see `engines/03_vacancy_discovery.md`). Carry the availability label onto every match card; `likely_open` roles must be shown as "likely open, confirm before applying". `uncertain`, `expired` and `removed` vacancies are never matched.
**Output Contract:** `MatchEvaluation[]` (`schemas/match_result.schema.json`) + ranked `12-Point Search Report`.

---

## Core Rule: Three Non-Overlapping Evidence Buckets

For every vacancy, inspect `requirements.mandatory` and `requirements.preferred` plus `eligibility_and_submission_rules` against `CandidateProfile`. Classify every single requirement into **exactly one** of three buckets:

### Bucket 1: `verified_requirements_met`
Requirements **directly and unambiguously satisfied** by `work_experience`, `education_and_credentials`, or `skills.explicit_skills` / `tools_and_systems` backed by `cv`, `certificate`, or `candidate_confirmed`.
- Quote the specific candidate evidence (`e.g., "Certificate in Project Planning & Management (2023)"`, `"3 years clinic ward coordination at..."`).

### Bucket 2: `inferred_transferable_skills`
Requirements where the candidate lacks the exact title/sector keyword, **but** holds credible transferable capability from documented tasks.
- Label explicitly as **inferred transferable bridge** and assign `confidence` (`high`, `medium`, `low`).
- **Never** rewrite or disguise a transferable skill as direct years of experience in that exact role.

### Bucket 3: `missing_qualifications_and_blockers`
Any unmet mandatory requirement, missing statutory license, unverified credential status, demographic constraint, or location/shift conflict. Tag each item with exact `severity`:
- `hard_blocker`: Explicitly disqualifying gap (e.g., role requires a Bachelor's in Civil Engineering + active EIZ Corporate Membership and candidate holds a Technician Certificate without EIZ; or role is restricted to US EST night shift which candidate excluded).
- `unverified_eligibility_check`: Vacancy lists a condition not confirmed in `CandidateProfile` (e.g., `Age: 18–25` when `verified_age_bracket` is `null`; or requires `ZAQA` when candidate status is `in_progress`). Surface prominently as a candidate verification gate!
- `manageable_gap`: Missing desirable or soft preference (e.g., asks for 3 years experience when candidate has 2.5 years + strong portfolio/outcomes, or asks for a specific tool closely adjacent to tools candidate already uses).
- `minor_desirable`: Nice-to-have bonus not strictly essential.

---

## Hard Rules Before Classification

- **A mandatory requirement the profile does not meet caps the fit at Stretch.** It can never be Strong Fit or Possible Fit because the duties look attractive. If it is a statutory bar with no pathway, the role is Excluded.
- **Never match on a title alone.** Compare requirements, not job names. The word "Executive" in sales and marketing adverts is often an entry or mid title in some markets; check the stated years and duties.
- **Report conflicting requirements, do not pick the convenient one.** If the advert body says "diploma" and the metadata says "bachelor's", show both and say which is more likely binding.
- Each "met" item needs evidence on both sides: the advert line and the profile entry.
- Gender, age and other eligibility restrictions are shown on the first screen of the card, not buried.

## Fit Tier Classification Matrix

| Fit Tier | Criteria | Default Action |
|---|---|---|
| **Strong Fit** | Meets all (or virtually all) `mandatory` qualification/experience/location/license criteria directly via `verified_requirements_met`; zero unresolved `hard_blocker`s; any credential verification `in_progress` is honestly disclosable. | `Apply Immediately` |
| **Possible Fit** | Meets core foundation (`education` / baseline skills) with 1–2 `manageable_gap`s bridged cleanly by `inferred_transferable_skills`, **OR** has 1 `unverified_eligibility_check` (such as an age/demographic clause or shared inbox/relocation cost) that the candidate must confirm first. | `Apply With Tailored Framing` or `Hold / Confirm Eligibility First` |
| **Stretch** | Valuable growth opportunity lacking a significant mandatory requirement (e.g., higher degree level or +2–3 extra years experience) or steep domain pivot, with no absolute statutory bar. | `Apply With Tailored Framing` (low probability — clearly labeled Stretch) |
| **Excluded** | Fails a `hard_blocker` (expired, scam, incompatible timezone/geo-restriction, missing mandatory statutory license with zero pathway, or materially mis-leveled seniority). | `Skip / Excluded` (log in Excluded & Audit Log) |

---

## Mandatory Gate 3 — 12-Point Search Report & Selection Checkpoint

Present the complete structured Search Report containing:
1. Total relevant vacancies reviewed
2. Verified currently open vacancies count
3. New records vs. existing tracker records
4. Duplicates & exclusions skipped (with grouped audit summary)
5. Breakdown by location/province and career domain
6. **Strong Fit**, **Possible Fit**, and **Stretch** tables with **Verified / Transferable / Missing & Blockers** breakdown for each role
7. Approaching/urgent deadlines sorted chronologically
8. Any unverified details or eligibility alerts (`ZAQA/SAQA`, `Age`, `NRC`, `1-PDF merge`, `Expected Salary`)
9. Link/path to updated tracker

**STOP.** Ask the candidate which roles or fit tiers they want tailored application packs generated for (e.g., Strong Fit only, or Strong + Possible Fit) before running Engine 5.
