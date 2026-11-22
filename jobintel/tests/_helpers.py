import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def vac(company="Acme Limited", title="Marketing Officer", city="Lusaka", ref=None, **extra):
    v = {
        "company": company,
        "job_title": title,
        "location": {"city_or_duty_station": city},
        "vacancy_ref": ref,
        "source": "board-a",
        "source_url": "https://a.example/1",
        "application_link_or_email": "https://a.example/apply",
        "verification_status": "verified_full_ad",
        "deadline_iso": "2026-12-05",
    }
    v.update(extra)
    return v
