# Contributing to tgnav-lite

Thanks for your interest in improving tgnav-lite! This project values
small, boring, maintainable code — please keep that spirit in mind.

## Development setup

```bash
git clone https://github.com/tobtok/tgnav-lite.git
cd tgnav-lite
pip install -e ".[dev]"
pytest
```

## Ground rules

1. **Static-first.** No databases, no server-side code, no heavy frontend
   frameworks. If a feature needs a backend, it probably doesn't belong here.
2. **One runtime dependency** (Jinja2). Dev dependencies (pytest) are fine.
3. **URLs are a public contract.** Anything that changes generated URLs must
   be discussed in an issue first and documented in `CHANGELOG.md` with a
   migration note.
4. **Data format compatibility.** The JSON entry format is documented in the
   README; new fields must be optional and backwards compatible.
5. **Tests required.** Every bug fix or feature needs a test that fails
   without your change.
6. **SEO hygiene.** Canonical URLs, sitemap and structured data changes must
   follow real search-engine behaviour — no speculative schema stacking.

## Pull requests

- Keep PRs focused; one feature or fix per PR.
- Run `pytest` and (for perf-relevant changes) `python tests/bench.py` and
  include the numbers in the PR description.
- Update `CHANGELOG.md` under an *Unreleased* heading.

## Reporting bugs

Open a bug report with the generator error message, the input JSON entry
(redact anything private) and the command you ran. Never paste private
channel data you don't own.
