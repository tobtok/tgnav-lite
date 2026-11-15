# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the
project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-11-16

### Added
- **Client-side site search** (`search.html` + `static/search.js`): searches
  name, username, description and tags over a chunked static JSON index —
  no backend, index files load progressively. Group/Channel filter included.
- **Sitemap index + sharding**: directories above `SITEMAP_MAX_URLS`
  (default 45,000) automatically split into `sitemap-N.xml` shards with a
  `sitemapindex` root.
- **Category pagination pages now appear in the sitemap** and emit
  `rel="prev"/"next"` links; each pagination page has its own canonical URL.
- **404 page**, **favicon** (`static/favicon.svg`), **breadcrumb navigation**
  on detail and category pages.
- **OpenGraph tags** on every page (`og:site_name`, `og:title`, `og:type`,
  `og:url`, `og:description`, optional `og:image` via `SITE_OG_IMAGE`).
- **JSON-LD rendered with Jinja `tojson`** — entries containing quotes,
  `<script>` or `&` can no longer break the page.
- **Safe XML escaping** in sitemap URLs.
- **`lastmod` reflects real content dates**: entries use their `added` date;
  category pages use the newest entry date. Honest dates instead of
  build-date-everywhere.
- **Atomic build**: everything renders into `dist-staging`, passes an
  internal-link integrity check, and only then swaps into `dist/`. A failed
  build can never corrupt the previous output.
- **Built-in link checker**: build fails loudly if any internal href/src
  points at a file that was not generated.
- **pytest suite** (`tests/`), test workflow (`.github/workflows/test.yml`),
  benchmark script (`tests/bench.py`), `pyproject.toml` with a
  `tgnav-build` console script.
- `PER_PAGE`, `SITEMAP_MAX_URLS`, `SEARCH_CHUNK`, `SITE_OG_IMAGE`,
  `SITE_BASE` configuration (env or `Config`).

### Changed
- **Detail-page URLs are now derived from the username** instead of the
  display name. Telegram usernames are unique and case-insensitive
  platform-wide, so a page URL can never shift when same-named entries are
  added later. This is the one breaking change in 0.2.0 — see the migration
  note in the README.
- Usernames are deduplicated **case-insensitively** (matching Telegram
  behaviour); the original display form is preserved on pages.
- Related entries ("Similar in …") are precomputed per category in a single
  pass — O(n) total instead of O(n²) for large categories.
- Input validation is strict with file/line context on every error
  (username format, `members` type, `added` ISO date, JSON syntax).

### Fixed
- Category slug collisions: two categories that slugify identically no
  longer overwrite each other's pages.
- Root-relative asset paths now respect `SITE_BASE` (GitHub Pages
  sub-directory hosting).
- `members` given as `"12k"` or a float string no longer crashes the build
  with a bare traceback.

## [0.1.0] — 2026-11-15
- Initial public release: JSON → static HTML generator with index, category,
  detail pages, sitemap, robots.txt, Jinja2 templates and a GitHub Pages
  deploy workflow.
