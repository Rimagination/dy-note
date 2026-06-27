#!/usr/bin/env python3
"""Compute a DyNote learning-note budget from extracted raw material."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def clamp(value: float, low: int, high: int) -> int:
    return int(max(low, min(high, round(value))))


def clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def visible_text_chars(text: str) -> int:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\s+", "", text)
    return len(text)


def as_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    mult = 1.0
    if text.endswith("万"):
        mult = 10000.0
        text = text[:-1]
    elif text.endswith("亿"):
        mult = 100000000.0
        text = text[:-1]
    try:
        return float(text) * mult
    except ValueError:
        return 0.0


def first_number(data: dict[str, Any], names: list[str]) -> int:
    for name in names:
        if name in data:
            value = int(as_number(data.get(name)))
            if value > 0:
                return value
    return 0


def flatten_stats(metadata: dict[str, Any]) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for key in ("statistics", "stat", "stats", "interaction_stats"):
        value = metadata.get(key)
        if isinstance(value, dict):
            stats.update(value)
    stats.update({key: value for key, value in metadata.items() if re.search(r"(count|num|view|like|digg|share|comment|collect|favorite|play)", key, re.I)})
    return stats


def normalized_log_score(value: float, reference: float) -> float:
    if value <= 0 or reference <= 0:
        return 0.0
    return clamp_float(math.log1p(value) / math.log1p(reference), 0.0, 1.0)


def extract_quality_metrics(metadata: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    stats = flatten_stats(metadata)
    like = first_number(stats, ["digg_count", "like_count", "like", "likes", "digg"])
    collect = first_number(stats, ["collect_count", "favorite_count", "favorites", "collect"])
    comment = first_number(stats, ["comment_count", "comments", "reply", "reply_count"])
    share = first_number(stats, ["share_count", "shares", "share"])
    play = first_number(stats, ["play_count", "view_count", "views", "play", "view"])

    published_raw = metadata.get("create_time") or metadata.get("publish_time") or metadata.get("published_at")
    published_at = None
    days_since_publish = None
    now = now or datetime.now(timezone.utc)
    if published_raw:
        try:
            ts = as_number(published_raw)
            if ts > 100000000000:
                ts = ts / 1000
            published_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            published_at = published_dt.date().isoformat()
            days_since_publish = max(0, (now.date() - published_dt.date()).days)
        except (OSError, OverflowError, ValueError):
            published_at = str(published_raw)

    age_days = max(days_since_publish or 0, 1)
    weighted_engagement = like + collect * 1.5 + comment * 1.8 + share * 1.6
    engagement_rate = weighted_engagement / play if play else 0.0
    collect_rate = collect / play if play else 0.0
    discussion_rate = comment / play if play else 0.0
    play_per_day = play / age_days if play and published_at else 0.0
    engagement_per_day = weighted_engagement / age_days if published_at else 0.0

    if play:
        engagement_rate_score = normalized_log_score(engagement_rate * 1000, 80)
        collect_rate_score = normalized_log_score(collect_rate * 1000, 35)
        discussion_score = normalized_log_score(discussion_rate * 1000, 18)
        velocity_score = normalized_log_score(play_per_day, 50000)
        engagement_velocity_score = normalized_log_score(engagement_per_day, 5000)
        quality_score = (
            engagement_rate_score * 0.32
            + collect_rate_score * 0.18
            + discussion_score * 0.14
            + velocity_score * 0.16
            + engagement_velocity_score * 0.20
        )
    else:
        like_score = normalized_log_score(like, 5000)
        collect_score = normalized_log_score(collect, 1500)
        discussion_score = normalized_log_score(comment, 800)
        share_score = normalized_log_score(share, 500)
        quality_score = like_score * 0.30 + collect_score * 0.25 + discussion_score * 0.25 + share_score * 0.20

    quality_multiplier = clamp_float(0.85 + quality_score * 0.55, 0.85, 1.4)
    if quality_score >= 0.72:
        quality_tier = "high"
    elif quality_score >= 0.45:
        quality_tier = "medium"
    else:
        quality_tier = "low"

    return {
        "available": bool(like or collect or comment or share or play),
        "published_at": published_at,
        "days_since_publish": days_since_publish,
        "play": play,
        "like": like,
        "collect": collect,
        "comment": comment,
        "share": share,
        "weighted_engagement": round(weighted_engagement, 3),
        "engagement_rate": round(engagement_rate, 6) if play else None,
        "collect_rate": round(collect_rate, 6) if play else None,
        "discussion_rate": round(discussion_rate, 6) if play else None,
        "play_per_day": round(play_per_day, 3) if play and published_at else None,
        "weighted_engagement_per_day": round(engagement_per_day, 3) if published_at else None,
        "quality_score": round(quality_score, 4),
        "quality_tier": quality_tier,
        "quality_multiplier": round(quality_multiplier, 3),
        "quality_basis": "点赞、收藏、评论、分享、播放量和发布距今天数的综合信号；缺少播放量时退化为互动绝对量信号",
    }


def duration_from(metadata: dict[str, Any], segments: list[dict[str, Any]]) -> float:
    raw = metadata.get("duration_ms") or metadata.get("duration") or metadata.get("duration_seconds")
    duration = as_number(raw)
    if duration > 1000:
        duration = duration / 1000
    if duration <= 0:
        ends = [as_number(seg.get("end")) for seg in segments if isinstance(seg, dict)]
        duration = max(ends or [0.0])
    return duration


def count_comments(comments_json: Path | None) -> int:
    if not comments_json or not comments_json.exists():
        return 0
    data = read_json(comments_json)
    if isinstance(data, dict):
        for key in ("row_count", "total_reported", "main_comment_count"):
            value = int(as_number(data.get(key)))
            if value > 0:
                return value
        rows = data.get("rows")
        if isinstance(rows, list):
            return len(rows)
        comments = data.get("comments")
        if isinstance(comments, list):
            return len(comments)
    if isinstance(data, list):
        return len(data)
    return 0


def auto_comments_json(out_dir: Path) -> Path | None:
    primary_patterns = [
        "douyin_comments_*_full.json",
        "douyin_comments_*_sample.json",
    ]
    fallback_patterns = [
        "douyin_comments_*_main_only_full.json",
        "douyin_comments_*_main_only_sample.json",
        "*comments*.json",
    ]
    matches = [
        path
        for pattern in primary_patterns
        for path in sorted(out_dir.glob(pattern))
        if "_main_only_" not in path.name
    ]
    matches.extend(path for pattern in fallback_patterns for path in sorted(out_dir.glob(pattern)))
    for path in matches:
        if path.name not in {"douyin_ai_brief.json", "doubao_brief.json", "note_budget.json"}:
            return path
    return None


def infer_granularity(duration_minutes: float, transcript_chars: int, quality_tier: str) -> tuple[str, str]:
    if duration_minutes >= 25 or transcript_chars >= 12000:
        base = ("medium_deep_dive", "按章节/主题写，保留论证链、方法步骤、关键例子、反例和可操作清单。")
    elif duration_minutes >= 8 or transcript_chars >= 4500:
        base = ("structured_explainer", "保留结构、关键论点、步骤和代表证据，不要压成三段摘要。")
    elif duration_minutes >= 3 or transcript_chars >= 1500:
        base = ("short_deep_note", "写清核心观点、关键细节、可迁移方法和适用边界。")
    else:
        base = ("micro_video", "提炼核心信息、场景、亮点和少量实践启发，避免过度扩写。")
    if quality_tier == "high":
        return base[0] + "_high_interaction", base[1] + " 因互动质量高，额外补充受众反馈、评论需求和可复用选题角度。"
    return base


def assess_visual_dependency(duration_minutes: float, transcript_chars: int, segment_count: int) -> dict[str, Any]:
    density = transcript_chars / duration_minutes if duration_minutes else None
    warnings: list[str] = []
    reasons: list[str] = []
    suggested_next_steps: list[str] = []
    risk = "low"

    if duration_minutes >= 3 and transcript_chars <= 240:
        risk = "high"
        reasons.append("long_video_sparse_transcript")
        warnings.append(
            "视频较长但转写文本明显很少，核心信息可能在画面、贴纸/画面文字、操作演示、音乐氛围或无对白片段中。不要只依赖本地自动语音识别写完整笔记。"
        )
    elif duration_minutes >= 5 and density is not None and density < 120:
        risk = "high"
        reasons.append("low_transcript_density")
        warnings.append(
            "转写密度低于长视频常见讲述密度，建议补抖音内置 AI 画面理解、关键帧或 OCR 后再写细笔记。"
        )
    elif duration_minutes >= 3 and density is not None and density < 180:
        risk = "medium"
        reasons.append("medium_low_transcript_density")
        warnings.append(
            "转写文本偏少，适合先写快读；如果用户要详细拆解，应补画面证据或明确覆盖范围。"
        )

    if duration_minutes >= 1 and transcript_chars == 0:
        risk = "high"
        reasons.append("no_transcript_text")
        warnings.append(
            "有视频时长但没有可用转写文本，不能把页面简介或标签当完整内容。需要抖音内置 AI 快读、关键帧/OCR、字幕轨或重新转写。"
        )

    if segment_count <= 1 and duration_minutes >= 5:
        if risk == "low":
            risk = "medium"
        reasons.append("few_segments_for_duration")
        warnings.append(
            "长视频只有极少结构化片段，时间线证据不足；写章节化笔记前应补分段信息或视觉检查。"
        )

    if risk in {"medium", "high"}:
        suggested_next_steps = [
            "先把独立字幕轨或本地自动语音识别转写作为事实主干；不要让抖音问 AI 或豆包代替完整字幕。",
            "用抖音网页版问 AI / 识别画面补充画面、贴纸文字、商品/场景和无对白片段。",
            "如果抖音问 AI 不可用或回答质量弱，再用豆包作为备用快读或视觉假设，并明确标注证据等级。",
            "对发布级笔记、事实核查或脚本拆解，继续补关键帧、OCR、评论或外部来源。"
        ]

    return {
        "risk": risk,
        "needs_visual_review": risk in {"medium", "high"},
        "reasons": reasons,
        "warnings": warnings,
        "suggested_next_steps": suggested_next_steps,
        "hallucination_guard": "字幕/ASR 是内容事实主干；抖音问 AI 和豆包只能作为视觉补充、快读草稿或待核验假设，不能当作完整字幕或逐帧事实。",
        "guidance": (
            "先以字幕/ASR 固定事实主干，再补抖音内置 AI 画面理解、关键帧/OCR 或人工画面检查；豆包只在抖音 AI 不可用时作为备用假设。"
            if risk == "high"
            else "如需详细拆解，补抖音问 AI、关键帧或 OCR 视觉证据；快读必须明确只基于现有转写、元数据和低等级视觉假设。"
            if risk == "medium"
            else "当前转写密度未显示明显视觉依赖风险。"
        ),
        "density_chars_per_minute": round(density, 3) if density is not None else None,
    }


def compute_budget(
    out_dir: Path,
    metadata_path: Path | None = None,
    transcript_path: Path | None = None,
    segments_path: Path | None = None,
    comments_json: Path | None = None,
) -> dict[str, Any]:
    metadata_path = metadata_path or out_dir / "metadata.json"
    transcript_path = transcript_path or out_dir / "transcript.txt"
    segments_path = segments_path or out_dir / "segments.json"
    metadata = read_json(metadata_path) if metadata_path.exists() else {}
    transcript = transcript_path.read_text(encoding="utf-8", errors="replace") if transcript_path.exists() else ""
    segments = read_json(segments_path) if segments_path.exists() else []
    if not isinstance(segments, list):
        segments = []
    comments_json = comments_json or auto_comments_json(out_dir)
    comment_records = count_comments(comments_json)

    transcript_chars = visible_text_chars(transcript)
    duration_seconds = duration_from(metadata, segments)
    duration_minutes = duration_seconds / 60 if duration_seconds else 0.0
    segment_count = len(segments)
    evidence_blocks = max(1 if transcript_chars else 0, math.ceil(transcript_chars / 320), math.ceil(segment_count / 8))
    quality_metrics = extract_quality_metrics(metadata)
    quality_multiplier = float(quality_metrics.get("quality_multiplier") or 1.0)

    base_target_min = clamp(
        500 + duration_minutes * 60 + transcript_chars * 0.08 + evidence_blocks * 8 + min(comment_records, 300) * 3,
        800,
        45000,
    )
    target_min = clamp(base_target_min * quality_multiplier, 800, 65000)
    target_max = clamp(target_min * 1.45, 1200, 90000)
    quick_target = clamp(target_min * 0.45, 600, 12000)
    deep_target = clamp(target_max * 1.55, target_max, 120000)
    granularity, writing_guidance = infer_granularity(duration_minutes, transcript_chars, str(quality_metrics.get("quality_tier") or "low"))
    visual_dependency = assess_visual_dependency(duration_minutes, transcript_chars, segment_count)
    if visual_dependency["needs_visual_review"]:
        writing_guidance += " " + str(visual_dependency["guidance"])

    budget = {
        "content_type": "douyin_video",
        "out_dir": str(out_dir),
        "duration_seconds": round(duration_seconds, 3),
        "duration_minutes": round(duration_minutes, 3),
        "transcript_chars": transcript_chars,
        "segment_count": segment_count,
        "transcript_density_chars_per_minute": round(transcript_chars / duration_minutes, 3) if duration_minutes else None,
        "subtitle_chars_per_minute": round(transcript_chars / duration_minutes, 3) if duration_minutes else None,
        "visual_dependency": visual_dependency,
        "evidence_warnings": visual_dependency["warnings"],
        "evidence_blocks_estimate": evidence_blocks,
        "comment_records": comment_records,
        "comments_json": str(comments_json) if comments_json else None,
        "base_note_chars_min": base_target_min,
        "quality_multiplier": round(quality_multiplier, 3),
        "quality_metrics": quality_metrics,
        "recommended_note_chars_min": target_min,
        "recommended_note_chars_max": target_max,
        "quick_note_chars": quick_target,
        "deep_note_chars": deep_target,
        "target_compression_ratio_min": round(target_min / transcript_chars, 4) if transcript_chars else None,
        "target_compression_ratio_max": round(target_max / transcript_chars, 4) if transcript_chars else None,
        "granularity": granularity,
        "writing_guidance": writing_guidance,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return budget


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute DyNote note_budget.json from extracted raw materials.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--metadata-json", type=Path)
    parser.add_argument("--transcript-txt", type=Path)
    parser.add_argument("--segments-json", type=Path)
    parser.add_argument("--comments-json", type=Path)
    parser.add_argument("--out", type=Path, help="Defaults to <out-dir>/note_budget.json")
    args = parser.parse_args()

    budget = compute_budget(
        out_dir=args.out_dir,
        metadata_path=args.metadata_json,
        transcript_path=args.transcript_txt,
        segments_path=args.segments_json,
        comments_json=args.comments_json,
    )
    out_path = args.out or args.out_dir / "note_budget.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(budget, ensure_ascii=False, indent=2)
    out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
