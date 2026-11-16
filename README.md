# tgnav-lite

A lightweight, SEO-friendly **static site generator for Telegram group & channel directories**.

Feed it JSON data files of Telegram groups/channels, and it builds a complete static website:
homepage, category pages with pagination, detail pages, **client-side search**,
`sitemap.xml` (with automatic index + sharding), `robots.txt`, a 404 page and OpenGraph tags.
No database, no server-side code — the output is pure HTML you can host anywhere
(GitHub Pages, Cloudflare Pages, any static host).

**Live demo** — a directory built with this generator:
**[https://tobtok.github.io/tgnav-lite/](https://tobtok.github.io/tgnav-lite/)**
(auto-rebuilt on every push via GitHub Actions — see `.github/workflows/deploy-pages.yml`).

Used in production by [navsou.com](https://navsou.com/) — the author's live
Telegram directory, rebuilt every 15 minutes from its own data pipeline.

## Features

- **JSON in, HTML out.** One command rebuilds the whole site.
- **SEO by default.** Canonical URLs (including per-pagination-page), `lastmod` based on
  real entry dates, safe XML sitemap with automatic sharding for large directories,
  escaped JSON-LD, OpenGraph tags, clean slugs.
- **Client-side search.** Name, username, description and tag search over a chunked
  static JSON index — loads progressively, filters by group/channel, no backend.
- **Stable URLs.** Detail-page slugs come from the Telegram username, so adding
  same-named entries never shifts an existing page's URL.
- **Safe builds.** Everything renders into a staging directory, passes an internal
  link-integrity check, and only then replaces `dist/`. A failed build never
  corrupts the previous output.
- **Responsive UI.** Card layout, light/dark theme (follows the OS setting),
  keyboard accessible, mobile-first breakpoints. One CSS file, zero frameworks.
- **Tested.** pytest suite covering validation, slugs, pagination, SITE_BASE,
  sitemap/JSON-LD correctness and link integrity; benchmark script included.

## Quick start

```bash
pip install -r requirements.txt
python generator/build.py
```

The site is generated into `dist/`. Open `dist/index.html` in a browser, or serve it:

```bash
python -m http.server -d dist 8080
```

Or install as a package and use the console script:

```bash
pip install .
tgnav-build
```

## Data format

Put one or more JSON files in `data/`. Each file is an array of entries:

```json
[
  {
    "name": "Example Tech Lounge",
    "username": "example_tech_lounge",
    "type": "channel",
    "category": "Tech",
    "description": "Daily news and discussion about technology.",
    "members": 12345,
    "tags": ["tech", "news"],
    "added": "2026-11-16"
  }
]
```

| Field         | Required | Notes                                                        |
|---------------|----------|--------------------------------------------------------------|
| `name`        | yes      | Display name                                                 |
| `username`    | yes      | Telegram username **without `@`**; 4–64 letters/digits/underscores; deduplicated case-insensitively, original form preserved |
| `type`        | yes      | `group` or `channel`                                         |
| `category`    | yes      | Free text; one page is generated per category                |
| `description` | no       | Shown on the detail page; keep it human-written              |
| `members`     | no       | Number (integer or numeric string)                           |
| `tags`        | no       | Array of strings; searchable                                 |
| `added`       | no       | ISO date `YYYY-MM-DD`; drives ordering and sitemap `lastmod` |

Invalid input stops the build with a precise message
(`items.json[42]: invalid Telegram username '@bad name!' …`) — nothing partial is published.

## Configuration

All settings are environment variables (or fields of `generator.build.Config`
when you call `build()` programmatically):

| Variable           | Default                | Meaning                                        |
|--------------------|------------------------|------------------------------------------------|
| `SITE_NAME`        | `TG Nav Directory`     | Display name                                   |
| `SITE_URL`         | `https://example.com`  | Absolute base URL, no trailing slash           |
| `SITE_BASE`        | *(empty)*              | Path prefix for sub-path hosting, e.g. `/repo` |
| `PER_PAGE`         | `200`                  | Entries per category page                      |
| `SITEMAP_MAX_URLS` | `45000`                | Split into a sitemap index above this          |
| `SEARCH_CHUNK`     | `4000`                 | Entries per search-index chunk                 |
| `SITE_OG_IMAGE`    | *(empty)*              | Absolute OpenGraph image URL                   |
| `FOOTER_LINK_URL`  | *(empty)*              | Optional footer attribution link (e.g. your live deployment); empty = hidden |
| `FOOTER_LINK_TEXT` | *(= URL)*              | Anchor text for the footer link                |

`SITE_BASE` is required for GitHub Pages project sites
(`https://user.github.io/repo/` → `SITE_BASE=/repo`, `SITE_URL=https://user.github.io/repo`).

## Deployment

### GitHub Pages

`.github/workflows/deploy-pages.yml` deploys on every push to `main` — just enable
*Settings → Pages → Source: GitHub Actions*. The workflow sets `SITE_URL`/`SITE_BASE`
for sub-path hosting; adjust them to your own domain in one place.

### Cloudflare Pages / any static host

Build command: `python generator/build.py` — output directory: `dist`.
On a domain root you can leave `SITE_BASE` empty and only set `SITE_URL`.

## Upgrading from 0.1.x → 0.2.0

**One breaking change:** detail-page URLs are now derived from the **username**
(`group/example-tech-lounge.html`) instead of the display name. Telegram usernames
are unique platform-wide, which guarantees an entry's URL never changes when new
same-named entries appear (with name-based slugs, a new entry could silently
reallocate the suffix `-2`). Because usernames are unique, collisions are
effectively eliminated.

If your 0.1.x site has external links pointing at old name-based URLs, either
keep a copy of the old `dist/` and generate redirect stubs, or accept the change
while the site is young. Category, pagination, homepage and asset URLs are unchanged.

## Project layout

```
generator/build.py      # the generator (single file, ~600 lines, documented)
templates/              # Jinja2 templates (base, index, category, detail, search, 404)
static/                 # style.css, search.js, favicon.svg — no frameworks
data/                   # your JSON data files
tests/                  # pytest suite + tests/bench.py benchmark
.github/workflows/      # deploy-pages.yml (Pages), test.yml (pytest CI)
```

## Performance

`python tests/bench.py` builds synthetic directories of 1,000 / 10,000 / 50,000
entries and reports wall time and peak memory. Related-entry recommendations are
precomputed per category in one pass, so large single categories stay linear.

## Design principles

1. **Index, not host.** This project only generates pages that link to public Telegram
   resources *you* add to the data files. It hosts, stores and distributes no Telegram
   content whatsoever.
2. **Human-written descriptions.** Auto-generated filler text is the fastest way for a
   directory to lose search-engine trust. The templates are built around real, unique
   descriptions — write one per entry.
3. **Boring tech.** Python + Jinja2 + one CSS file + one vanilla JS file. Easy to read,
   easy to fork, easy to maintain.

## Roadmap

- [x] Pagination for large categories
- [x] Search (client-side, chunked static index)
- [x] Sitemap index / sharding for large directories
- [ ] OpenGraph images generated from entry data
- [ ] UI string i18n (UI is currently English)

## License

[MIT](LICENSE) — use it, fork it, build your directory with it.

## Disclaimer

This software is an independent, generic website generator. It is not affiliated with or
endorsed by Telegram. Users are responsible for the links they publish and for complying
with Telegram's Terms of Service and the laws of their jurisdiction.
