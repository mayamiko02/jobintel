#!/usr/bin/env python3
"""Generate transparent, CV-driven SearchStrategy JSON from a confirmed CandidateProfile + MarketPack."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SENIORITY_TITLE_MODIFIERS = {
    "intern_graduate": ["Intern", "Graduate Trainee", "Trainee"],
    "entry_junior": ["Junior", "Assistant", "Trainee"],
    "assistant_associate": ["Assistant", "Associate", "Officer"],
    "officer_specialist": ["Officer", "Specialist", "Coordinator"],
    "mid_level": ["Officer", "Coordinator", "Specialist", "Analyst"],
    "senior_lead": ["Senior", "Lead", "Principal"],
    "manager": ["Manager", "Head"],
    "executive_director": ["Director", "Chief"],
}

LEVEL_LABELS = {
    "intern_graduate": "Intern",
    "entry_junior": "Junior",
    "assistant_associate": "Assistant",
    "officer_specialist": "Officer",
    "mid_level": "Mid-level",
    "senior_lead": "Senior",
    "manager": "Manager",
    "executive_director": "Director",
}


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        clean = item.strip()
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            out.append(clean)
    return out


def build_search_strategy(profile: dict, market: dict) -> dict:
    if profile.get("profile_status") != "confirmed":
        raise ValueError("Gate 1 violation: CandidateProfile must have profile_status='confirmed' before strategy generation.")

    domains = profile.get("professional_positioning", {}).get("primary_domains", [])
    work_titles = [w.get("role_title", "") for w in profile.get("work_experience", []) if w.get("role_title")]
    explicit_skills = profile.get("skills", {}).get("explicit_skills", [])
    tools = [t.get("name", "") for t in profile.get("skills", {}).get("tools_and_systems", []) if t.get("name")]
    inferred = [i.get("skill", "") for i in profile.get("skills", {}).get("inferred_transferable_skills", []) if i.get("skill")]
    regs = [r.get("body_name", "") for r in profile.get("education_and_credentials", {}).get("professional_registrations", []) if r.get("status") in {"active", "in_progress"}]

    rec_levels = profile.get("seniority", {}).get("recommended_levels", ["entry_junior", "officer_specialist"])
    excl_levels = profile.get("seniority", {}).get("excluded_levels", [])

    # Cluster skills dynamically by emergent CV clusters (never fixed occupation list)
    clusters_map: dict[str, list[str]] = {}
    for sk in explicit_skills:
        cname = sk.get("cluster", "Core Domain")
        clusters_map.setdefault(cname, []).append(sk.get("name", ""))
    if not clusters_map:
        for dom in domains or ["Primary Role"]:
            clusters_map[dom] = []

    title_clusters = []
    for cname, cskills in clusters_map.items():
        matching_work = [t for t in work_titles if any(tok.lower() in t.lower() for tok in cname.split())] or work_titles[:2]
        modifiers = _dedupe_keep_order([m for lvl in rec_levels for m in SENIORITY_TITLE_MODIFIERS.get(lvl, [])])[:3]
        primary = _dedupe_keep_order(matching_work + [f"{cname} {mod}".strip() for mod in modifiers[:2]])[:5]
        alternatives = _dedupe_keep_order([f"{cname} {m}" for m in modifiers[1:] + ["Coordinator", "Specialist"]])[:4]
        adjacent = _dedupe_keep_order([p.get("track_name", "") for p in profile.get("adjacent_career_paths", [])])[:4]
        rationale = f"Derived from CV domain cluster '{cname}' backed by skills ({', '.join(cskills[:4]) or 'verified roles'}) and seniority levels ({', '.join(rec_levels)})."
        title_clusters.append({
            "cluster_name": cname,
            "primary_titles": primary,
            "alternative_titles": alternatives,
            "adjacent_titles": adjacent,
            "cv_evidence_rationale": rationale,
        })

    # Location tiers derived from candidate preferences + MarketPack
    prefs = profile.get("preferences", {})
    pref_locs = [p.lower() for p in prefs.get("priority_locations", [])]
    reloc = prefs.get("relocation_openness", "unknown")
    location_tiers = []
    for reg in market.get("priority_regions", []):
        tier_num = reg.get("tier", 1)
        aliases = reg.get("cities_and_aliases", [])
        if reloc == "home_city_only" and pref_locs:
            kept = [c for c in aliases if c.lower() in pref_locs or any(p in c.lower() for p in pref_locs)]
            if not kept:
                continue
            locs = kept
        else:
            locs = aliases[:6]
        location_tiers.append({
            "tier": tier_num,
            "locations": locs,
            "rationale": f"{market.get('market_name')} Tier {tier_num} ({reg.get('name')}) aligned with relocation='{reloc}'."
        })
    if not location_tiers and prefs.get("priority_locations"):
        location_tiers.append({
            "tier": 1,
            "locations": prefs["priority_locations"],
            "rationale": "Candidate-specified priority locations."
        })

    # Exclusions & Boolean queries
    exclusions = [f"-{LEVEL_LABELS[lvl]}" for lvl in excl_levels if lvl in LEVEL_LABELS]
    for sh in prefs.get("excluded_shift_or_industries", []):
        exclusions.append(f"-{sh}")
    excl_clause = " ".join(exclusions[:4])

    top_cities = location_tiers[0]["locations"][:3] if location_tiers else [profile.get("identity", {}).get("location", {}).get("city", "")]
    loc_or = " OR ".join(f'"{c}"' for c in top_cities if c)

    core_kw = _dedupe_keep_order([s.get("name", "") for s in explicit_skills])[:10]
    tool_stat_kw = _dedupe_keep_order(tools + regs)[:8]
    transf_kw = _dedupe_keep_order(inferred)[:8]

    boolean_queries = []
    for idx, cl in enumerate(title_clusters, start=1):
        titles_or = " OR ".join(f'"{t}"' for t in (cl["primary_titles"][:3] + cl["alternative_titles"][:2]))
        kw_or = " OR ".join(f'"{k}"' for k in (core_kw[:3] + tool_stat_kw[:2]))
        q_str = f"({titles_or})"
        if loc_or:
            q_str += f" ({loc_or})"
        if kw_or:
            q_str += f" ({kw_or})"
        if excl_clause:
            q_str += f" {excl_clause}"
        boolean_queries.append({
            "query_id": f"Q{idx:02d}_{cl['cluster_name'].lower().replace(' ', '_')[:20]}",
            "intent": f"Core + alternative title discovery for {cl['cluster_name']}",
            "boolean_string": q_str.strip(),
            "target_scope": f"{market.get('market_name')} Tier 1-2",
            "portal_domain_hint": None,
        })

    # Portal-specific queries for top 3 portals in MarketPack
    all_primary_titles = _dedupe_keep_order([t for c in title_clusters for t in c["primary_titles"][:2]])[:4]
    if all_primary_titles:
        p_titles_or = " OR ".join(f'"{t}"' for t in all_primary_titles)
        for p_idx, portal in enumerate(market.get("portals", [])[:3], start=1):
            dom = portal.get("domain", "")
            boolean_queries.append({
                "query_id": f"P{p_idx:02d}_{dom.split('.')[0]}",
                "intent": f"Direct scan on {portal.get('name')} ({portal.get('category')})",
                "boolean_string": f"site:{dom} ({p_titles_or}) ({loc_or or market.get('market_name')})".strip(),
                "target_scope": portal.get("name"),
                "portal_domain_hint": dom,
            })

    # Remote query if candidate is open to remote
    remote_pref = prefs.get("remote_preference", "unknown")
    if remote_pref in {"remote_local_hours", "remote_any_timezone", "flexible"} and all_primary_titles:
        country = profile.get("identity", {}).get("location", {}).get("country_name") or market.get("market_name", "")
        r_titles_or = " OR ".join(f'"{t}"' for t in all_primary_titles[:3])
        boolean_queries.append({
            "query_id": "R01_remote_eligible",
            "intent": "Remote roles explicitly eligible for candidate's country/region",
            "boolean_string": f"({r_titles_or}) \"Remote\" (\"{country}\" OR \"Africa\" OR \"EMEA\" OR \"Worldwide\") -\"US only\" -\"EU only\"",
            "target_scope": "Remote Africa / EMEA / Global Eligible",
            "portal_domain_hint": None,
        })

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_id": market.get("market_id", "UNKNOWN"),
        "candidate_profile_ref": profile.get("profile_id", profile.get("identity", {}).get("full_name", "candidate")),
        "target_seniority_bands": rec_levels,
        "title_clusters": title_clusters,
        "industry_categories": _dedupe_keep_order(domains + [c["cluster_name"] for c in title_clusters]),
        "keyword_sets": {
            "core_domain_keywords": core_kw,
            "tools_and_cert_keywords": tool_stat_kw,
            "transferable_keywords": transf_kw,
        },
        "boolean_queries": boolean_queries,
        "location_tiers": location_tiers,
        "source_channels": [f"{p['name']} ({p['domain']})" for p in market.get("portals", [])],
        "exclusion_filters": exclusions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate transparent JOBINTEL SearchStrategy JSON")
    parser.add_argument("profile_json", help="Confirmed CandidateProfile JSON path")
    parser.add_argument("market_json", help="Target MarketPack JSON path")
    parser.add_argument("--out", help="Optional output file path")
    args = parser.parse_args()

    try:
        profile = json.loads(Path(args.profile_json).read_text(encoding="utf-8"))
        market = json.loads(Path(args.market_json).read_text(encoding="utf-8"))
        if not isinstance(profile, dict) or not isinstance(market, dict):
            raise ValueError("profile and market must both be JSON objects")
        strategy = build_search_strategy(profile, market)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(strategy, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
