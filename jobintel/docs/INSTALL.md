# Installation and usage guide

## 1. What you need

Minimum, to use JOBINTEL as an agent skill:
- An AI agent runner that supports skills defined by a `SKILL.md` file (for example Claude with custom skills enabled). Check your runner's documentation; this package has been written to the open `SKILL.md` convention but has not been tested on every runner.
- For live job search: a web search tool and a page fetch or browser tool supplied by that runner. Without them JOBINTEL stops at the profile, the strategy and a manual search plan.

Optional, for the helper scripts:
- Python 3.10 or newer.
- `pip install -r scripts/requirements.txt` for everything, or only the packages named in `docs/TOOLS.md`.

Optional, for the tracker:
- A spreadsheet connector (for example Google Sheets and Drive) supplied by your runner. Without one you get an `.xlsx` or a table.

## 2. Install

```bash
git clone https://github.com/mayamiko02/jobintel.git
```

Then add the `jobintel` folder (it must contain `SKILL.md`) to your runner's skills location, or upload it as a custom skill, following your runner's instructions.

## 3. First run

1. Give the agent a CV (PDF, DOCX or text) or a profile JSON, and say which country you want.
   Example: "Use JOBINTEL on my CV. I want jobs in Lusaka and the Copperbelt, open to hybrid."
2. Gate 1: review the extracted profile. Correct dates, credentials and skills. Nothing is searched until you confirm.
3. Gate 2: review the generated titles, keywords, Boolean queries and locations, with the reason for each. Add or remove anything.
4. The agent searches and verifies vacancies, then shows ranked matches in three buckets: verified requirements, inferred transferable skills, and missing qualifications.
5. Gate 3: choose which roles you want application documents for.
6. Review drafts and send applications yourself. JOBINTEL never submits or emails on your behalf.

## 4. Using the scripts directly

```bash
python3 -m unittest discover -s tests -v

python3 scripts/validate_contract.py profile examples/nurse_lusaka_profile.json --gate1
python3 scripts/generate_search_queries.py examples/nurse_lusaka_profile.json markets/zambia.json
python3 scripts/dedupe_vacancies.py vacancies_raw.json --market markets/zambia.json --today 2026-11-21 --out vacancies_clean.json
python3 scripts/build_tracker.py --input tracker_payload.json --out Job_Hunt_Tracker.xlsx
```

Exit codes: 0 success, 1 validation failed, 2 unreadable or malformed input.

## 5. Adding a country

Copy `markets/_template_market.json` to `markets/<country>.json`, fill it in, tag each portal and regulator as `observed`, `reported` or `provisional`, then run:

```bash
python3 scripts/validate_contract.py market markets/<country>.json
```

## 6. Limitations

- JOBINTEL cannot see anything the host tools cannot reach. Some sites block automated access; those are reported as gaps, not bypassed.
- Availability is only as good as the last check. Re-verify before applying.
- Search results and job-board ages are often stale. Deadlines on the full advert decide.
- Market packs other than Zambia are provisional and unverified. The Zambia pack is only partly verified (see its `provenance` fields).
- The profile engine reads what is written. It cannot know about undocumented experience, and it will not invent any.
- Matching is advisory. Employers apply their own screening, including requirements a CV cannot show.
- There is no scheduler, alerting, email sending or application submission in this package.
- PDF and Excel generation need optional libraries, and PDF output has been tested only where those libraries were installed.

## 7. Privacy

Do not commit CVs, certificates, profiles, trackers or application documents. `.gitignore` blocks common formats and names, and `tests/test_repo_hygiene.py` fails if candidate-like files or personal contact details appear in the repository. Only fictional fixtures belong here.
