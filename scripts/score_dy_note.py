#!/usr/bin/env python3
"""Score a generated DyNote learning note against note_budget.json."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def visible_text_chars(markdown: str) -> int:
    text = re.sub(r"```.*?```", "", markdown, flags=re.S)
    text = re.sub(r"^[ \t]*\[[^\]]+\]:\s+\S+.*$", "", text, flags=re.M)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[#>\-\*\|\s:]+", "", text, flags=re.M)
    text = re.sub(r"\s+", "", text)
    return len(text)


def status_for(actual: int, low: int, high: int) -> str:
    if actual < low:
        return "too_short"
    if actual > high:
        return "too_long"
    return "ok"


def score_note(out_dir: Path, note_path: Path) -> dict[str, Any]:
    budget_path = out_dir / "note_budget.json"
    budget = read_json(budget_path)
    note = note_path.read_text(encoding="utf-8", errors="replace")
    actual_chars = visible_text_chars(note)
    low = int(budget.get("recommended_note_chars_min") or 0)
    high = int(budget.get("recommended_note_chars_max") or 0)
    transcript_chars = int(budget.get("transcript_chars") or 0)
    duration_minutes = float(budget.get("duration_minutes") or 0)
    return {
        "note_path": str(note_path),
        "out_dir": str(out_dir),
        "actual_note_chars": actual_chars,
        "recommended_note_chars_min": low,
        "recommended_note_chars_max": high,
        "status": status_for(actual_chars, low, high),
        "quality_multiplier": budget.get("quality_multiplier"),
        "quality_metrics": budget.get("quality_metrics"),
        "actual_compression_ratio": round(actual_chars / transcript_chars, 4) if transcript_chars else None,
        "target_compression_ratio_min": budget.get("target_compression_ratio_min"),
        "target_compression_ratio_max": budget.get("target_compression_ratio_max"),
        "note_chars_per_minute": round(actual_chars / duration_minutes, 3) if duration_minutes else None,
        "subtitle_chars_per_minute": budget.get("subtitle_chars_per_minute"),
        "granularity": budget.get("granularity"),
        "writing_guidance": budget.get("writing_guidance"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a DyNote Markdown learning note against note_budget.json.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--note-path", required=True, type=Path)
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    result = score_note(args.out_dir, args.note_path)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
