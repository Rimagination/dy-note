#!/usr/bin/env python3
"""Inspect DyNote artifacts and recommend the next non-duplicative step."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


COMPLEX_MODES = {
    "comment-insight",
    "account-analysis",
    "topic-research",
    "script-mining",
    "commerce-analysis",
    "fact-check",
    "knowledge-archive",
}


def file_info(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "path": str(path),
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
    }


def newest(paths: list[Path]) -> float:
    return max((path.stat().st_mtime for path in paths if path.exists()), default=0.0)


def first_match(out_dir: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        matches = sorted(out_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def inspect(out_dir: Path, mode: str) -> dict[str, Any]:
    files = {
        "analysis_plan": out_dir / "analysis_plan.json",
        "douyin_ai_brief_md": out_dir / "douyin_ai_brief.md",
        "douyin_ai_brief_json": out_dir / "douyin_ai_brief.json",
        "doubao_brief_md": out_dir / "doubao_brief.md",
        "doubao_brief_json": out_dir / "doubao_brief.json",
        "transcript_txt": out_dir / "transcript.txt",
        "transcript_markdown": out_dir / "transcript.cleaned.md",
        "segments_json": out_dir / "segments.json",
        "metadata_json": out_dir / "metadata.json",
        "page_metadata_json": out_dir / "page_metadata.json",
        "note_budget": out_dir / "note_budget.json",
        "learning_note": out_dir / "learning_note.md",
        "note_score": out_dir / "note_score.json",
        "asset_manifest": out_dir / "assets" / "asset_manifest.json",
    }
    comment_file = first_match(out_dir, ["douyin_comments_*_full.json", "*comments*.json", "douyin_comments_*_full.csv", "*comments*.csv"])
    media_file = first_match(out_dir, ["*.mp4", "*.m4a", "*.wav"])
    qwen_file = first_match(out_dir, ["*.qwen3_asr.json"])
    whisper_srt = first_match(out_dir, ["*.srt"])

    present = {name: file_info(path) for name, path in files.items()}
    present["comments"] = file_info(comment_file) if comment_file else {"exists": False}
    present["media_or_audio"] = file_info(media_file) if media_file else {"exists": False}
    present["qwen_result"] = file_info(qwen_file) if qwen_file else {"exists": False}
    present["whisper_srt"] = file_info(whisper_srt) if whisper_srt else {"exists": False}

    has_plan = files["analysis_plan"].exists()
    has_douyin_ai = files["douyin_ai_brief_md"].exists() and files["douyin_ai_brief_json"].exists()
    has_doubao = files["doubao_brief_md"].exists() and files["doubao_brief_json"].exists()
    has_transcript = files["transcript_txt"].exists() and files["segments_json"].exists()
    has_budget = files["note_budget"].exists()
    has_note = files["learning_note"].exists()
    has_score = files["note_score"].exists()
    has_assets = files["asset_manifest"].exists()
    has_comments = bool(comment_file and comment_file.exists())

    source_mtime = newest([files["transcript_txt"], files["segments_json"], files["metadata_json"], Path(comment_file) if comment_file else out_dir / "_missing"])
    assets_mtime = newest([files["asset_manifest"]])
    budget_mtime = newest([files["note_budget"]])
    note_mtime = newest([files["learning_note"]])
    score_mtime = newest([files["note_score"]])
    stale_budget = bool(has_budget and source_mtime and budget_mtime < source_mtime)
    stale_score = bool(has_score and note_mtime and score_mtime < max(note_mtime, budget_mtime))
    stale_assets = bool(has_assets and source_mtime and assets_mtime < source_mtime)
    budget_data = read_json_dict(files["note_budget"]) if has_budget else {}
    visual_dependency = budget_data.get("visual_dependency") if isinstance(budget_data.get("visual_dependency"), dict) else {}
    visual_warnings = visual_dependency.get("warnings") if isinstance(visual_dependency, dict) else []
    if not isinstance(visual_warnings, list):
        visual_warnings = []

    reusable = []
    next_steps = []
    avoid = []
    warnings = [str(item) for item in visual_warnings if item]

    if has_plan:
        reusable.append("analysis_plan.json")
    elif mode in COMPLEX_MODES:
        next_steps.append("create_analysis_plan")

    if has_douyin_ai:
        reusable.append("douyin_ai_brief")
        avoid.append("do not rerun Douyin Web AI unless source URL changed, page AI was weak, or frame evidence is needed")

    if has_doubao:
        reusable.append("doubao_brief")
        avoid.append("do not rerun Doubao unless Douyin Web AI is unavailable/weak or objective/share text changed")

    if has_transcript:
        reusable.append("transcript")
        avoid.append("do not rerun ASR unless source audio changed or higher-fidelity transcript is required")
    elif not (has_douyin_ai or has_doubao):
        next_steps.append("run_douyin_web_ai_or_extract_transcript")
    elif mode in {"script-mining", "commerce-analysis", "fact-check"}:
        next_steps.append("extract_transcript_or_use_existing_srt_txt_if_exact_wording_needed")

    if has_comments:
        reusable.append("comments")
        avoid.append("do not refetch comments unless sample scope changed or existing sample is incomplete")
    elif mode == "comment-insight":
        next_steps.append("fetch_comments")

    if has_budget and not stale_budget:
        reusable.append("note_budget")
        if visual_dependency.get("needs_visual_review"):
            next_steps.append("add_visual_evidence_or_warn_sparse_transcript")
    elif has_transcript:
        next_steps.append("compute_note_budget")

    if has_note:
        reusable.append("learning_note.md")
    elif has_budget or has_douyin_ai or has_doubao or has_transcript:
        next_steps.append("write_learning_note_or_task_output")

    if has_score and not stale_score:
        reusable.append("note_score")
    elif has_note and has_budget:
        next_steps.append("score_learning_note")

    if has_assets and (not source_mtime or assets_mtime >= source_mtime):
        reusable.append("assets")
    elif has_transcript or has_comments or has_douyin_ai or has_doubao:
        next_steps.append("archive_assets")

    return {
        "out_dir": str(out_dir),
        "mode": mode,
        "present": present,
        "reusable_artifacts": reusable,
        "stale": {
            "note_budget": stale_budget,
            "note_score": stale_score,
            "assets": stale_assets,
        },
        "warnings": dedupe(warnings),
        "visual_dependency": visual_dependency,
        "recommended_next_steps": dedupe(next_steps),
        "avoid_rework": dedupe(avoid),
        "force_rerun_when": [
            "source URL/share text changed",
            "objective or mode changed",
            "existing artifact is stale, partial, corrupt, or below required evidence tier",
            "user explicitly asks for a higher-fidelity rerun",
        ],
    }


def dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a DyNote output directory and avoid unnecessary reruns.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--mode", default="single-video-note")
    args = parser.parse_args()
    result = inspect(args.out_dir, args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
