#!/usr/bin/env python3
"""Render tailored 1-page CV PDF, 1-page Cover Letter PDF, and 2-page Merged Pack PDF with automated geometry & fact-leakage audits."""

import argparse
import html
import json
import re
import sys
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _esc(val: str) -> str:
    return html.escape(val or "")


def render_html_from_spec(spec: dict) -> tuple[str, str]:
    cv_tpl = (TEMPLATES_DIR / "cv_template.html").read_text(encoding="utf-8")
    cl_tpl = (TEMPLATES_DIR / "cover_letter_template.html").read_text(encoding="utf-8")

    accent = spec.get("theme", {}).get("accent_color", "#BDDDF1")
    dark = spec.get("theme", {}).get("dark_color", "#2B2F33")
    cand = spec["candidate"]

    contact_parts = [p for p in [cand.get("location"), cand.get("phone"), cand.get("email"), cand.get("portfolio")] if p]
    contact_line = "  |  ".join(_esc(p) for p in contact_parts)
    short_contact = " | ".join(_esc(p) for p in [cand.get("phone"), cand.get("email")] if p)

    avatar_path = cand.get("avatar_path")
    avatar_html = f'<img class="avatar" src="file://{_esc(avatar_path)}" alt="Portrait">' if avatar_path else ""
    qr_path = cand.get("qr_path")
    qr_label = cand.get("qr_label", "Portfolio")
    qr_html = f'<div class="qr-box"><img src="file://{_esc(qr_path)}" alt="QR"><div class="qr-label">{_esc(qr_label)}</div></div>' if qr_path else ""

    skills_html = "\n".join(f'<div class="skill-tag">&bull; {_esc(s)}</div>' for s in spec["cv"]["skills"])
    edu_html = "\n".join(
        f'<div class="edu-item"><div class="edu-title">{_esc(e["title"])}</div><div>{_esc(e["institution"])}{(" (" + _esc(e["year"]) + ")") if e.get("year") else ""}</div></div>'
        for e in spec["cv"]["education"]
    )
    lang_html = "\n".join(f'<div class="skill-tag">&bull; {_esc(l)}</div>' for l in spec["cv"].get("languages", []))

    exp_blocks = []
    for exp in spec["cv"]["experience"]:
        bullets = "".join(f"<li>{_esc(b)}</li>" for b in exp["bullets"])
        exp_blocks.append(
            f'<div class="item"><div class="role-line">{_esc(exp["role_title"])} &mdash; {_esc(exp["employer"])}</div>'
            f'<div class="meta-line">{_esc(exp.get("period", ""))} | {_esc(exp.get("location", ""))}</div>'
            f'<ul class="bullets">{bullets}</ul></div>'
        )
    exp_html = "\n".join(exp_blocks)

    certs = spec["cv"].get("certificates", [])
    certs_html = ""
    if certs:
        c_items = "".join(f'<div class="skill-tag">&bull; {_esc(c)}</div>' for c in certs)
        certs_html = f'<div class="section"><div class="section-title">Selected Certifications</div>{c_items}</div>'

    cv_html = (
        cv_tpl.replace("{{ACCENT_COLOR}}", _esc(accent))
        .replace("{{DARK_COLOR}}", _esc(dark))
        .replace("{{FULL_NAME}}", _esc(cand["full_name"]))
        .replace("{{HEADLINE}}", _esc(spec["cv"]["headline"]))
        .replace("{{CONTACT_LINE}}", contact_line)
        .replace("{{AVATAR_HTML}}", avatar_html)
        .replace("{{SUMMARY_TEXT}}", _esc(spec["cv"]["summary"]))
        .replace("{{SKILLS_HTML}}", skills_html)
        .replace("{{EDUCATION_HTML}}", edu_html)
        .replace("{{LANGUAGES_HTML}}", lang_html)
        .replace("{{QR_HTML}}", qr_html)
        .replace("{{EXPERIENCE_HTML}}", exp_html)
        .replace("{{CERTIFICATES_SECTION_HTML}}", certs_html)
    )

    cl = spec["cover_letter"]
    hl_html = ""
    if cl.get("highlights"):
        hl_items = "".join(f"<li>{_esc(h)}</li>" for h in cl["highlights"])
        hl_html = f'<ul class="highlights">{hl_items}</ul>'
    disc_html = f'<div class="notice-box">{_esc(cl["disclosure_note"])}</div>' if cl.get("disclosure_note") else ""

    cl_html = (
        cl_tpl.replace("{{ACCENT_COLOR}}", _esc(accent))
        .replace("{{DARK_COLOR}}", _esc(dark))
        .replace("{{FULL_NAME}}", _esc(cand["full_name"]))
        .replace("{{HEADLINE}}", _esc(spec["cv"]["headline"]))
        .replace("{{CONTACT_LINE}}", contact_line)
        .replace("{{DATE_LINE}}", _esc(cl["date_line"]))
        .replace("{{RECIPIENT_BLOCK}}", _esc(cl["recipient"]).replace("\n", "<br>"))
        .replace("{{SUBJECT_LINE}}", _esc(cl["subject_line"]))
        .replace("{{SALUTATION}}", _esc(cl.get("salutation", "Dear Hiring Team,")))
        .replace("{{OPENING_PARAGRAPH}}", _esc(cl["opening_paragraph"]))
        .replace("{{ALIGNMENT_PARAGRAPH}}", _esc(cl["alignment_paragraph"]))
        .replace("{{HIGHLIGHTS_HTML}}", hl_html)
        .replace("{{TRANSFERABLE_OR_CLOSING_PARAGRAPH}}", _esc(cl["closing_paragraph"]))
        .replace("{{DISCLOSURE_HTML}}", disc_html)
        .replace("{{SHORT_CONTACT}}", short_contact)
    )
    return cv_html, cl_html


def audit_pdf(pdf_path: Path, expected_pages: int, max_y_bottom: float = 785.0, forbidden_tokens: list[str] | None = None) -> dict:
    import fitz
    doc = fitz.open(str(pdf_path))
    pages = len(doc)
    y_max = 0.0
    full_text = []
    for page in doc:
        full_text.append(page.get_text("text"))
        for b in page.get_text("blocks"):
            y_max = max(y_max, float(b[3]))
    text_blob = "\n".join(full_text)
    errors = []
    if pages != expected_pages:
        errors.append(f"Expected {expected_pages} page(s), got {pages}")
    if y_max > max_y_bottom:
        errors.append(f"Bottom text y={y_max:.1f}pt exceeds safe threshold {max_y_bottom}pt (footer collision risk)")
    if "{{" in text_blob or "}}" in text_blob:
        errors.append("Unresolved template braces '{{' or '}}' found in rendered PDF")
    for tok in (forbidden_tokens or []):
        if re.search(rf"\b{re.escape(tok)}\b", text_blob, re.IGNORECASE):
            errors.append(f"Forbidden/unverified token detected: {tok!r}")
    return {"file": str(pdf_path), "pages": pages, "y_bottom": round(y_max, 2), "errors": errors}


def render_pack(spec: dict, out_dir: Path, max_y_bottom: float = 785.0) -> dict:
    try:
        import weasyprint
        import fitz
    except ImportError as exc:
        raise RuntimeError("Install 'weasyprint' and 'pymupdf' to render and audit PDFs.") from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    cv_html, cl_html = render_html_from_spec(spec)
    slug = spec["output_slug"]

    cv_pdf = out_dir / f"CV_{slug}.pdf"
    cl_pdf = out_dir / f"Cover_Letter_{slug}.pdf"
    pack_pdf = out_dir / f"Application_Pack_{slug}.pdf"

    weasyprint.HTML(string=cv_html).write_pdf(str(cv_pdf))
    weasyprint.HTML(string=cl_html).write_pdf(str(cl_pdf))

    merged = fitz.open()
    merged.insert_pdf(fitz.open(str(cl_pdf)))
    merged.insert_pdf(fitz.open(str(cv_pdf)))
    merged.save(str(pack_pdf))
    merged.close()

    forbidden = spec.get("audit_forbidden_tokens", [])
    audits = [
        audit_pdf(cv_pdf, 1, max_y_bottom=max_y_bottom, forbidden_tokens=forbidden),
        audit_pdf(cl_pdf, 1, max_y_bottom=max_y_bottom, forbidden_tokens=forbidden),
        audit_pdf(pack_pdf, 2, max_y_bottom=max_y_bottom, forbidden_tokens=forbidden),
    ]
    all_errors = [e for a in audits for e in a["errors"]]
    return {"files": [str(cv_pdf), str(cl_pdf), str(pack_pdf)], "audits": audits, "passed": len(all_errors) == 0}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render & audit JOBINTEL PDF Application Pack")
    parser.add_argument("--spec", required=True, help="JSON pack spec path")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    parser.add_argument("--max-y", type=float, default=785.0, help="Max safe bottom coordinate in pt (A4=841.89pt)")
    args = parser.parse_args()

    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise ValueError("pack spec must be a JSON object")
        report = render_pack(spec, Path(args.out_dir), max_y_bottom=args.max_y)
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError, ImportError, KeyError) as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
