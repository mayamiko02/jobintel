# Engine 2 — Search Strategy & Query Generator

**Input Contract:** Requires a confirmed `CandidateProfile` (`profile_status == "confirmed"`) + target `MarketPack` (`markets/<market>.json`, plus `markets/remote_africa.json` if `preferences.remote_preference` permits remote work).
**Output Contract:** `SearchStrategy` JSON (`schemas/search_strategy.schema.json`).

Engine 2 **never reads raw CV files** — it operates purely on `CandidateProfile` so strategies are reproducible whether the profile originated from a PDF CV, an intake form, or an external platform database.

---

## Step 1: Dynamic Role & Title Expansion (`title_clusters`)

Build 2–6 dynamic `title_clusters` anchored in the candidate's `primary_domains`, `work_experience`, `education_and_credentials`, and `adjacent_career_paths`. For **each** cluster generate:
1. **`primary_titles`:** Exact titles aligned with the candidate's core evidence and `recommended_levels`.
2. **`alternative_titles`:** Common market synonyms in the target region (for example: *Commercial Assistant* vs *Billing & Customer Operations Assistant*; *Site Engineer* vs *Clerk of Works* / *Junior Civil Engineer*; *Monitoring & Evaluation Officer* vs *Programme Data Officer*; *Accounts Assistant* vs *Bookkeeper*).
3. **`adjacent_titles`:** Transferable/cross-functional roles backed by `inferred_transferable_skills` + `adjacent_career_paths`.
4. **`cv_evidence_rationale`:** One explicit sentence naming the CV experience or credential that justifies searching this cluster.

Apply **Seniority Guardrails**:
- Prefix or filter queries according to `seniority.recommended_levels` (`Junior`, `Assistant`, `Officer`, `Coordinator`, `Associate`, `Specialist`, `Intern` vs `Senior`, `Lead`, `Manager`).
- Add negative/exclusion filters for `seniority.excluded_levels` (`-Director -VP -"Head of"` unless candidate meets management seniority).

## Step 2: Keyword & Boolean Query Synthesis

You may run `python3 scripts/generate_search_queries.py <confirmed_profile.json> <market.json>` to bootstrap deterministic Boolean strings, then refine with domain nuance:
- **Core Title + Location Queries:** Combine primary/alternative titles with Tier 1 & Tier 2 cities/regions from `MarketPack.priority_regions`.
- **Skill-Cluster Queries:** Catch unorthodox titles by querying combinations of core domain tools, statutory bodies, or competencies (e.g., `("EIZ" OR "Civil Engineering") ("AutoCAD" OR "site supervision") "Kitwe" OR "Ndola"` or `("HPCZ" OR "Registered Nurse") ("ART" OR "MCH" OR "public health") "Lusaka"`).
- **Portal-Targeted Queries:** Pair top role clusters with trusted domains in `MarketPack.portals` (`site:<portal_domain>` or `inurl:careers`) plus official NGO/multilateral/public-sector channels.
- **Remote Eligibility Queries (only if enabled):** Explicitly include candidate country/region eligibility qualifiers (e.g., `"Remote" ("Zambia" OR "Africa" OR "EMEA" OR "Worldwide")`), excluding incompatible shift regions if configured (`preferences.excluded_shift_or_industries`).
- **Freshness Window:** Filter queries toward active hiring windows relative to today's date (e.g., current month/previous 30–45 days) while still inspecting rolling portals.

## Title Vocabulary and Seniority Cautions

Local employers use titles loosely. Search around a core role using regional variants: Officer, Assistant, Coordinator, Executive, Representative, Personnel, Associate, Specialist, Trainee, Attache, Marketer, Consultant. Small employers often advertise unusual forms ("Marketing Personnel", "Marketer", "Field Representative"). Do not exclude "Executive" automatically for sales, marketing or customer roles: in several African markets it means an entry or mid-level post. Verify the stated requirements instead of trusting the word. Keep "Head", "Director", "Chief" and similar excluded unless the seniority evidence supports them.

Every title, keyword and location in the brief must carry a one-line reason tracing it to the profile and be labelled Direct (demonstrated experience), Transferable (inferred skill) or Stretch/Pivot (above band or an adjacent path).

## Step 3: Mandatory Gate 2 — Search Transparency Brief

Before executing broad searches, render `templates/gate2_search_transparency.md` showing:
1. Generated primary, alternative, and adjacent job titles — **and why each was selected from the profile**.
2. Core keywords, tools, statutory terms, and Boolean search queries.
3. Priority geographic tiers and remote/shift boundary rules.
4. Target portals and exclusion criteria.

Allow the candidate to confirm, add, or trim any cluster or location before Engine 3 runs live searches (or proceed directly if the candidate already pre-approved autonomous execution for the confirmed profile).

**Unattended runs:** if nobody can answer, proceed on the draft, put an `UNCONFIRMED PROFILE` line at the top of every output, and list the assumptions made.
