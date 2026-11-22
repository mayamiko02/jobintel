# Engine 5A — Tailored Application Documents & Visual PDF Engine

**Input Contract:** Confirmed `CandidateProfile` + selected `VerifiedVacancy` + `MatchEvaluation` + optional uploaded candidate styled CV PDF (for visual template cloning).
**Output Artifacts per Role:**
1. `CV_<Candidate>_<Role>.pdf` — Strictly **1-page** tailored CV PDF
2. `Cover_Letter_<Company>_<Role>.pdf` — Strictly **1-page** tailored Cover Letter PDF matching the CV aesthetic
3. `Application_Pack_<Candidate>_<Company>_<Role>.pdf` — **2-page merged PDF** (Cover Letter + CV)
4. Optional editable `.docx` counterparts
5. `Application_Email_and_Submission_Checklist.md` — Exact recipient/URL, subject line, concise email body, attachment checklist, and pre-send alerts

---

## Output Format Preference

Honour the candidate's stated output preference. When none is stated, give pasteable drafts (cover letter text, application email, checklist) as **plain text with no markdown symbols** (no asterisks, hash headings or bullet glyphs) so they paste cleanly into an email or web form. If the candidate prefers plain text, apply that to the checklist and summary as well. PDF and DOCX packs are produced only when the optional libraries in `docs/TOOLS.md` are installed; otherwise provide the text and say that rendering was not possible.

## Strict Non-Fabrication Rules

1. **Zero Fact Invention:** Never add unverified software, invented KPIs/percentages, altered job dates, upgraded qualification titles, or unconfirmed salary/age claims.
2. **Evidence Framing Only:** Tailoring reorders bullets, foregrounds role-relevant verified duties, and mirrors the employer's truthful terminology — never invents experience.
3. **Honest Disclosure:**
   - If `credential_verification_status.status == "in_progress"` and the role requires accreditation (e.g., ZAQA/SAQA), include a crisp factual line in the Cover Letter noting certification is currently in progress.
   - If the ad requires stating expected salary (`requires_salary_expectation == true`) and `preferences.expected_salary.min_monthly` is `null`, insert an unmistakable `[INSERT EXPECTED MONTHLY SALARY IN <CURRENCY>]` placeholder AND surface it as a bold alert in the checklist and summary!
   - If `requires_combined_single_pdf == true` or `requires_national_id_copy == true`, highlight it at the top of `Application_Email_and_Submission_Checklist.md`.
4. **No Auto-Submit:** Never transmit emails or submit ATS forms automatically.

---

## Two Visual PDF Rendering Modes

### Mode A — Clean Executive Built-In Template (`templates/cv_template.html` + `templates/cover_letter_template.html`)
Use when no styled PDF template is supplied or when an ATS-clean 2-column A4 executive design is preferred. Customizable via accent color, fonts, optional circular portrait, and optional portfolio QR code.

### Mode B — Visual Template Cloning (manual agent procedure; `render_pdf_pack.py` does not automate it)
To preserve a candidate's existing Canva/InDesign/Illustrator CV visual identity while tailoring text cleanly per job:
1. Inspect the original PDF geometry with **PyMuPDF (`fitz`)**: record page size (`595.28 × 841.89 pt` A4), column split coordinates, top/bottom accent bar colors (`get_drawings()`), font families/sizes/weights (`get_text("dict")`), circular portrait image (`get_images()` + circular alpha mask via Pillow), and QR/brand graphics.
2. Replicate the exact CSS grid, colors, and embedded fonts (`@font-face`) in HTML/CSS and render via **WeasyPrint** (`@page { size: A4; margin: 0; }`).
3. Keep the Cover Letter visually coordinated (matching top accent bar, typography, contact strip, and bottom footer rule).

---

## Automated Geometry & Truthfulness Audit (`scripts/render_pdf_pack.py`)

Every generated pack **must pass** automated checks before delivery:
- **Page Count Invariant:** Tailored CV = `1` page; Cover Letter = `1` page; Merged Pack = `2` pages.
- **Overflow / Footer Collision Check:** Inspect rendered PDF text block bounding boxes via PyMuPDF and assert `max(block_y1) <= page_height - footer_margin` (for A4 `841.89pt` with footer bar, target `y_bottom <= 740pt`). If exceeded, tighten vertical spacing or trim redundant bullet phrasing and re-render — never ship clipped or 2-page-spill CVs!
- **Leakage & Placeholder Audit:** Scan extracted PDF text for banned fabrication tokens, unresolved Jinja/template braces (`{{`, `}}`), or stray unrequested candidate PII.
- **Visual Spot-Check:** Render representative output pages to PNG (`150+ dpi`) and visually inspect spacing, portrait alignment, and margins before finalizing.
