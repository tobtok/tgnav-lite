# tgnav-lite

A lightweight, SEO-friendly **static site generator for Telegram group & channel directories**.

Feed it a JSON file of Telegram groups/channels, and it builds a complete static website:
homepage, category pages, detail pages with structured data, `sitemap.xml` and `robots.txt`.
No database, no server-side code — the output is pure HTML you can host anywhere
(GitHub Pages, Cloudflare Pages, any static host).

> **Live demo** — a directory built with this generator: *coming soon*

## Why static?

Telegram group directories usually die from complexity: a database, a backend, constant
maintenance. `tgnav-lite` takes the boring path instead:

- **Data in, HTML out.** One command rebuilds the whole site.
- **Nothing to break.** Static pages can't be hacked, don't need patching, load instantly.
- **SEO by default.** Canonical URLs, meta descriptions, `ItemList` JSON-LD, clean slugs,
  auto-generated sitemap — the on-page basics that directory sites usually get wrong.

## Quick start

```bash
pip install -r requirements.txt
python generator/build.py
```

The site is generated into `dist/`. Open `dist/index.html` in a browser, or serve it:

```bash
python -m http.server -d dist 8080
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

| Field        | Required | Notes                                            |
|--------------|----------|--------------------------------------------------|
| `name`       | yes      | Display name                                     |
| `username`   | yes      | Telegram username **without `@`**                |
| `type`       | yes      | `group` or `channel`                             |
| `category`   | yes      | Free text; one page is generated per category    |
| `description`| no       | Shown on the detail page; keep it human-written  |
| `members`    | no       | Approximate subscriber count (display only)      |
| `tags`       | no       | Free-form tags                                   |
| `added`      | no       | ISO date; used for sorting                       |

## Customization

- **Templates** live in `templates/` (Jinja2). Edit freely — the generator passes each
  item plus the full item list to every page.
- **Styles** are a single file, `static/style.css`. Light, responsive, no framework.
- **Site name, base URL and page size** are configured at the top of `generator/build.py`
  or via environment variables (`SITE_NAME`, `SITE_URL`, `PER_PAGE`).

## Design principles

1. **Index, not host.** This project only generates pages that link to public Telegram
   resources *you* add to the data files. It hosts, stores and distributes no Telegram
   content whatsoever.
2. **Human-written descriptions.** Auto-generated filler text is the fastest way for a
   directory to lose search-engine trust. The templates are built around real, unique
   descriptions — write one per entry.
3. **Boring tech.** Python + Jinja2 + one CSS file. Easy to read, easy to fork.

## Roadmap

- [ ] Pagination for large categories
- [ ] Search (client-side, index built at generation time)
- [ ] i18n (UI strings are currently English)
- [ ] OpenGraph images for detail pages

## License

[MIT](LICENSE) — use it, fork it, build your directory with it.

## Disclaimer

This software is an independent, generic website generator. It is not affiliated with or
endorsed by Telegram. Users are responsible for the links they publish and for complying
with Telegram's Terms of Service and the laws of their jurisdiction.
