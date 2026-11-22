"""Repository privacy guard: no candidate files, no personal contact details, and a .gitignore that actually works."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _helpers import ROOT

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}
FORBIDDEN_SUFFIXES = {".pdf", ".docx", ".doc", ".odt", ".rtf", ".xlsx", ".xls", ".csv", ".jpg", ".jpeg", ".png", ".zip"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
ALLOWED_EMAIL_DOMAINS = re.compile(r"(example|invalid|test|localhost|acme)", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(\+?260|0)?\s?9[5-7]\d[\s-]?\d{3}[\s-]?\d{3}(?!\d)")


def repo_files():
    for p in ROOT.rglob("*"):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS):
            yield p


class TestRepoHygiene(unittest.TestCase):
    def test_no_candidate_document_formats_committed(self):
        bad = [str(p.relative_to(ROOT)) for p in repo_files() if p.suffix.lower() in FORBIDDEN_SUFFIXES]
        self.assertEqual(bad, [], "candidate-like files present: " + ", ".join(bad))

    def test_only_fictional_emails_present(self):
        offenders = []
        for p in repo_files():
            if p.suffix.lower() not in {".json", ".md", ".py", ".html", ".txt"}:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
            for m in EMAIL_RE.finditer(text):
                domain = m.group(1)
                if not ALLOWED_EMAIL_DOMAINS.search(domain) and domain not in {"noreply.github.com"}:
                    offenders.append(f"{p.relative_to(ROOT)}: {m.group(0)}")
        self.assertEqual(offenders, [], offenders)

    def test_no_real_looking_phone_numbers_outside_marked_fictional_fixtures(self):
        offenders = []
        for p in repo_files():
            if p.suffix.lower() not in {".json", ".md", ".py", ".html"}:
                continue
            for m in PHONE_RE.finditer(p.read_text(encoding="utf-8", errors="ignore")):
                ctx = m.group(0)
                # +260 970 000 xxx style placeholders are fictional; anything else is flagged.
                if not re.search(r"0{3}", ctx):
                    offenders.append(f"{p.relative_to(ROOT)}: {ctx}")
        self.assertEqual(offenders, [], offenders)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_gitignore_blocks_private_files_and_allows_project_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shutil.copy(ROOT / ".gitignore", tmp_path / ".gitignore")
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            private = [
                "My_CV.pdf", "cv.docx", "resume.rtf", "Jane Doe CV.odt", "cover_letter_acme.docx",
                "certificate.pdf", "transcript.png", "scan.jpg", "Job_Hunt_2027.xlsx", "tracker.csv",
                "my_tracker.ods", "jane_profile.json", "profile_jane.json", "tracker_payload.json",
                "pack_spec.json", "cv_extracted.json", "Application_Pack_X_Y.pdf", "vacancies_raw.json",
                "uploads/a.txt", "cvs/b.txt", "resumes/c.md", "candidates/d.json", "profiles/e.json",
                "trackers/f.xlsx", "applications/g.docx", "output/h.pdf", ".env", "credentials.json",
                "archive.zip",
            ]
            for rel in private:
                f = tmp_path / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("x")
            allowed = [
                "SKILL.md", "README.md", "LICENSE", "CHANGELOG.md", "engines/01_cv_analysis.md",
                "engines/06_tracker_sync.md", "scripts/extract_cv_text.py", "scripts/build_tracker.py",
                "scripts/requirements.txt", "schemas/candidate_profile.schema.json",
                "templates/cv_template.html", "templates/cover_letter_template.html",
                "examples/nurse_lusaka_profile.json", "examples/README.md", "markets/zambia.json",
                "docs/INSTALL.md", "tests/test_dedupe.py", "tests/fixtures/sample.json",
            ]
            for rel in allowed:
                f = tmp_path / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("x")
            subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
            tracked = set(subprocess.run(["git", "ls-files"], cwd=tmp, capture_output=True, text=True, check=True).stdout.splitlines())
            leaked = [p for p in private if p in tracked]
            blocked = [p for p in allowed if p not in tracked]
            self.assertEqual(leaked, [], f"gitignore failed to block: {leaked}")
            self.assertEqual(blocked, [], f"gitignore wrongly blocks project files: {blocked}")

    def test_every_real_repo_file_would_be_tracked(self):
        if not shutil.which("git"):
            self.skipTest("git not installed")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for p in repo_files():
                rel = p.relative_to(ROOT)
                (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(p, tmp_path / rel)
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
            tracked = set(subprocess.run(["git", "ls-files"], cwd=tmp, capture_output=True, text=True, check=True).stdout.splitlines())
            expected = {str(p.relative_to(ROOT)) for p in repo_files()}
            self.assertEqual(sorted(expected - tracked), [], "legitimate files are ignored by .gitignore")


if __name__ == "__main__":
    unittest.main()
