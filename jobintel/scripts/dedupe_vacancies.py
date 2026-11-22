#!/usr/bin/env python3
"""Vacancy de-duplication, expiry checking and availability audit.

Duplicate rules (pairwise, never by URL):

1. If BOTH records carry a vacancy reference number, they are duplicates only if
   the normalised references are equal AND the normalised employers match.
   Different references on both sides => different vacancies, even when the
   employer and title are identical (employers often run parallel postings).
2. If either record has no reference, fall back to normalised
   employer + title + location. An empty location on either side is treated as
   unknown and does not block a match.
3. Source URL, source name and punctuation never decide anything.

Availability (see engines/03_vacancy_discovery.md) is derived here only from
what the record already states; the script never fetches pages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

AVAILABILITY_STATES = ("verified_open", "likely_open", "uncertain", "expired", "removed")
OPEN_STATES = {"verified_open", "likely_open"}

LEGAL_SUFFIX_RE = re.compile(
    r"\b(limited|ltd|plc|inc|incorporated|corp|corporation|llc|co|company|"
    r"zambia|zambian|kenya|nigeria|ghana|group|the)\b",
    re.IGNORECASE,
)
PAREN_RE = re.compile(r"\([^)]*\)")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _squash(text: str) -> str:
    return NON_ALNUM_RE.sub(" ", text.lower()).strip()


def normalize_company(name: str | None) -> str:
    text = PAREN_RE.sub(" ", name or "")
    text = text.replace("&", " and ")
    text = LEGAL_SUFFIX_RE.sub(" ", text)
    return _squash(text)


def normalize_title(title: str | None) -> str:
    # Drop trailing location hints such as "Sales Officer - Lusaka" or "(Ndola)".
    base = re.split(r"\s+[-–—|]\s+|\(", title or "")[0]
    return _squash(base.replace("&", " and "))


def normalize_location(loc: str | None) -> str:
    # "Lusaka, Lusaka Province" -> "lusaka"
    first = re.split(r"[,/;]", loc or "")[0]
    first = re.sub(r"\b(province|region|city|district|town)\b", " ", first, flags=re.IGNORECASE)
    return _squash(first)


def normalize_ref(ref: str | None) -> str:
    """Reference numbers: case, spaces, dashes, slashes and dots are ignored."""
    return re.sub(r"[^a-z0-9]", "", (ref or "").lower())


def compute_dedupe_key(company: str, title: str, city: str, vacancy_ref: str | None = None) -> str:
    """Stable fingerprint for storage. Matching itself uses is_duplicate()."""
    ref = normalize_ref(vacancy_ref)
    if ref:
        raw = f"ref|{normalize_company(company)}|{ref}"
    else:
        raw = f"fb|{normalize_company(company)}|{normalize_title(title)}|{normalize_location(city)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _fields(v: dict) -> tuple[str, str, str, str]:
    loc = v.get("location") or {}
    city = loc.get("city_or_duty_station", "") if isinstance(loc, dict) else str(loc)
    return (
        normalize_company(v.get("company")),
        normalize_title(v.get("job_title")),
        normalize_location(city),
        normalize_ref(v.get("vacancy_ref")),
    )


def is_duplicate(a: dict, b: dict) -> bool:
    ca, ta, la, ra = _fields(a)
    cb, tb, lb, rb = _fields(b)
    if not ca or not cb or ca != cb:
        return False
    if ra and rb:
        return ra == rb
    if ta != tb:
        return False
    if la and lb and la != lb:
        return False
    return True


def _score(v: dict) -> tuple:
    """Higher is better when choosing which duplicate to keep."""
    avail_rank = {"verified_open": 3, "likely_open": 2, "uncertain": 1}.get(v.get("availability_status"), 0)
    full = 1 if v.get("verification_status") == "verified_full_ad" else 0
    link = v.get("application_link_or_email", "") or ""
    official = 1 if ("@" in link or v.get("is_official_source")) else 0
    has_ref = 1 if normalize_ref(v.get("vacancy_ref")) else 0
    return (full, avail_rank, official, has_ref)


def derive_availability(v: dict, today: date, recency_days: int = 30) -> tuple[str, str]:
    """Return (state, reason). Honours an explicit availability_status if present
    and consistent; otherwise derives one from the record. Never invents evidence."""
    explicit = v.get("availability_status")
    d_iso = v.get("deadline_iso")
    if d_iso:
        try:
            if date.fromisoformat(str(d_iso)[:10]) < today:
                return "expired", f"deadline {d_iso} is before {today.isoformat()}"
        except ValueError:
            return "uncertain", f"unparseable deadline_iso {d_iso!r}"
    if explicit in ("expired", "removed"):
        return explicit, v.get("verification_notes") or f"marked {explicit}"
    if str(v.get("verification_status", "")).startswith("excluded_"):
        return "expired" if v["verification_status"] == "excluded_expired" else "uncertain", (
            v.get("verification_notes") or v["verification_status"]
        )
    if v.get("is_currently_open") is False:
        return "uncertain", v.get("verification_notes") or "is_currently_open=false"
    if explicit in AVAILABILITY_STATES:
        # A "verified_open" claim needs a full-page check and a deadline.
        if explicit == "verified_open" and (v.get("verification_status") != "verified_full_ad" or not d_iso):
            return "likely_open" if v.get("verification_status") == "verified_full_ad" else "uncertain", (
                "downgraded: verified_open requires verified_full_ad and a future deadline_iso"
            )
        return explicit, v.get("verification_notes", "")
    if d_iso and v.get("verification_status") == "verified_full_ad":
        return "verified_open", "full ad, deadline in the future"
    if d_iso:
        return "likely_open", "deadline in the future but not verified from the full ad"
    posted = v.get("date_posted")
    if posted and v.get("verification_status") == "verified_full_ad":
        try:
            age = (today - date.fromisoformat(str(posted)[:10])).days
            if 0 <= age <= recency_days:
                return "likely_open", f"no deadline; posted {age} days ago"
        except ValueError:
            pass
    return "uncertain", "no deadline and no recent verified posting date"


def audit_and_dedupe(vacancies: list[dict], today_iso: str, market: dict | None = None) -> dict:
    if not isinstance(vacancies, list):
        raise TypeError("vacancies must be a list of records")
    try:
        today = date.fromisoformat(today_iso)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"today must be YYYY-MM-DD, got {today_iso!r}") from exc

    kept: list[dict] = []
    excluded: list[dict] = []

    for v in vacancies:
        if not isinstance(v, dict):
            raise TypeError("each vacancy must be an object")
        company = v.get("company", "")
        title = v.get("job_title", "")
        loc = v.get("location") or {}
        city = loc.get("city_or_duty_station", "") if isinstance(loc, dict) else str(loc)
        v["dedupe_key"] = compute_dedupe_key(company, title, city, v.get("vacancy_ref"))

        state, reason = derive_availability(v, today)
        v["availability_status"] = state
        v["is_currently_open"] = state in OPEN_STATES

        if state not in OPEN_STATES:
            excluded.append({
                "company": company,
                "job_title": title,
                "availability_status": state,
                "reason": f"{state}: {reason}",
                "source_url": v.get("source_url", ""),
            })
            continue

        match_idx = next((i for i, k in enumerate(kept) if is_duplicate(k, v)), None)
        if match_idx is None:
            kept.append(v)
            continue
        existing = kept[match_idx]
        if _score(v) > _score(existing):
            excluded.append({
                "company": existing.get("company", ""),
                "job_title": existing.get("job_title", ""),
                "availability_status": existing.get("availability_status"),
                "reason": f"Duplicate of higher-confidence listing ({v.get('source', '')})",
                "source_url": existing.get("source_url", ""),
            })
            kept[match_idx] = v
        else:
            excluded.append({
                "company": company,
                "job_title": title,
                "availability_status": state,
                "reason": f"Duplicate of existing listing ({existing.get('source', '')})",
                "source_url": v.get("source_url", ""),
            })

    return {
        "today": today_iso,
        "market_id": market.get("market_id") if market else None,
        "active_count": len(kept),
        "excluded_count": len(excluded),
        "active_vacancies": kept,
        "excluded_log": excluded,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate and availability-audit JOBINTEL vacancies")
    parser.add_argument("vacancies_json", help="Path to JSON array of vacancy records")
    parser.add_argument("--market", help="Optional MarketPack JSON path")
    parser.add_argument("--today", default=date.today().isoformat(), help="Current local date YYYY-MM-DD")
    parser.add_argument("--out", help="Output JSON path")
    args = parser.parse_args()

    try:
        vacancies = json.loads(Path(args.vacancies_json).read_text(encoding="utf-8"))
        market = json.loads(Path(args.market).read_text(encoding="utf-8")) if args.market else None
        result = audit_and_dedupe(vacancies, args.today, market)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
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
