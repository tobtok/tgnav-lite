#!/usr/bin/env python3
"""tgnav-lite — static site generator for Telegram group/channel directories.

Reads JSON data files from data/, renders templates from templates/,
writes a complete static site into dist/.

Usage:
    python generator/build.py

Environment overrides:
    SITE_NAME        display name of the site                (default: "TG Nav Directory")
    SITE_URL         absolute base URL, no trailing slash    (default: "https://example.com")
    SITE_BASE        URL path prefix for sub-path hosting    (default: "")
    PER_PAGE         items per category page                 (default: 200)
    SITEMAP_MAX_URLS max URLs per sitemap file before split  (default: 45000)
    SEARCH_CHUNK     entries per search-index chunk          (default: 4000)
    SITE_OG_IMAGE    absolute OpenGraph image URL            (default: none)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import unicodedata
import xml.sax.saxutils as xml_escape
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE = Path(__file__).resolve().parent.parent

VALID_TYPES = ("group", "channel")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{4,64}$")


class BuildError(Exception):
    """Raised with a clear, user-facing message for any invalid input/config."""


@dataclass
class Config:
    data_dir: Path
    tpl_dir: Path
    static_dir: Path
    out_dir: Path
    site_name: str
    site_url: str          # absolute, no trailing slash; may include the sub-path
    site_base: str         # URL path prefix, "" for domain-root hosting
    per_page: int
    sitemap_max_urls: int
    search_chunk: int
    og_image: str = ""
    # Optional attribution link rendered in the footer (e.g. a live
    # production deployment of this generator). Empty = no extra link.
    footer_link_url: str = ""
    footer_link_text: str = ""

    @property
    def now_str(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_config(env: dict[str, str] | None = None) -> Config:
    env = dict(os.environ if env is None else env)
    base_dir = Path(env.get("TGLITE_BASE", BASE))

    def _int(name: str, default: int, minimum: int) -> int:
        raw = env.get(name, str(default)).strip()
        try:
            val = int(raw)
        except ValueError:
            raise BuildError(f"environment {name}={raw!r} must be an integer") from None
        if val < minimum:
            raise BuildError(f"environment {name}={val} must be >= {minimum}")
        return val

    cfg = Config(
        data_dir=Path(env.get("TGLITE_DATA", base_dir / "data")),
        tpl_dir=Path(env.get("TGLITE_TEMPLATES", base_dir / "templates")),
        static_dir=Path(env.get("TGLITE_STATIC", base_dir / "static")),
        out_dir=Path(env.get("TGLITE_OUT", base_dir / "dist")),
        site_name=env.get("SITE_NAME", "TG Nav Directory").strip() or "TG Nav Directory",
        site_url=env.get("SITE_URL", "https://example.com").strip().rstrip("/"),
        site_base=env.get("SITE_BASE", "").strip().rstrip("/"),
        per_page=_int("PER_PAGE", 200, 1),
        sitemap_max_urls=_int("SITEMAP_MAX_URLS", 45000, 500),
        search_chunk=_int("SEARCH_CHUNK", 4000, 100),
        og_image=env.get("SITE_OG_IMAGE", "").strip(),
        footer_link_url=env.get("FOOTER_LINK_URL", "").strip(),
        footer_link_text=env.get("FOOTER_LINK_TEXT", "").strip(),
    )
    if cfg.footer_link_url:
        if not cfg.footer_link_url.startswith(("http://", "https://")):
            raise BuildError(
                f"environment FOOTER_LINK_URL={cfg.footer_link_url!r} "
                "must start with http:// or https://"
            )
        cfg.footer_link_url = cfg.footer_link_url.rstrip("/")
        if not cfg.footer_link_text:
            cfg.footer_link_text = cfg.footer_link_url
    return cfg


# ---------------------------------------------------------------- slugs

def slugify(text: str) -> str:
    """URL-safe slug: lowercase, whitespace/underscores → hyphens.

    CJK characters are preserved (readable, SEO-useful for Chinese
    directories); browsers percent-encode them transparently. Names made
    purely of symbols/emoji fall back to a short hash so a slug always exists.
    """
    slug = unicodedata.normalize("NFKD", text)
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE).strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = hashlib.md5(text.encode("utf-8")).hexdigest()[:10]
    return slug[:64].strip("-") or hashlib.md5(text.encode("utf-8")).hexdigest()[:10]


def unique_slug(base: str, taken: set[str]) -> str:
    """Deterministic collision resolver: first caller wins, later ones get -2, -3 ..."""
    if base not in taken:
        taken.add(base)
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    slug = f"{base}-{n}"
    taken.add(slug)
    return slug


# ---------------------------------------------------------------- data loading

def _parse_members(raw: Any, where: str) -> int:
    if raw is None or raw == "":
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            raise BuildError(f"{where}: 'members' must be a number, got {raw!r}") from None


def _parse_date(raw: Any, where: str) -> str:
    if raw is None or str(raw).strip() == "":
        return ""
    value = str(raw).strip()
    try:
        date.fromisoformat(value)
    except ValueError:
        raise BuildError(
            f"{where}: 'added' must be an ISO date (YYYY-MM-DD), got {value!r}"
        ) from None
    return value


def load_items(cfg: Config) -> list[dict]:
    """Load + validate all JSON data files. Raises BuildError with file/index context."""
    items: list[dict] = []
    files = sorted(cfg.data_dir.glob("*.json"))
    if not files:
        raise BuildError(
            f"No data files found in {cfg.data_dir}. "
            "Add a JSON array of entries (see README 'Data format')."
        )
    seen: dict[str, str] = {}  # username_lower -> username as first seen (display form)
    for path in files:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BuildError(f"{path.name}: invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}") from None
        if not isinstance(raw, list):
            raise BuildError(f"{path.name}: top level must be a JSON array")
        for i, it in enumerate(raw):
            where = f"{path.name}[{i}]"
            if not isinstance(it, dict):
                raise BuildError(f"{where}: entry must be a JSON object")
            for fname in ("name", "username", "type", "category"):
                value = it.get(fname)
                if value is None or str(value).strip() == "":
                    raise BuildError(f"{where}: missing required field '{fname}'")
            if it["type"] not in VALID_TYPES:
                raise BuildError(
                    f"{where}: type must be one of {list(VALID_TYPES)}, got {it['type']!r}"
                )
            display_uname = str(it["username"]).strip().lstrip("@")
            if not USERNAME_RE.match(display_uname):
                raise BuildError(
                    f"{where}: invalid Telegram username '@{display_uname}' "
                    "(allowed: 4-64 letters, digits, underscores)"
                )
            key = display_uname.lower()
            if key in seen:
                raise BuildError(
                    f"{where}: duplicate username '@{display_uname}' "
                    f"(case-insensitive match with '@{seen[key]}')"
                )
            seen[key] = display_uname
            tags = it.get("tags") or []
            if not isinstance(tags, list):
                raise BuildError(f"{where}: 'tags' must be an array of strings")
            items.append(
                {
                    "name": str(it["name"]).strip(),
                    "username": display_uname,       # original display form
                    "username_lower": key,           # dedupe/search key
                    "type": it["type"],
                    "category": str(it["category"]).strip(),
                    "description": str(it.get("description") or "").strip(),
                    "members": _parse_members(it.get("members"), where),
                    "tags": [str(t).strip() for t in tags if str(t).strip()],
                    "added": _parse_date(it.get("added"), where),
                }
            )
    # deterministic order: newest first, then name A→Z (stable two-pass)
    items.sort(key=lambda x: x["name"].lower())
    items.sort(key=lambda x: x["added"], reverse=True)
    if not items:
        raise BuildError(
            f"Data files in {cfg.data_dir} contain no entries. "
            "Add a JSON array of entries (see README 'Data format')."
        )
    return items


def group_by_category(items: list[dict]) -> dict[str, list[dict]]:
    cats: dict[str, list[dict]] = {}
    for it in items:
        cats.setdefault(it["category"], []).append(it)
    return dict(sorted(cats.items(), key=lambda kv: (-len(kv[1]), kv[0])))


def assign_category_slugs(cats: dict[str, list[dict]]) -> dict[str, str]:
    """category display name -> unique slug. Deterministic, collision-safe."""
    taken: set[str] = set()
    out: dict[str, str] = {}
    for name in sorted(cats.keys()):
        out[name] = unique_slug(slugify(name), taken)
    return out


def assign_detail_slugs(items: list[dict]) -> None:
    """Stable per-entry slug derived from the username (unique by data validation).

    Telegram usernames are case-insensitive and unique platform-wide, so the URL
    of a page never changes when new entries are added. The suffix disambiguator
    only triggers when two *different* usernames collapse to the same ASCII slug
    (e.g. "abc_1" vs "abc-1"); it is assigned in username order so the result is
    reproducible across builds.
    """
    by_type: dict[str, list[dict]] = {"group": [], "channel": []}
    for it in items:
        by_type[it["type"]].append(it)
    for entries in by_type.values():
        taken: set[str] = set()
        for it in sorted(entries, key=lambda x: x["username_lower"]):
            it["slug"] = unique_slug(slugify(it["username"]), taken)


# ---------------------------------------------------------------- env/template

def make_env(cfg: Config, cat_slugs: dict[str, str], now_str: str) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(cfg.tpl_dir)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["fmt_members"] = lambda n: f"{n:,}" if n else ""
    env.globals.update(
        SITE_NAME=cfg.site_name,
        SITE_URL=cfg.site_url,
        SITE_BASE=cfg.site_base,
        OG_IMAGE=cfg.og_image,
        FOOTER_LINK_URL=cfg.footer_link_url.rstrip("/") if cfg.footer_link_url else "",
        FOOTER_LINK_TEXT=cfg.footer_link_text or cfg.footer_link_url,
        NOW=now_str,
        cat_slugs=cat_slugs,
    )
    return env


# ---------------------------------------------------------------- file writing

def remove_tree(path: Path) -> None:
    """Delete a directory tree; best-effort under sandboxed/locked environments.

    Never raises: if deletion is refused (sandbox policy, file locks), the
    caller proceeds and stale directories are cleaned up on a later build.
    """
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
        return
    except Exception:
        pass
    for root, dirs, files in os.walk(path, topdown=False):
        for f in files:
            try:
                os.unlink(os.path.join(root, f))
            except Exception:
                pass
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except Exception:
                pass
    try:
        path.rmdir()
    except Exception:
        pass


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# ---------------------------------------------------------------- sitemap

def _sitemap_url_xml(loc: str, lastmod: str) -> str:
    return (
        "  <url>"
        f"<loc>{xml_escape.escape(loc)}</loc>"
        f"<lastmod>{xml_escape.escape(lastmod)}</lastmod>"
        "</url>"
    )


def write_sitemaps(cfg: Config, out: Path, urls: list[tuple[str, str]]) -> None:
    """Write sitemap (index + shards when large). urls = [(loc, lastmod), ...]."""
    header = '<?xml version="1.0" encoding="UTF-8"?>'
    if len(urls) <= cfg.sitemap_max_urls:
        lines = [header, '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        lines += [_sitemap_url_xml(loc, lm) for loc, lm in urls]
        lines.append("</urlset>")
        write(out / "sitemap.xml", "\n".join(lines))
        return
    shards: list[str] = []
    for i in range(0, len(urls), cfg.sitemap_max_urls):
        n = i // cfg.sitemap_max_urls + 1
        fname = f"sitemap-{n}.xml"
        lines = [header, '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        lines += [_sitemap_url_xml(loc, lm) for loc, lm in urls[i : i + cfg.sitemap_max_urls]]
        lines.append("</urlset>")
        write(out / fname, "\n".join(lines))
        shards.append(fname)
    index = [
        header,
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    index += [
        f"  <sitemap><loc>{xml_escape.escape(cfg.site_url)}/{xml_escape.escape(f)}</loc>"
        f"<lastmod>{xml_escape.escape(cfg.now_str)}</lastmod></sitemap>"
        for f in shards
    ]
    index.append("</sitemapindex>")
    write(out / "sitemap.xml", "\n".join(index))


# ---------------------------------------------------------------- search index

def write_search_index(cfg: Config, out: Path, items: list[dict]) -> int:
    """Static, chunked search index (no backend). Returns entry count."""
    if not items:
        return 0
    search_dir = out / "search"
    search_dir.mkdir(parents=True, exist_ok=True)
    chunk_files: list[str] = []
    total = 0
    for i in range(0, len(items), cfg.search_chunk):
        chunk = items[i : i + cfg.search_chunk]
        fname = f"search-{i // cfg.search_chunk + 1}.json"
        rows = [
            [
                it["name"],
                it["username"],
                it["type"],
                it["category"],
                it["description"][:140],
                "|".join(it["tags"][:8]),
                f"{it['type']}/{it['slug']}.html",
            ]
            for it in chunk
        ]
        write(search_dir / fname, json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
        chunk_files.append(fname)
        total += len(rows)
    write(
        search_dir / "index.json",
        json.dumps({"chunks": chunk_files, "count": total}, separators=(",", ":")),
    )
    return total


# ---------------------------------------------------------------- link check

_HREF_RE = re.compile(r'(?:href|src)="([^"]+)"')


def check_internal_links(cfg: Config, out: Path) -> list[str]:
    """Verify every internal href/src resolves to a generated file. Returns problems."""
    problems: list[str] = []
    for html in out.rglob("*.html"):
        rel_dir = html.parent.relative_to(out)
        for ref in _HREF_RE.findall(html.read_text(encoding="utf-8")):
            if ref.startswith(("#", "mailto:", "tel:", "data:")):
                continue
            path_part = None
            if ref.startswith(cfg.site_url + "/"):
                path_part = ref[len(cfg.site_url) + 1 :]
            elif cfg.site_base and ref.startswith(cfg.site_base + "/"):
                path_part = ref[len(cfg.site_base) + 1 :]
            elif not re.match(r"^[a-z][a-z0-9+.-]*:", ref) and not ref.startswith("//"):
                # site-relative like /static/style.css or page.html
                if ref.startswith("/") and not cfg.site_base:
                    path_part = ref.lstrip("/")
                elif not ref.startswith("/"):
                    path_part = str((rel_dir / ref).as_posix())
                elif cfg.site_base and ref.startswith("/"):
                    problems.append(f"{html.relative_to(out)}: root-relative link '{ref}' "
                                    "without SITE_BASE prefix")
                    continue
            if path_part is None:
                continue  # external link
            path_part = path_part.split("#", 1)[0].split("?", 1)[0]
            if path_part == "":
                target = out / "index.html"
            else:
                target = out / path_part
            if not target.exists():
                problems.append(
                    f"{html.relative_to(out)}: broken internal link '{ref}'"
                )
    return problems


# ---------------------------------------------------------------- build

def build(cfg: Config) -> dict[str, Any]:
    """Full build into a staging dir, then atomic swap into out_dir.

    Raises BuildError on invalid input; the existing out_dir is never touched
    on failure.
    """
    items = load_items(cfg)
    cats = group_by_category(items)
    cat_slugs = assign_category_slugs(cats)
    cat_names = list(cats.keys())
    assign_detail_slugs(items)
    now_str = cfg.now_str

    env = make_env(cfg, cat_slugs, now_str)

    # staging directory: never touch the live output until success
    staging = cfg.out_dir.with_name(cfg.out_dir.name + "-staging")
    remove_tree(staging)
    staging.mkdir(parents=True)

    # absolute URLs for each entry
    for it in items:
        it["url"] = f"{cfg.site_url}/{it['type']}/{it['slug']}.html"

    # precompute related entries per category in one pass (no per-page rescan)
    for citems in cats.values():
        n = len(citems)
        for i, it in enumerate(citems):
            forward = citems[i + 1 : i + 9]
            deficit = 8 - len(forward)
            backward = citems[max(0, i - deficit) : i] if deficit > 0 else []
            it["related"] = (forward + backward)[:8]

    stats: dict[str, Any] = {"entries": len(items), "categories": len(cats), "pages": 0}

    tpl_detail = env.get_template("detail.html")
    tpl_category = env.get_template("category.html")

    # ---------- detail pages ----------
    for it in items:
        ld = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": it["name"],
            "description": it["description"][:155],
            "url": it["url"],
            "mainEntity": {
                "@type": "Thing",
                "name": it["name"],
                "sameAs": f"https://t.me/{it['username']}",
            },
        }
        ctx = {
            "item": it,
            "related": it.get("related", []),
            "cat_names": cat_names,
            "cat_slug": cat_slugs[it["category"]],
            "ld": ld,
            "page_type": "detail",
        }
        write(staging / it["type"] / f"{it['slug']}.html", tpl_detail.render(**ctx))
        stats["pages"] += 1

    # ---------- category pages ----------
    cat_meta = []
    for cname, citems in cats.items():
        cslug = cat_slugs[cname]
        chunks = [citems[i : i + cfg.per_page] for i in range(0, len(citems), cfg.per_page)]
        cat_lastmod = max((x["added"] for x in citems if x["added"]), default=now_str)
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
            write(staging / "category" / fname, tpl_category.render(**ctx))
            stats["pages"] += 1
        cat_meta.append(
            {
                "name": cname,
                "slug": cslug,
                "count": len(citems),
                "url": f"{cfg.site_url}/category/{cslug}.html",
                "lastmod": cat_lastmod,
            }
        )

    # ---------- homepage ----------
    featured = items[:24]
    write(
        staging / "index.html",
        env.get_template("index.html").render(
            items=featured,
            cat_meta=cat_meta,
            total=len(items),
            cat_names=cat_names,
            page_type="index",
        ),
    )
    stats["pages"] += 1

    # ---------- 404 + search pages ----------
    write(staging / "404.html", env.get_template("404.html").render(cat_names=cat_names, page_type="404"))
    stats["pages"] += 1
    if items:
        write(staging / "search.html", env.get_template("search.html").render(cat_names=cat_names, page_type="search"))
        stats["pages"] += 1

    # ---------- sitemap + robots ----------
    urls: list[tuple[str, str]] = [(cfg.site_url + "/", now_str)]
    urls += [(c["url"], c["lastmod"]) for c in cat_meta]
    # category pagination pages
    for cname, citems in cats.items():
        cslug = cat_slugs[cname]
        total_pages = max(1, -(-len(citems) // cfg.per_page))
        cat_lastmod = max((x["added"] for x in citems if x["added"]), default=now_str)
        for p in range(2, total_pages + 1):
            urls.append((f"{cfg.site_url}/category/{cslug}-{p}.html", cat_lastmod))
    urls += [(it["url"], it["added"] or now_str) for it in items]
    write_sitemaps(cfg, staging, urls)
    write(
        staging / "robots.txt",
        f"User-agent: *\nAllow: /\nSitemap: {cfg.site_url}/sitemap.xml\n",
    )

    # ---------- search index ----------
    stats["search_indexed"] = write_search_index(cfg, staging, items)

    # ---------- static assets ----------
    if cfg.static_dir.exists():
        shutil.copytree(cfg.static_dir, staging / "static", dirs_exist_ok=True)

    # ---------- integrity checks before going live ----------
    problems = check_internal_links(cfg, staging)
    if problems:
        preview = "\n".join(problems[:20])
        raise BuildError(
            f"internal link check failed ({len(problems)} broken):\n{preview}"
        )
    if not (staging / "index.html").exists():
        raise BuildError("build produced no index.html")

    # ---------- atomic swap ----------
    old = cfg.out_dir.with_name(cfg.out_dir.name + "-old")
    remove_tree(old)
    if cfg.out_dir.exists():
        try:
            cfg.out_dir.rename(old)
        except OSError:
            remove_tree(cfg.out_dir)
    try:
        staging.rename(cfg.out_dir)
    except OSError:
        # fallback: copy contents (cross-device or sandboxed rename)
        shutil.copytree(staging, cfg.out_dir, dirs_exist_ok=True)
        remove_tree(staging)
    remove_tree(old)

    return stats


def main() -> None:
    cfg = load_config()
    try:
        stats = build(cfg)
    except BuildError as exc:
        raise SystemExit(f"tgnav-lite: ERROR: {exc}") from None
    print(
        f"tgnav-lite: {stats['entries']} entries, {stats['categories']} categories, "
        f"{stats['pages']} pages, search index {stats['search_indexed']} -> {cfg.out_dir}"
    )


if __name__ == "__main__":
    main()
