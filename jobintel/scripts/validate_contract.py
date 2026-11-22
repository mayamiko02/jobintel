#!/usr/bin/env python3
"""Validate JOBINTEL JSON artifacts against schemas and Gate readiness rules."""

import argparse
import json
import sys
from pathlib import Path

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"

SCHEMA_MAP = {
    "profile": "candidate_profile.schema.json",
    "market": "market_pack.schema.json",
    "strategy": "search_strategy.schema.json",
    "vacancy": "vacancy.schema.json",
    "match": "match_result.schema.json",
}


_PY_TYPES = {
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
    "null": type(None),
    "array": list,
    "object": dict,
}


def _type_ok(value, type_name: str) -> bool:
    if type_name in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _PY_TYPES[type_name])


def _basic_validate(data, schema: dict, path: str = "$") -> list[str]:
    """Dependency-free fallback used only when jsonschema is not installed."""
    errors: list[str] = []
    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        if not any(_type_ok(data, t) for t in expected_type if t in _PY_TYPES):
            return [f"{path}: expected one of {expected_type}, got {type(data).__name__}"]
        expected_type = next((t for t in expected_type if t in _PY_TYPES and _type_ok(data, t)), None)
    elif expected_type in _PY_TYPES and expected_type not in ("object", "array"):
        if not _type_ok(data, expected_type):
            return [f"{path}: expected {expected_type}, got {type(data).__name__}"]
    if expected_type == "object":
        if not isinstance(data, dict):
            return [f"{path}: expected object, got {type(data).__name__}"]
        for req in schema.get("required", []):
            if req not in data:
                errors.append(f"{path}: missing required key '{req}'")
        props = schema.get("properties", {})
        for k, v in data.items():
            if k in props:
                errors.extend(_basic_validate(v, props[k], f"{path}.{k}"))
    elif expected_type == "array":
        if not isinstance(data, list):
            return [f"{path}: expected array, got {type(data).__name__}"]
        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(data):
                errors.extend(_basic_validate(item, item_schema, f"{path}[{idx}]"))
    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: value {data!r} not in allowed enum {schema['enum']}")
    if "const" in schema and data != schema["const"]:
        errors.append(f"{path}: value {data!r} must equal {schema['const']!r}")
    return errors


OPEN_STATES = {"verified_open", "likely_open"}


def validate_artifact(kind: str, data, require_confirmed_gate1: bool = False) -> list[str]:
    if kind not in SCHEMA_MAP:
        return [f"unknown artifact kind {kind!r}; expected one of {sorted(SCHEMA_MAP)}"]
    if not isinstance(data, dict):
        return [f"$: expected a JSON object, got {type(data).__name__}"]
    schema_path = SCHEMAS_DIR / SCHEMA_MAP[kind]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            loc = ".".join(str(p) for p in err.path) or "$"
            errors.append(f"{loc}: {err.message}")
    except ImportError:
        errors.extend(_basic_validate(data, schema))

    if kind == "profile":
        # Ensure strict separation: inferred items must not masquerade as verified work/edu
        if require_confirmed_gate1 and data.get("profile_status") != "confirmed":
            errors.append("Gate 1 blocked: 'profile_status' must be 'confirmed' before running Engine 2 search.")
        unresolved = [a for a in data.get("ambiguities_to_confirm", []) if not a.get("resolved")]
        if require_confirmed_gate1 and unresolved:
            errors.append(
                f"Gate 1 blocked: {len(unresolved)} unresolved ambiguity item(s): "
                + ", ".join(a.get("field", "?") for a in unresolved)
            )
    if kind == "vacancy":
        status = data.get("availability_status")
        if status in OPEN_STATES and data.get("is_currently_open") is False:
            errors.append("Availability inconsistency: is_currently_open=false but availability_status is open.")
        if status not in OPEN_STATES and data.get("is_currently_open") is True:
            errors.append(f"Availability inconsistency: is_currently_open=true but availability_status={status!r}.")
        if status == "verified_open":
            if data.get("verification_status") != "verified_full_ad":
                errors.append("verified_open requires verification_status='verified_full_ad'.")
            if not data.get("deadline_iso"):
                errors.append("verified_open requires a deadline_iso in the future; without a deadline the best state is likely_open.")
        evidence = data.get("availability_evidence")
        if status and not evidence:
            errors.append("availability_status is set but availability_evidence (with checked_at and basis) is missing.")
    if kind == "match":
        # Verify three buckets do not overlap trivially on identical strings
        ver = {x.get("requirement", "").strip().lower() for x in data.get("verified_requirements_met", [])}
        inf = {x.get("requirement", "").strip().lower() for x in data.get("inferred_transferable_skills", [])}
        mis = {x.get("gap", "").strip().lower() for x in data.get("missing_qualifications_and_blockers", [])}
        overlap = (ver & inf) | (ver & mis) | (inf & mis)
        if overlap:
            errors.append(f"Evidence buckets overlap on identical requirements: {sorted(overlap)}")
        hard_blockers = [
            x for x in data.get("missing_qualifications_and_blockers", [])
            if x.get("severity") == "hard_blocker"
        ]
        if hard_blockers and data.get("fit_tier") == "Strong Fit":
            errors.append("Match consistency error: cannot assign 'Strong Fit' when a 'hard_blocker' exists.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate JOBINTEL JSON contract & Gate readiness")
    parser.add_argument("kind", choices=sorted(SCHEMA_MAP.keys()))
    parser.add_argument("json_path", help="Path to JSON file to validate")
    parser.add_argument("--gate1", action="store_true", help="Enforce confirmed Gate 1 check for profile")
    args = parser.parse_args()

    try:
        data = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"ERROR: cannot read {args.json_path}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: {args.json_path} is not valid JSON: {exc}", file=sys.stderr)
        return 2
    errors = validate_artifact(args.kind, data, require_confirmed_gate1=args.gate1)
    if errors:
        print(f"INVALID ({args.kind}): {len(errors)} issue(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"VALID ({args.kind}): passed all contract checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
