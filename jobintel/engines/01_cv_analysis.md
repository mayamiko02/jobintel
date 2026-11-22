# Engine 1 — CV & Candidate Intelligence Engine

**Architectural Boundary:** Engine 1 is **strictly decoupled** from job searching. Its sole deliverable is a structured `CandidateProfile` JSON (`schemas/candidate_profile.schema.json`) that can also be supplied directly by a manual web intake form or an external JOBINTEL platform API.

---

## Step 1: Ingest Raw Materials

Read all candidate-supplied files:
- Primary CV (`PDF`, `DOCX`, `TXT`, `MD`, or image-based CV).
  - Run `python3 scripts/extract_cv_text.py <file>` to extract text, embedded portfolio/LinkedIn URLs, and detect if a PDF is scanned/image-only (requiring vision OCR).
- Supporting certificates, academic transcripts, or practicing licenses (if supplied).
  - Extract issuing institution, credential title, qualification level, registration/membership number, date issued, and score/status (e.g., `"in progress"` vs `"completed"`).

## Step 2: Fact-Grounded Extraction (`verified_facts`)

Extract **only** facts explicitly evidenced in the CV or uploaded certificates:
1. **Identity & Location:** Name, email, phone, portfolio/LinkedIn URLs, current city, province/region, country (`country_code`), and work authorization. Leave `verified_age_bracket` and `national_id_available` as `null` unless explicitly present.
2. **Work History:** Role title, employer, location, start/end dates, employment type (`full_time`, `contract`, `project_based`, `internship`, `freelance`), concrete responsibilities, and measurable outcomes (only metrics explicitly written on the CV).
3. **Education & Statutory Credentials:** Completed degrees/diplomas/certificates, in-progress studies, and statutory/professional body registrations (e.g., `EIZ`, `HPCZ`, `NMCZ`, `ZICA`, `LAZ`, `SAICA`, `NCK`, `COREN` — whichever applies to the candidate's profession).
4. **Explicit Skills, Tools & Languages:** Tag every skill with its **emergent domain cluster** (never force-fit into an unrelated preset taxonomy) and cite its `evidence_source` (`cv` or `certificate`).

### Credential classification rules
- Distinguish certificate, diploma, degree and short course. Online-course "certificates of achievement" and similar are short courses, not formal qualifications, unless the issuer says otherwise. Record `formal_qualification: false` where the schema allows, or note it in the evidence.
- Study in progress stays `in progress`, with the expected completion date if stated. Never present it as completed.
- Never assume a credential is accredited or recognised by a national regulator. Leave accreditation `unknown` until the CV, certificate or candidate states it.
- Self-employed and freelance work counts as experience but must be labelled as such, because employers read it differently from employment.
- Infer from what the person did, not from what a job title usually implies. A "manager" title in a one-person business is not evidence of people management unless the CV says so.

## Step 3: Analytical Inference (Strictly Tagged as `inferred`)

From verified duties and projects, derive — **and keep strictly separate from `verified_facts`**:
1. **`inferred_transferable_skills`:** Capabilities demonstrated in practice even when not listed as a headline skill (e.g., a Site Nurse managing clinic vaccine cold-chain logs demonstrates *inventory control & compliance documentation*; a Civil Site Intern coordinating subcontractors demonstrates *stakeholder coordination & site scheduling*; a Freelance Designer handling client briefs and invoicing demonstrates *client account management & commercial awareness*). Record `inferred_from` and `confidence` (`high`, `medium`, `low`).
2. **`adjacent_career_paths`:** Identify 2–6 realistic adjacent career tracks enabled by combinations of the candidate's skills and education. Include both:
   - `why_plausible` (exact skills/duties that bridge cleanly)
   - `required_bridge_or_gap` (what may still be missing — e.g., formal license, specific software, extra years)
3. **`seniority` Assessment:** Estimate `estimated_years_relevant` conservatively (do not double-count overlapping part-time or project periods). Determine `recommended_levels` (typically 2–3 adjacent bands such as `["entry_junior", "assistant_associate", "officer_specialist"]`) and explicitly populate `excluded_levels` (e.g., exclude `executive_director` for early-career profiles).

## Step 4: Identify Missing, Ambiguous, or Blocker-Sensitive Details (`ambiguities_to_confirm`)

Do **not** guess answers to critical operational questions. Populate `ambiguities_to_confirm` whenever missing:
- **Geographic scope & relocation:** Home city only vs. domestic provinces vs. regional Africa? Is candidate willing to relocate at own cost if relocation support is absent?
- **Remote work & shift hours:** Open to fully remote roles? Exclude overnight foreign-timezone shifts (e.g., US EST) or accept any timezone?
- **National Qualification / Statutory Accreditation Status:** In markets with mandatory foreign/domestic credential evaluation (e.g., **ZAQA** in Zambia, **SAQA** in South Africa, **KNQA** in Kenya), confirm whether certification is `verified`, `in_progress`, or `not_started` — and whether active professional body registration (e.g., EIZ, HPCZ, ZICA) is held.
- **Role-blocking practical details (only ask when needed):** Notice period/availability, salary band (when employers require stating expected pay), valid driver's license (if relevant to field/sales/engineering), and National ID availability.

## Step 5: Mandatory Gate 1 — Candidate Confirmation

Present `templates/gate1_profile_confirmation.md` (populated from the draft `CandidateProfile` JSON).
- Clearly distinguish **Verified from CV/Certificates** vs. **Inferred Transferable Skills & Adjacent Paths** vs. **Questions to Confirm**.
- **STOP.** Wait for the candidate to confirm or edit their profile, resolve ambiguities, and set `profile_status = "confirmed"` before invoking Engine 2.
