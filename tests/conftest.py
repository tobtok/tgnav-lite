"""Shared pytest helpers: build isolated sites in tmp dirs."""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from generator import build as build_mod  # noqa: E402


def make_config(tmp_path: Path, entries: list[dict], **overrides) -> build_mod.Config:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "items.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    defaults = dict(
        data_dir=data_dir,
        tpl_dir=REPO / "templates",
        static_dir=REPO / "static",
        out_dir=tmp_path / "dist",
        site_name="Test Directory",
        site_url="https://test.example.com",
        site_base="",
        per_page=200,
        sitemap_max_urls=45000,
        search_chunk=4000,
        og_image="",
    )
    defaults.update(overrides)
    return build_mod.Config(**defaults)


@pytest.fixture
def sample_entries() -> list[dict]:
    return [
        {
            "name": "Example Tech Lounge",
            "username": "example_tech_lounge",
            "type": "channel",
            "category": "Tech",
            "description": "Daily news and discussion about technology.",
            "members": 12345,
            "tags": ["tech", "news"],
            "added": "2026-01-15",
        },
        {
            "name": "Movie Club",
            "username": "example_movie_club",
            "type": "group",
            "category": "Movies",
            "description": "What did you watch this week?",
            "members": 4200,
            "tags": ["movies"],
            "added": "2026-02-01",
        },
    ]
