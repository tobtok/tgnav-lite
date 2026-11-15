#!/usr/bin/env python3
"""tgnav-lite — static site generator for Telegram group/channel directories.

Reads JSON data files from data/, renders templates from templates/,
writes a complete static site into dist/.

Usage:
    python generator/build.py

Environment overrides:
    SITE_NAME   display name of the site        (default: "TG Nav Directory")
    SITE_URL    absolute base URL, no trailing slash (default: "https://example.com")
    PER_PAGE    items per category page chunk    (default: 200, effectively no paging)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
TPL_DIR = BASE / "templates"
STATIC_DIR = BASE / "static"
OUT = BASE / "dist"

SITE_NAME = os.environ.get("SITE_NAME", "TG Nav Directory")
SITE_URL = os.environ.get("SITE_URL", "https://example.com").rstrip("/")
PER_PAGE = int(os.environ.get("PER_PAGE", "200"))

VALID_TYPES = {"group", "channel"}


def slugify(text: str) -> str:
    """ASCII-safe, readable slug. Falls back to a hash suffix for pure CJK names."""
    slug = unicodedata.normalize("NFKD", text)
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE).strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        import hashlib

        slug = hashlib.md5(text.encode("utf-8")).hexdigest()[:10]
    return slug[:64]


def load_items() -> list[dict]:
    items: list[dict] = []
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        raise SystemExit(
            f"No data files found in {DATA_DIR}. Add a JSON array of entries first."
        )
    seen_usernames: set[str] = set()
    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise SystemExit(f"{path.name}: top level must be a JSON array")
        for i, it in enumerate(raw):
            for field in ("name", "username", "type", "category"):
                if not it.get(field):
                    raise SystemExit(f"{path.name}[{i}]: missing required field '{field}'")
            if it["type"] not in VALID_TYPES:
                raise SystemExit(f"{path.name}[{i}]: type must be one of {sorted(VALID_TYPES)}")
            uname = str(it["username"]).lstrip("@").strip()
            if uname in seen_usernames:
                raise SystemExit(f"{path.name}[{i}]: duplicate username '@{uname}'")
            seen_usernames.add(uname)
            items.append(
                {
                    "name": str(it["name"]).strip(),
                    "username": uname,
                    "type": it["type"],
                    "category": str(it["category"]).strip(),
                    "description": str(it.get("description", "")).strip(),
                    "members": int(it.get("members", 0) or 0),
                    "tags": [str(t).strip() for t in it.get("tags", []) if str(t).strip()],
                    "added": str(it.get("added", "")).strip(),
                }
            )
    items.sort(key=lambda x: (x["added"] or "", x["name"]), reverse=True)
    return items


def group_by_category(items: list[dict]) -> dict[str, list[dict]]:
    cats: dict[str, list[dict]] = {}
    for it in items:
        cats.setdefault(it["category"], []).append(it)
    # stable, readable order: most items first
    return dict(sorted(cats.items(), key=lambda kv: -len(kv[1])))


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    tmp.replace(path)  # atomic-ish write


def main() -> None:
    items = load_items()
    cats = group_by_category(items)
    cat_names = list(cats.keys())
    cat_slugs = {name: slugify(name) for name in cat_names}
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    env = Environment(
        loader=FileSystemLoader(str(TPL_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["fmt_members"] = lambda n: f"{n:,}" if n else ""
    env.globals.update(
        SITE_NAME=SITE_NAME,
        SITE_URL=SITE_URL,
        NOW=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        cat_slugs=cat_slugs,
    )

    stats = {"pages": 0}

    # ---------- detail pages ----------
    used_slugs: set[str] = set()
    for it in items:
        base = slugify(it["name"])
        slug, n = base, 2
        while slug in used_slugs:
            slug = f"{base}-{n}"
            n += 1
        used_slugs.add(slug)
        it["slug"] = slug
    for it in items:
        url = f"{SITE_URL}/{it['type']}/{it['slug']}.html"
        it["url"] = url
        related = [x for x in cats[it["category"]] if x["username"] != it["username"]][:8]
        ctx = {
            "item": it,
            "related": related,
            "cat_names": cat_names,
            "page_type": "detail",
        }
        write(OUT / it["type"] / f"{it['slug']}.html", env.get_template("detail.html").render(**ctx))
        stats["pages"] += 1

    # ---------- category pages ----------
    cat_meta = []
    for cname, citems in cats.items():
        cslug = slugify(cname)
        chunks = [citems[i : i + PER_PAGE] for i in range(0, len(citems), PER_PAGE)]
        for idx, chunk in enumerate(chunks, start=1):
            fname = f"{cslug}.html" if idx == 1 else f"{cslug}-{idx}.html"
            ctx = {
                "category": cname,
                "cslug": cslug,
                "items": chunk,
                "page_no": idx,
                "total_pages": len(chunks),
                "cat_names": cat_names,
                "page_type": "category",
            }
            write(OUT / "category" / fname, env.get_template("category.html").render(**ctx))
            stats["pages"] += 1
        cat_meta.append(
            {
                "name": cname,
                "slug": cslug,
                "count": len(citems),
                "url": f"{SITE_URL}/category/{cslug}.html",
            }
        )

    # ---------- homepage ----------
    featured = items[:24]
    write(
        OUT / "index.html",
        env.get_template("index.html").render(
            items=featured,
            cat_meta=cat_meta,
            total=len(items),
            cat_names=cat_names,
            page_type="index",
        ),
    )
    stats["pages"] += 1

    # ---------- sitemap + robots ----------
    urls = [f"{SITE_URL}/"] + [c["url"] for c in cat_meta] + [it["url"] for it in items]
    sitemap = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in urls:
        sitemap.append(f"  <url><loc>{u}</loc><lastmod>{now_str}</lastmod></url>")
    sitemap.append("</urlset>")
    write(OUT / "sitemap.xml", "\n".join(sitemap))
    write(OUT / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")

    # ---------- static assets ----------
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUT / "static", dirs_exist_ok=True)

    print(f"tgnav-lite: {len(items)} entries, {len(cat_meta)} categories, "
          f"{stats['pages']} pages -> {OUT}")


if __name__ == "__main__":
    main()
