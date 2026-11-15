"""Build performance benchmark: 1k / 10k / 50k synthetic entries.

Run manually:  python tests/bench.py [tmp_root]
Uses only synthetic data; never touches real production data.

Wall time is measured without allocation tracking (tracemalloc slows Jinja
rendering by an order of magnitude and would give misleading numbers).
Peak memory is sampled from the process working set via psapi.
"""

import ctypes
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.build import Config, build  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CATEGORIES = [f"Cat{i % 60}" for i in range(60)]
WORDS = ["tech", "news", "movies", "crypto", "music", "travel", "games", "china", "trading"]


def synthetic_entries(n: int) -> list[dict]:
    entries = []
    for i in range(n):
        entries.append(
            {
                "name": f"Channel {i:07d} {WORDS[i % len(WORDS)]}",
                "username": f"bench_user_{i:07d}",
                "type": ["group", "channel"][i % 2],
                "category": CATEGORIES[i % len(CATEGORIES)],
                "description": (
                    f"Benchmark entry {i} about {WORDS[i % len(WORDS)]} with enough "
                    "text to look like a real description for rendering purposes."
                ),
                "members": 1000 + (i * 37) % 90000,
                "tags": [WORDS[i % len(WORDS)], "bench"],
                "added": f"2026-{1 + i % 12:02d}-{1 + i % 28:02d}",
            }
        )
    return entries


def _peak_memory_mb() -> float:
    """Peak process working set in MB (Windows, via psutil)."""
    try:
        import psutil

        return psutil.Process().memory_info().peak_wset / 1e6
    except Exception:
        return 0.0


def run(n: int, tmp_root: Path) -> dict:
    data_dir = tmp_root / f"data-{n}"
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = data_dir / "items.json"
    if not payload.exists():
        payload.write_text(json.dumps(synthetic_entries(n)), encoding="utf-8")

    cfg = Config(
        data_dir=data_dir,
        tpl_dir=REPO / "templates",
        static_dir=REPO / "static",
        out_dir=tmp_root / f"dist-{n}",
        site_name="Bench",
        site_url="https://bench.example.com",
        site_base="",
        per_page=200,
        sitemap_max_urls=45000,
        search_chunk=4000,
    )
    t0 = time.perf_counter()
    stats = build(cfg)
    elapsed = time.perf_counter() - t0
    return {**stats, "seconds": round(elapsed, 2), "peak_mb": round(_peak_memory_mb(), 1)}

if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / ".bench"
    root.mkdir(parents=True, exist_ok=True)
    print(f"{'entries':>8} {'pages':>7} {'seconds':>8} {'peak MB':>8}", flush=True)
    for n in (1000, 10000, 50000):
        r = run(n, root)
        print(f"{r['entries']:>8} {r['pages']:>7} {r['seconds']:>8} {r['peak_mb']:>8}", flush=True)
