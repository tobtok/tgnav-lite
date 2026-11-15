"""SEO outputs: sitemap correctness, JSON-LD safety, canonical URLs."""

import json
import re
import xml.etree.ElementTree as ET

from generator.build import build

from conftest import make_config


def get_urls(cfg):
    tree = ET.parse(cfg.out_dir / "sitemap.xml")
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [u.text for u in tree.getroot().findall(".//sm:loc", ns)]


def test_sitemap_includes_all_page_kinds(tmp_path, sample_entries):
    cfg = make_config(tmp_path, sample_entries)
    build(cfg)
    urls = get_urls(cfg)
    assert "https://test.example.com/" in urls
    assert "https://test.example.com/category/tech.html" in urls
    assert "https://test.example.com/channel/example-tech-lounge.html" in urls
    assert "https://test.example.com/group/example-movie-club.html" in urls


def test_sitemap_excludes_utility_pages(tmp_path, sample_entries):
    cfg = make_config(tmp_path, sample_entries)
    build(cfg)
    urls = get_urls(cfg)
    assert all("search.html" not in u for u in urls)
    assert all("404" not in u for u in urls)


def test_sitemap_escapes_xml(tmp_path):
    """SITE_URL containing & must not break the sitemap."""
    cfg = make_config(tmp_path, [
        {"name": "A", "username": "abc_xyz", "type": "group", "category": "C"}
    ], site_url="https://test.example.com")
    cfg.site_url = "https://test.example.com/a?b=1&c=2"
    build(cfg)
    tree = ET.parse(cfg.out_dir / "sitemap.xml")  # would raise on raw &
    assert len(get_urls(cfg)) > 0


def test_sitemap_index_on_large_directory(tmp_path):
    entries = [
        {
            "name": f"Entry {i}",
            "username": f"user_{i:05d}",
            "type": "group",
            "category": f"Cat{i % 50}",
        }
        for i in range(1200)
    ]
    cfg = make_config(tmp_path, entries, sitemap_max_urls=500)
    build(cfg)
    assert (cfg.out_dir / "sitemap.xml").exists()
    tree = ET.parse(cfg.out_dir / "sitemap.xml")
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    shards = tree.getroot().findall(".//sm:loc", ns)
    assert len(shards) >= 3  # 1200 urls / 500 per shard
    for loc in shards:
        fname = loc.text.rsplit("/", 1)[1]
        ET.parse(cfg.out_dir / fname)  # each shard parses


def test_json_ld_parses_and_is_safe(tmp_path):
    entries = [
        {
            "name": 'Evil "Name" <script>alert(1)</script>',
            "username": "evil_name_x",
            "type": "group",
            "category": "C & D",
            "description": "desc with 'quotes' and <tags>",
        }
    ]
    cfg = make_config(tmp_path, entries)
    build(cfg)
    html = (cfg.out_dir / "group" / "evil-name-x.html").read_text(encoding="utf-8")
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert m, "JSON-LD block missing"
    ld = json.loads(m.group(1))  # must parse
    assert ld["name"].startswith("Evil")
    # no raw </script> inside the JSON block (would break the page)
    assert "</script>" not in m.group(1).lower().replace("</script>", "", 1)


def test_pagination_canonical_points_to_itself(tmp_path):
    entries = [
        {
            "name": f"Entry {i:03d}",
            "username": f"user_{i:05d}",
            "type": "group",
            "category": "Big",
        }
        for i in range(30)
    ]
    cfg = make_config(tmp_path, entries, per_page=10)
    build(cfg)
    p2 = cfg.out_dir / "category" / "big-2.html"
    p3 = cfg.out_dir / "category" / "big-3.html"
    assert p2.exists() and p3.exists()
    can2 = re.search(
        r'rel="canonical" href="([^"]+)"', p2.read_text(encoding="utf-8")
    ).group(1)
    assert can2 == "https://test.example.com/category/big-2.html"
    prev_next = p2.read_text(encoding="utf-8")
    assert 'rel="prev"' in prev_next and 'rel="next"' in prev_next


def test_lastmod_uses_entry_date(tmp_path, sample_entries):
    cfg = make_config(tmp_path, sample_entries)
    build(cfg)
    import xml.etree.ElementTree as ET

    tree = ET.parse(cfg.out_dir / "sitemap.xml")
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    lastmods = {
        u.text: lm.text
        for u, lm in zip(
            tree.getroot().findall(".//sm:loc", ns),
            tree.getroot().findall(".//sm:lastmod", ns),
        )
    }
    assert lastmods["https://test.example.com/channel/example-tech-lounge.html"] == "2026-01-15"
    assert lastmods["https://test.example.com/group/example-movie-club.html"] == "2026-02-01"


def test_robots_has_sitemap(tmp_path, sample_entries):
    cfg = make_config(tmp_path, sample_entries, site_base="/repo")
    build(cfg)
    robots = (cfg.out_dir / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap: https://test.example.com/sitemap.xml" in robots


def test_internal_links_resolve(tmp_path):
    """Build with pagination + mixed content, then rely on the built-in check."""
    entries = [
        {
            "name": f"Entry {i:03d}",
            "username": f"user_{i:05d}",
            "type": ["group", "channel"][i % 2],
            "category": f"Cat{i % 7}",
            "description": f"Description {i}",
            "tags": ["t"],
            "added": "2026-03-01",
        }
        for i in range(120)
    ]
    cfg = make_config(tmp_path, entries, per_page=25, site_base="/repo")
    cfg.site_url = "https://test.example.com/repo"
    stats = build(cfg)  # build() raises BuildError on broken internal links
    assert stats["pages"] > 100
