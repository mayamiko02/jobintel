#!/usr/bin/env python3
"""Build a new 3-tab Excel (.xlsx) JOBINTEL application tracker from a payload.

This script only creates a workbook. It does not read, merge into or update an
existing tracker; merging is a separate, agent-driven step (see engines/06).
"""

import argparse
import json
import sys
from pathlib import Path

STATUS_OPTIONS = ["Not Applied", "Applied", "Assessment", "Interview", "Rejected", "Offer"]


def build_xlsx(payload: dict, out_path: Path) -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.datavalidation import DataValidation
    except ImportError as exc:
        raise RuntimeError("Install 'openpyxl' to build Excel trackers.") from exc

    wb = Workbook()
    ws = wb.active
    ws.title = "Vacancy Tracker"

    # The 11 required columns come first and in a fixed order; extras follow.
    headers = [
        "Company",
        "Job Title",
        "Industry/Category",
        "Location/Province",
        "Employment Type",
        "Experience Level",
        "Application Link / Email",
        "Deadline",
        "Date Posted",
        "Source",
        "Status",
        "Fit Tier",
        "Match Summary",
        "Availability",
        "Next Action / Notes",
    ]

    hdr_fill = PatternFill("solid", fgColor="1F3A52")
    hdr_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    body_font = Font(name="Calibri", size=10, color="1E242B")
    alt_fill = PatternFill("solid", fgColor="F5F8FB")

    fit_fills = {
        "Strong Fit": PatternFill("solid", fgColor="E3F2E8"),
        "Possible Fit": PatternFill("solid", fgColor="FFF4DF"),
        "Stretch": PatternFill("solid", fgColor="FCE8E8"),
    }

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = hdr_fill
        cell.font = hdr_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 28

    rows = payload.get("vacancies", [])
    for r_offset, item in enumerate(rows, start=2):
        vals = [
            item.get("company", ""),
            item.get("job_title", ""),
            item.get("category", ""),
            item.get("location", ""),
            item.get("employment_type", ""),
            item.get("experience_level", ""),
            item.get("application_link_or_email", ""),
            item.get("deadline", "Not specified"),
            item.get("date_posted", "Not specified"),
            item.get("source", ""),
            item.get("status", "Not Applied") or "Not Applied",
            item.get("fit_tier", ""),
            item.get("match_summary", ""),
            item.get("availability_status", "Not specified"),
            item.get("notes", ""),
        ]
        for c_idx, val in enumerate(vals, start=1):
            c = ws.cell(row=r_offset, column=c_idx, value=val)
            c.font = body_font
            c.alignment = Alignment(vertical="top", wrap_text=True)
            if r_offset % 2 == 1:
                c.fill = alt_fill
        fit_cell = ws.cell(row=r_offset, column=12)
        if fit_cell.value in fit_fills:
            fit_cell.fill = fit_fills[fit_cell.value]
        ws.row_dimensions[r_offset].height = 38

    widths = [24, 28, 22, 20, 15, 16, 34, 16, 15, 18, 15, 13, 40, 15, 36]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A2"
    last_row = max(len(rows) + 1, 2)
    ws.auto_filter.ref = f"A1:O{last_row}"

    dv = DataValidation(type="list", formula1=f'"{",".join(STATUS_OPTIONS)}"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(f"K2:K{max(last_row + 25, 100)}")

    # Tab 2: Summary & Breakdown
    ws2 = wb.create_sheet("Search Summary & Breakdown")
    ws2["A1"] = payload.get("tracker_title", "JOBINTEL Search Summary")
    ws2["A1"].font = Font(name="Calibri", size=14, bold=True, color="1F3A52")
    ws2["A3"] = "Fit Tier"
    ws2["B3"] = "Count"
    for c in (ws2["A3"], ws2["B3"]):
        c.fill = hdr_fill
        c.font = hdr_font

    for idx, tier in enumerate(["Strong Fit", "Possible Fit", "Stretch"], start=4):
        ws2.cell(row=idx, column=1, value=tier)
        ws2.cell(row=idx, column=2, value=f'=COUNTIF(\'Vacancy Tracker\'!L2:L{max(last_row, 2)},"{tier}")')

    ws2["A8"] = "Status"
    ws2["B8"] = "Count"
    for c in (ws2["A8"], ws2["B8"]):
        c.fill = hdr_fill
        c.font = hdr_font
    for idx, st in enumerate(STATUS_OPTIONS, start=9):
        ws2.cell(row=idx, column=1, value=st)
        ws2.cell(row=idx, column=2, value=f'=COUNTIF(\'Vacancy Tracker\'!K2:K{max(last_row, 2)},"{st}")')

    ws2.column_dimensions["A"].width = 30
    ws2.column_dimensions["B"].width = 16

    # Tab 3: Excluded & Audit Log
    ws3 = wb.create_sheet("Excluded & Audit Log")
    ex_headers = ["Company", "Job Title", "Exclusion Reason", "Source / URL"]
    for col_idx, h in enumerate(ex_headers, start=1):
        c = ws3.cell(row=1, column=col_idx, value=h)
        c.fill = hdr_fill
        c.font = hdr_font
    for r_idx, ex in enumerate(payload.get("excluded_log", []), start=2):
        ws3.cell(row=r_idx, column=1, value=ex.get("company", ""))
        ws3.cell(row=r_idx, column=2, value=ex.get("job_title", ""))
        ws3.cell(row=r_idx, column=3, value=ex.get("reason", ""))
        ws3.cell(row=r_idx, column=4, value=ex.get("source_url", ""))
    for i, w in enumerate([26, 30, 48, 42], start=1):
        ws3.column_dimensions[get_column_letter(i)].width = w
    ws3.freeze_panes = "A2"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out_path))
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build 3-tab JOBINTEL Excel (.xlsx) tracker")
    parser.add_argument("--input", required=True, help="Tracker payload JSON")
    parser.add_argument("--out", required=True, help="Output .xlsx path")
    args = parser.parse_args()

    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("tracker payload must be a JSON object")
        saved = build_xlsx(payload, Path(args.out))
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Saved tracker: {saved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
