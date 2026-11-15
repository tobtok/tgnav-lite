"""Core build behaviour: data validation, slugs, output structure."""

import json
import re

import pytest

from generator import build as build_mod
from generator.build import BuildError, build, slugify, unique_slug

from conftest import make_config


# ---------- slugify / unique_slug ----------

def test_slugify_ascii():
    assert slugify("Example Tech Lounge") == "example-tech-lounge"


def test_slugify_cjk_preserved():
    assert slugify("中文技术群") == "中文技术群"


def test_slugify_mixed_cjk():
    assert slugify("TG 中文") == "tg-中文"


def test_slugify_symbols_fall_back_to_hash():
    slug = slugify("🎉🚀")
    assert slug and re.fullmatch(r"[0-9a-f]{10}", slug)


def test_unique_slug_collision():
    taken = set()
    assert unique_slug("abc", taken) == "abc"
    assert unique_slug("abc", taken) == "abc-2"
    assert unique_slug("abc", taken) == "abc-3"


# ---------- data validation ----------

def test_missing_required_field(tmp_path):
    cfg = make_config(tmp_path, [{"name": "X", "username": "abc_xyz"}])
    with pytest.raises(BuildError, match="missing required field 'type'"):
        build(cfg)


def test_invalid_username_rejected(tmp_path):
    cfg = make_config(
        tmp_path,
        [{"name": "X", "username": "bad space!", "type": "group", "category": "C"}],
    )
    with pytest.raises(BuildError, match="invalid Telegram username"):
        build(cfg)


def test_duplicate_username_case_insensitive(tmp_path, tmp_path_factory):
    entries = [
        {"name": "A", "username": "Tech_Lounge", "type": "group", "category": "C"},
        {"name": "B", "username": "tech_lounge", "type": "group", "category": "C"},
    ]
    cfg = make_config(tmp_path_factory.mktemp("dup"), entries)
    with pytest.raises(BuildError, match="case-insensitive match"):
        build(cfg)


def test_original_username_case_preserved(tmp_path):
    cfg = make_config(
        tmp_path,
        [
            {
                "name": "A",
                "username": "My_Channel_Name",
                "type": "channel",
                "category": "C",
            }
        ],
    )
    build(cfg)
    html = (cfg.out_dir / "channel" / "my-channel-name.html").read_text(encoding="utf-8")
    assert "@My_Channel_Name" in html


def test_bad_members_value(tmp_path):
    cfg = make_config(
        tmp_path,
        [
            {
                "name": "A",
                "username": "abc_xyz",
                "type": "group",
                "category": "C",
                "members": "12k",
            }
        ],
    )
    with pytest.raises(BuildError, match="'members' must be a number"):
        build(cfg)


def test_bad_added_date(tmp_path):
    cfg = make_config(
        tmp_path,
        [
            {
                "name": "A",
                "username": "abc_xyz",
                "type": "group",
                "category": "C",
                "added": "15/01/2026",
            }
        ],
    )
    with pytest.raises(BuildError, match="ISO date"):
        build(cfg)


def test_invalid_json_clear_error(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "broken.json").write_text('{"a": 1', encoding="utf-8")
    cfg = make_config(tmp_path, [])
    # overwrite generated file with broken json
    (data_dir / "items.json").unlink(missing_ok=True)
    with pytest.raises(BuildError, match="invalid JSON"):
        build(cfg)


def test_empty_data_error(tmp_path):
    cfg = make_config(tmp_path, [])
    (cfg.data_dir / "items.json").write_text("[]", encoding="utf-8")
    with pytest.raises(BuildError, match="contain no entries"):
        build(cfg)


# ---------- structure & stability ----------

def test_build_outputs(sample_entries, tmp_path):
    cfg = make_config(tmp_path, sample_entries)
    stats = build(cfg)
    assert stats["entries"] == 2
    assert stats["pages"] >= 4  # 2 detail + 2 category + index + 404
    for path in (
        "index.html",
        "404.html",
        "sitemap.xml",
        "robots.txt",
        "channel/example-tech-lounge.html",
        "group/example-movie-club.html",
        "category/tech.html",
        "category/movies.html",
        "search/index.json",
    ):
        assert (cfg.out_dir / path).exists(), f"missing {path}"


def test_detail_slug_stable_when_new_same_name_added(tmp_path, tmp_path_factory):
    """A new entry with the same display name must not shift the old URL."""
    e1 = {"name": "Cool Group", "username": "zzz_cool", "type": "group", "category": "C"}
    cfg1 = make_config(tmp_path, [e1])
    build(cfg1)
    old_html = (cfg1.out_dir / "group" / "zzz-cool.html").read_text(encoding="utf-8")
    assert "@zzz_cool" in old_html

    # same display name, different username — must NOT touch the old URL
    e2 = {
        "name": "Cool Group",
        "username": "aaa_cool",
        "type": "group",
        "category": "C",
        "added": "2027-01-01",
    }
    cfg2 = make_config(tmp_path_factory.mktemp("b"), [e2, e1])
    stats = build(cfg2)
    assert stats["entries"] == 2
    # old entry keeps its username-derived URL
    page = (cfg2.out_dir / "group" / "zzz-cool.html").read_text(encoding="utf-8")
    assert "@zzz_cool" in page
    assert (cfg2.out_dir / "group" / "aaa-cool.html").exists()


def test_same_name_entries_both_present(tmp_path):
    entries = [
        {"name": "Same", "username": "same_one", "type": "group", "category": "C"},
        {"name": "Same", "username": "same_two", "type": "channel", "category": "C"},
    ]
    cfg = make_config(tmp_path, entries)
    build(cfg)
    assert (cfg.out_dir / "group" / "same-one.html").exists()
    assert (cfg.out_dir / "channel" / "same-two.html").exists()


def test_mixed_types_in_category(tmp_path):
    entries = [
        {"name": "A", "username": "abc_channel", "type": "channel", "category": "Mix"},
        {"name": "B", "username": "abc_group", "type": "group", "category": "Mix"},
    ]
    cfg = make_config(tmp_path, entries)
    build(cfg)
    cat = (cfg.out_dir / "category" / "mix.html").read_text(encoding="utf-8")
    assert "/channel/abc-channel.html" in cat
    assert "/group/abc-group.html" in cat


def test_chinese_entries_build(tmp_path):
    entries = [
        {
            "name": "中文技术交流群",
            "username": "cn_tech_chat",
            "type": "group",
            "category": "技术",
            "description": "讨论中文技术话题，包含特殊字符 & < > \" ' !",
            "tags": ["中文", "标签"],
        }
    ]
    cfg = make_config(tmp_path, entries)
    build(cfg)
    detail = list((cfg.out_dir / "group").glob("*.html"))
    assert len(detail) == 1
    html = detail[0].read_text(encoding="utf-8")
    assert "中文技术交流群" in html
    assert "cn-tech-chat" in detail[0].name
    cat = list((cfg.out_dir / "category").glob("*.html"))
    assert cat, "chinese category page missing"


def test_build_failure_preserves_existing_dist(tmp_path, sample_entries):
    cfg = make_config(tmp_path, sample_entries)
    build(cfg)
    good = (cfg.out_dir / "index.html").read_text(encoding="utf-8")
    # now poison the data
    (cfg.data_dir / "items.json").write_text(
        json.dumps([{"name": "bad", "username": "!!!", "type": "x", "category": "y"}]),
        encoding="utf-8",
    )
    with pytest.raises(BuildError):
        build(cfg)
    # dist untouched
    assert (cfg.out_dir / "index.html").read_text(encoding="utf-8") == good


def test_no_staging_or_old_left_behind(tmp_path, sample_entries):
    cfg = make_config(tmp_path, sample_entries)
    build(cfg)
    siblings = [p.name for p in cfg.out_dir.parent.iterdir()]
    assert "dist-staging" not in siblings
    assert "dist-old" not in siblings
