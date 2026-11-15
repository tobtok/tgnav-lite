"""SITE_BASE sub-path deployment, search index, config errors."""

import json

import pytest

from generator.build import BuildError, build, load_config

from conftest import make_config


def test_site_base_prefixes_all_internal_urls(tmp_path, sample_entries):
    cfg = make_config(
        tmp_path,
        sample_entries,
        site_url="https://host.example.com/repo",
        site_base="/repo",
    )
    build(cfg)
    idx = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="https://host.example.com/repo/category/tech.html"' in idx
    detail = (cfg.out_dir / "channel" / "example-tech-lounge.html").read_text(
        encoding="utf-8"
    )
    assert 'href="/repo/static/style.css"' in detail
    assert 'href="https://host.example.com/repo/"' in detail  # breadcrumb home


def test_site_base_empty_keeps_root_paths(tmp_path, sample_entries):
    cfg = make_config(tmp_path, sample_entries)
    build(cfg)
    detail = (cfg.out_dir / "channel" / "example-tech-lounge.html").read_text(
        encoding="utf-8"
    )
    assert 'href="/static/style.css"' in detail


def test_search_index_chunks(tmp_path):
    entries = [
        {
            "name": f"Entry {i:04d}",
            "username": f"user_{i:05d}",
            "type": "group",
            "category": "C",
            "description": f"Description for entry {i}",
            "tags": ["x"],
        }
        for i in range(50)
    ]
    cfg = make_config(tmp_path, entries, search_chunk=20)
    stats = build(cfg)
    assert stats["search_indexed"] == 50
    manifest = json.loads((cfg.out_dir / "search" / "index.json").read_text())
    assert manifest["count"] == 50
    assert len(manifest["chunks"]) == 3  # 50 / 20
    rows = json.loads(
        (cfg.out_dir / "search" / manifest["chunks"][0]).read_text(encoding="utf-8")
    )
    assert len(rows) == 20
    assert rows[0][2] == "group"  # type field position


def test_config_bad_per_page():
    with pytest.raises(BuildError, match="PER_PAGE"):
        load_config(env={"PER_PAGE": "zero", "TGLITE_BASE": "/tmp"})


def test_config_bad_per_page_negative():
    with pytest.raises(BuildError, match="PER_PAGE"):
        load_config(env={"PER_PAGE": "-5", "TGLITE_BASE": "/tmp"})


def test_load_config_env_override(tmp_path):
    cfg = load_config(
        env={
            "TGLITE_BASE": str(tmp_path),
            "SITE_NAME": "Custom",
            "SITE_URL": "https://x.example.com/base/",
            "SITE_BASE": "/base/",
            "PER_PAGE": "50",
            "SITEMAP_MAX_URLS": "600",
            "SEARCH_CHUNK": "150",
        }
    )
    assert cfg.site_name == "Custom"
    assert cfg.site_url == "https://x.example.com/base"  # trailing slash stripped
    assert cfg.site_base == "/base"
    assert cfg.per_page == 50
    assert cfg.sitemap_max_urls == 600
    assert cfg.search_chunk == 150
