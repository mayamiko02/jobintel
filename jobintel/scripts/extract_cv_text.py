#!/usr/bin/env python3
"""Extract text, links, and scan status from candidate CV/certificate files (PDF, DOCX, TXT/MD)."""

import argparse
import json
import re
import sys
from pathlib import Path

URL_RE = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def extract_pdf(path: Path) -> dict:
    pages = []
    urls = set()
    try:
        import fitz  # pymupdf
        doc = fitz.open(str(path))
        for i, page in enumerate(doc):
            txt = page.get_text("text") or ""
            pages.append({"page": i + 1, "text": txt.strip()})
            for link in page.get_links():
                if link.get("uri"):
                    urls.add(link["uri"])
    except ImportError:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            for i, page in enumerate(reader.pages):
                txt = page.extract_text() or ""
                pages.append({"page": i + 1, "text": txt.strip()})
                annots = page.get("/Annots") or []
                for a in annots:
                    obj = a.get_object()
                    if "/A" in obj and "/URI" in obj["/A"]:
                        urls.add(str(obj["/A"]["/URI"]))
        except ImportError as exc:
            raise RuntimeError("Install 'pymupdf' or 'pypdf' to parse PDF files (pip install -r scripts/requirements.txt).") from exc

    full_text = "\n\n".join(p["text"] for p in pages if p["text"]).strip()
    for m in URL_RE.findall(full_text):
        urls.add(m.rstrip(".,;"))
    needs_ocr = len(full_text) < 80
    return {
        "file_path": str(path),
        "file_type": "pdf",
        "page_count": len(pages),
        "char_count": len(full_text),
        "needs_ocr": needs_ocr,
        "extracted_urls": sorted(urls),
        "extracted_emails": sorted(set(EMAIL_RE.findall(full_text))),
        "raw_text": full_text,
    }


def extract_docx(path: Path) -> dict:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Install 'python-docx' to parse DOCX files.") from exc
    doc = Document(str(path))
    chunks = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            row_txt = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_txt:
                chunks.append(row_txt)
    full_text = "\n".join(chunks)
    return {
        "file_path": str(path),
        "file_type": "docx",
        "page_count": None,
        "char_count": len(full_text),
        "needs_ocr": len(full_text) < 50,
        "extracted_urls": sorted(set(m.rstrip(".,;") for m in URL_RE.findall(full_text))),
        "extracted_emails": sorted(set(EMAIL_RE.findall(full_text))),
        "raw_text": full_text,
    }


def extract_text_file(path: Path) -> dict:
    full_text = path.read_text(encoding="utf-8", errors="replace").strip()
    return {
        "file_path": str(path),
        "file_type": path.suffix.lstrip(".").lower() or "txt",
        "page_count": 1,
        "char_count": len(full_text),
        "needs_ocr": False,
        "extracted_urls": sorted(set(m.rstrip(".,;") for m in URL_RE.findall(full_text))),
        "extracted_emails": sorted(set(EMAIL_RE.findall(full_text))),
        "raw_text": full_text,
    }


def extract_file(path: Path) -> dict:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    if ext == ".docx":
        return extract_docx(path)
    if ext in {".txt", ".md", ".json"}:
        return extract_text_file(path)
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        return {
            "file_path": str(path),
            "file_type": ext.lstrip("."),
            "page_count": 1,
            "char_count": 0,
            "needs_ocr": True,
            "extracted_urls": [],
            "extracted_emails": [],
            "raw_text": "",
        }
    raise ValueError(f"Unsupported CV/document extension: {ext}")


def main() -> int:
    parser = argparse.ArgumentParser(description="JOBINTEL CV/Certificate text and link extractor")
    parser.add_argument("input_path", help="Path to CV or certificate file (.pdf, .docx, .txt, .md)")
    parser.add_argument("--out", help="Optional path to save JSON output")
    args = parser.parse_args()

    try:
        result = extract_file(Path(args.input_path))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
