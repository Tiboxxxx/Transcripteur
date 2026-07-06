#!/usr/bin/env python3
"""Tests unitaires des fonctions pures de app.py (sans audio ni API).

Utilisation : python3 test_app_units.py  (ou pytest test_app_units.py)
"""

import re
import sys
import tempfile
from pathlib import Path

from app import (
    clean_segment_text,
    default_capture_name,
    group_into_paragraphs,
    load_config,
    reset_stats_if_new_month,
    slugify_title,
    unique_path,
)


def test_clean_segment_text_fillers():
    assert clean_segment_text("euh bonjour à tous hein") == "Bonjour à tous"
    assert clean_segment_text("Hum, alors on commence voilà") == "Alors on commence"


def test_clean_segment_text_dedup():
    assert clean_segment_text("le le machine learning") == "Le machine learning"


def test_clean_segment_text_empty():
    assert clean_segment_text("") == ""
    assert clean_segment_text("euh hum") == ""


def test_group_into_paragraphs():
    segments = [
        {"start": 0.0, "end": 2.0, "text": "a"},
        {"start": 2.5, "end": 4.0, "text": "b"},   # écart 0.5 → même paragraphe
        {"start": 8.0, "end": 9.0, "text": "c"},   # écart 4.0 → nouveau paragraphe
    ]
    paragraphs = group_into_paragraphs(segments, gap=3.0)
    assert len(paragraphs) == 2
    assert [s["text"] for s in paragraphs[0]] == ["a", "b"]
    assert [s["text"] for s in paragraphs[1]] == ["c"]
    assert group_into_paragraphs([]) == []


def test_load_config_returns_dict():
    assert isinstance(load_config(), dict)


def test_default_capture_name_format():
    assert re.fullmatch(r"capture_\d{4}-\d{2}-\d{2}_\d{2}h\d{2}", default_capture_name())


def test_unique_path():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "note.md"
        assert unique_path(path) == path
        path.write_text("x")
        assert unique_path(path) == Path(tmp) / "note_2.md"
        (Path(tmp) / "note_2.md").write_text("x")
        assert unique_path(path) == Path(tmp) / "note_3.md"


def test_reset_stats_new_month():
    old = {"month": "2026-06", "total_tokens": 5000, "total_cost": 1.2,
           "transcriptions": 3, "monthly_limit_tokens": 2_000_000}
    fresh = reset_stats_if_new_month(old, "2026-07")
    assert fresh["month"] == "2026-07"
    assert fresh["total_tokens"] == 0
    assert fresh["transcriptions"] == 0
    assert fresh["monthly_limit_tokens"] == 2_000_000

    same = reset_stats_if_new_month(fresh, "2026-07")
    assert same["total_tokens"] == 0
    kept = reset_stats_if_new_month({"month": "2026-07", "total_tokens": 42}, "2026-07")
    assert kept["total_tokens"] == 42


def test_slugify_title():
    assert slugify_title("Les 5 étapes de l'IA en 2026 !") == "Les_5_étapes_de_lIA_en_2026"
    assert slugify_title("a" * 100) == "a" * 60
    assert slugify_title("   ") == ""


if __name__ == "__main__":
    failures = 0
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                print(f"[OK] {name}")
            except AssertionError as error:
                failures += 1
                print(f"[FAIL] {name} : {error}")
    print(f"\n=== {'PASSED' if failures == 0 else f'{failures} FAILED'} ===")
    sys.exit(1 if failures else 0)
