#!/usr/bin/env python3
"""Extract clean note-ready text from a Douyin video.

The default network route uses the local web-access CDP proxy and the user's
already-authorized Chrome page. It does not read browser profile files or copy
cookies. Signed media URLs are treated as temporary transport details and are
not written to metadata.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


PROXY = "http://localhost:3456"
DEFAULT_QWEN_MODEL = "Qwen/Qwen3-ASR-0.6B"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


class DouyinTextError(RuntimeError):
    pass


def http_json(method: str, path: str, body: str | None = None, timeout: int = 30) -> Any:
    data = body.encode("utf-8") if body is not None else None
    req = request.Request(
        f"{PROXY}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except error.URLError as exc:
        raise DouyinTextError(f"CDP proxy request failed: {exc}") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DouyinTextError(f"CDP proxy returned non-JSON: {payload[:300]}") from exc


def eval_js(target: str, js: str, timeout: int = 30) -> Any:
    result = http_json("POST", f"/eval?target={parse.quote(target)}", js, timeout=timeout)
    if "error" in result:
        raise DouyinTextError(f"CDP eval failed: {result['error']}")
    if "exceptionDetails" in result:
        details = result.get("exceptionDetails") or {}
        raise DouyinTextError(f"CDP eval exception: {details.get('text', details)}")
    return result.get("value")


def open_target(url: str) -> str:
    result = http_json("GET", f"/new?url={parse.quote(url, safe='')}", timeout=60)
    target = result.get("targetId")
    if not target:
        raise DouyinTextError(f"Could not create browser target: {result}")
    return str(target)


def close_target(target: str) -> None:
    try:
        http_json("GET", f"/close?target={parse.quote(target)}", timeout=10)
    except Exception:
        pass


def extract_first_url(text: str) -> str:
    match = re.search(r"https?://[^\s，。；；、\"'<>]+", text)
    if not match:
        raise DouyinTextError("No URL found in the Douyin share text.")
    return match.group(0).rstrip(").,，。")


def infer_aweme_id(text: str) -> str | None:
    for pattern in (
        r"/(?:note|video)/(\d{10,24})",
        r"(?:aweme_id|modal_id|item_id|group_id)=(\d{10,24})",
        r"\b(\d{16,24})\b",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def parse_timecode(value: str) -> float:
    match = re.match(r"(?:(\d+):)?(\d{2}):(\d{2})[,.](\d{1,3})$", value.strip())
    if not match:
        raise ValueError(f"Invalid SRT timecode: {value}")
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    millis = int(match.group(4).ljust(3, "0")[:3])
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def seconds_to_hhmmss(seconds: float | int | None) -> str:
    if seconds is None:
        return ""
    total = max(0, int(float(seconds)))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_srt_text(text: str) -> list[dict[str, Any]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    blocks = re.split(r"\n\s*\n", normalized)
    segments: list[dict[str, Any]] = []
    for block in blocks:
        lines = [line.strip("\ufeff ") for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if re.fullmatch(r"\d+", lines[0]) and len(lines) > 1:
            lines = lines[1:]
        if not lines or "-->" not in lines[0]:
            continue
        start_raw, end_raw = [part.strip() for part in lines[0].split("-->", 1)]
        content = clean_segment_text(" ".join(lines[1:]))
        if not content:
            continue
        segments.append(
            {
                "index": len(segments) + 1,
                "start": parse_timecode(start_raw),
                "end": parse_timecode(end_raw.split()[0]),
                "text": content,
            }
        )
    return segments


def clean_segment_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_segments_from_whisper_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = []
    for item in data.get("segments") or []:
        text = clean_segment_text(str(item.get("text") or ""))
        if text:
            segments.append(
                {
                    "index": len(segments) + 1,
                    "start": float(item.get("start") or 0),
                    "end": float(item.get("end") or 0),
                    "text": text,
                }
            )
    if not segments and data.get("text"):
        return segments_from_plain_text(str(data["text"]))
    return segments


def segments_from_plain_text(text: str) -> list[dict[str, Any]]:
    lines = [clean_segment_text(line) for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [line for line in lines if line]
    return [{"index": idx + 1, "start": None, "end": None, "text": line} for idx, line in enumerate(lines)]


def sentence_has_terminal(text: str) -> bool:
    return bool(re.search(r"[。！？!?；;：:]$|[.!?]$", text.strip()))


def make_paragraphs(lines: list[str], max_chars: int = 420) -> list[str]:
    paragraphs: list[str] = []
    buf: list[str] = []
    char_count = 0
    for raw in lines:
        line = clean_segment_text(raw)
        if not line:
            continue
        if buf and char_count + len(line) > max_chars:
            paragraphs.append("\n".join(buf).strip())
            buf = [line]
            char_count = len(line)
            continue
        buf.append(line)
        char_count += len(line)
        if char_count >= max_chars * 0.65 and sentence_has_terminal(line):
            paragraphs.append("\n".join(buf).strip())
            buf = []
            char_count = 0
    if buf:
        paragraphs.append("\n".join(buf).strip())
    return paragraphs


def is_cjk_text(text: str) -> bool:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return cjk >= latin


def load_metadata(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_title(metadata: dict[str, Any]) -> str:
    desc = str(metadata.get("desc") or metadata.get("title") or "").strip()
    if desc:
        return desc.split("\n")[0][:80]
    return "抖音视频文本素材"


def normalize_chapter_list(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = metadata.get("chapter_list") or []
    if not isinstance(chapters, list):
        return []
    normalized = []
    for item in chapters:
        if not isinstance(item, dict):
            continue
        start_ms = item.get("timestamp_ms") or item.get("start_time") or item.get("start") or item.get("time")
        try:
            start_sec = float(start_ms) / 1000 if start_ms is not None and float(start_ms) > 1000 else float(start_ms or 0)
        except (TypeError, ValueError):
            start_sec = 0
        normalized.append(
            {
                "time": seconds_to_hhmmss(start_sec),
                "title": item.get("title") or item.get("desc") or item.get("content") or "",
                "desc": item.get("detail") or item.get("abstract") or (item.get("desc") if item.get("title") else ""),
            }
        )
    return normalized


def metadata_source_url(metadata: dict[str, Any], fallback: str | None) -> str:
    return str(metadata.get("source_url") or metadata.get("url") or fallback or "")


def pick_number(data: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        if key not in data:
            continue
        try:
            value = int(float(data.get(key) or 0))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def extract_interaction_stats(detail: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for key in ("statistics", "stats", "stat", "status"):
        value = detail.get(key)
        if isinstance(value, dict):
            candidates.append(value)
    if isinstance(detail, dict):
        candidates.append(detail)
    merged: dict[str, Any] = {}
    for item in candidates:
        for key, value in item.items():
            if re.search(r"(count|num|view|like|digg|share|comment|collect|favorite|play)", str(key), re.I):
                merged[str(key)] = value
    normalized = {
        "digg_count": pick_number(merged, ["digg_count", "like_count", "like", "digg"]),
        "comment_count": pick_number(merged, ["comment_count", "comments", "reply_count", "reply"]),
        "collect_count": pick_number(merged, ["collect_count", "favorite_count", "collect", "favorite"]),
        "share_count": pick_number(merged, ["share_count", "share"]),
        "play_count": pick_number(merged, ["play_count", "view_count", "play", "view"]),
    }
    return {key: value for key, value in normalized.items() if value is not None}


def render_markdown(
    metadata: dict[str, Any],
    paragraphs: list[str],
    segments: list[dict[str, Any]],
    source_url: str | None,
    transcript_source: str,
) -> str:
    title = safe_title(metadata)
    source = metadata_source_url(metadata, source_url)
    raw_author = metadata.get("author")
    author = metadata.get("author_nickname")
    if not author and isinstance(raw_author, dict):
        author = raw_author.get("nickname") or raw_author.get("unique_id")
    if not author and isinstance(raw_author, str):
        author = raw_author
    duration_ms = metadata.get("duration_ms") or metadata.get("duration")
    duration_text = ""
    try:
        duration = float(duration_ms)
        duration_text = seconds_to_hhmmss(duration / 1000 if duration > 1000 else duration)
    except (TypeError, ValueError):
        pass
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    lines = [
        "# 抖音视频文本素材",
        "",
        f"- 标题/描述：{title}",
    ]
    if source:
        lines.append(f"- 来源：{source}")
    if metadata.get("aweme_id"):
        lines.append(f"- 作品 ID：{metadata['aweme_id']}")
    if author:
        lines.append(f"- 作者：{author}")
    if duration_text:
        lines.append(f"- 视频时长：{duration_text}")
    lines.extend(
        [
            f"- 文本来源：{transcript_source}",
            f"- 片段数：{len(segments)}",
            f"- 生成时间：{now}",
            "",
        ]
    )
    abstract = str(metadata.get("chapter_abstract") or "").strip()
    chapters = normalize_chapter_list(metadata)
    if abstract or chapters:
        lines.append("## 页面章节/摘要")
        lines.append("")
        if abstract:
            lines.extend([abstract, ""])
        for chapter in chapters:
            detail = f"：{chapter['desc']}" if chapter.get("desc") else ""
            lines.append(f"- [{chapter['time']}] {chapter.get('title') or '章节'}{detail}")
        lines.append("")
    lines.append("## 文本正文")
    lines.append("")
    lines.append("\n\n".join(paragraphs))
    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def core_outputs_ready(out_dir: Path) -> bool:
    return all((out_dir / name).exists() for name in ("transcript.txt", "segments.json", "metadata.json"))


def newest_mtime(paths: list[Path]) -> float:
    return max((path.stat().st_mtime for path in paths if path.exists()), default=0.0)


def existing_comments_files(out_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("douyin_comments_*_full.json", "*comments*.json"):
        files.extend(path for path in out_dir.glob(pattern) if path.name not in {"douyin_ai_brief.json", "doubao_brief.json", "note_budget.json"})
    return sorted(set(files))


def note_budget_needs_update(out_dir: Path) -> bool:
    budget = out_dir / "note_budget.json"
    if not budget.exists():
        return True
    source_paths = [out_dir / "transcript.txt", out_dir / "segments.json", out_dir / "metadata.json", *existing_comments_files(out_dir)]
    return newest_mtime(source_paths) > budget.stat().st_mtime


def try_write_note_budget(out_dir: Path) -> dict[str, Any]:
    helper = Path(__file__).with_name("compute_note_budget.py")
    if not helper.exists():
        return {"note_budget_error": f"helper not found: {helper}"}
    result = subprocess.run(
        [sys.executable, str(helper), "--out-dir", str(out_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return {"note_budget_error": (result.stderr or result.stdout)[-800:]}
    budget_path = out_dir / "note_budget.json"
    if budget_path.exists():
        return {"note_budget": "note_budget.json"}
    return {"note_budget_error": "compute_note_budget.py completed but note_budget.json was not found"}


def ensure_note_budget(out_dir: Path) -> dict[str, Any]:
    if note_budget_needs_update(out_dir):
        return try_write_note_budget(out_dir)
    return {"note_budget": "note_budget.json", "note_budget_reused": True}


def reuse_existing_outputs(out_dir: Path) -> dict[str, Any]:
    report = load_metadata(out_dir / "metadata.json")
    if not isinstance(report, dict):
        report = {}
    report = dict(report)
    report["reused_existing"] = True
    report.setdefault(
        "outputs",
        {
            "transcript_txt": "transcript.txt",
            "transcript_markdown": "transcript.cleaned.md",
            "segments_json": "segments.json",
        },
    )
    budget_report = ensure_note_budget(out_dir)
    report.update(budget_report)
    if budget_report.get("note_budget"):
        report.setdefault("outputs", {})["note_budget"] = budget_report["note_budget"]
    return report


def build_outputs(
    segments: list[dict[str, Any]],
    out_dir: Path,
    metadata: dict[str, Any] | None,
    source_url: str | None,
    transcript_source: str,
) -> dict[str, Any]:
    if not segments:
        raise DouyinTextError("No transcript text was found.")
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata = dict(metadata or {})
    if source_url and not metadata.get("source_url"):
        metadata["source_url"] = source_url
    lines = [str(seg.get("text") or "") for seg in segments]
    paragraphs = make_paragraphs(lines)
    text = "\n\n".join(paragraphs).strip() + "\n"
    md = render_markdown(metadata, paragraphs, segments, source_url, transcript_source)
    (out_dir / "transcript.txt").write_text(text, encoding="utf-8")
    (out_dir / "transcript.cleaned.md").write_text(md, encoding="utf-8")
    write_json(out_dir / "segments.json", segments)
    sanitized = sanitize_metadata(metadata)
    sanitized.update(
        {
            "transcript_source": transcript_source,
            "segment_count": len(segments),
            "paragraph_count": len(paragraphs),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "outputs": {
                "transcript_txt": "transcript.txt",
                "transcript_markdown": "transcript.cleaned.md",
                "segments_json": "segments.json",
            },
        }
    )
    write_json(out_dir / "metadata.json", sanitized)
    budget_report = try_write_note_budget(out_dir)
    sanitized.update(budget_report)
    if budget_report.get("note_budget"):
        sanitized.setdefault("outputs", {})["note_budget"] = budget_report["note_budget"]
    write_json(out_dir / "metadata.json", sanitized)
    return sanitized


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    blocked = {"media_url", "video_url", "download_url", "play_addr", "bit_rate"}
    clean: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in blocked:
            continue
        if isinstance(value, str) and ("douyinvod.com" in value or "byte" in value and "sign" in value):
            continue
        clean[key] = value
    return clean


def build_from_local_transcript(
    source_path: Path,
    source_kind: str,
    out_dir: Path,
    metadata_path: Path | None,
    source_url: str | None = None,
) -> dict[str, Any]:
    metadata = load_metadata(metadata_path)
    text = source_path.read_text(encoding="utf-8-sig", errors="replace")
    if source_kind == "srt":
        segments = parse_srt_text(text)
        transcript_source = f"local SRT: {source_path.name}"
    elif source_kind == "whisper-json":
        segments = load_segments_from_whisper_json(source_path)
        transcript_source = f"local Whisper JSON: {source_path.name}"
    elif source_kind == "txt":
        segments = segments_from_plain_text(text)
        transcript_source = f"local text: {source_path.name}"
    else:
        raise DouyinTextError(f"Unsupported local transcript type: {source_kind}")
    return build_outputs(segments, out_dir, metadata, source_url, transcript_source)


def build_from_qwen_result(
    result_path: Path,
    out_dir: Path,
    metadata: dict[str, Any] | None,
    source_url: str | None = None,
) -> dict[str, Any]:
    data = json.loads(result_path.read_text(encoding="utf-8-sig"))
    segments: list[dict[str, Any]] = []
    for item in data.get("segments") or []:
        if not isinstance(item, dict):
            continue
        text = clean_segment_text(str(item.get("text") or ""))
        if not text:
            continue
        segments.append(
            {
                "index": len(segments) + 1,
                "start": item.get("start"),
                "end": item.get("end"),
                "text": text,
            }
        )
    if not segments:
        raw_text = str(data.get("text") or "")
        lines = [clean_segment_text(line) for line in raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        lines = [line for line in lines if line]
        segments = [{"index": idx + 1, "start": None, "end": None, "text": line} for idx, line in enumerate(lines)]
    if not segments:
        raise DouyinTextError(f"Qwen result has no text: {result_path}")
    qwen_metadata = dict(metadata or {})
    qwen_metadata["qwen_language"] = data.get("language")
    qwen_metadata["qwen_model"] = data.get("model")
    qwen_metadata["qwen_chunk_seconds"] = data.get("chunk_seconds")
    transcript_source = f"Qwen3-ASR: {data.get('model') or DEFAULT_QWEN_MODEL}"
    return build_outputs(segments, out_dir, qwen_metadata, source_url, transcript_source)


def collect_page_info(target: str) -> dict[str, Any]:
    js = r"""
(() => {
  const text = (sel) => {
    const el = document.querySelector(sel);
    return el ? (el.content || el.textContent || '').trim() : '';
  };
  const url = location.href;
  const title = document.title || '';
  const metaDescription = text('meta[name="description"]') || text('meta[property="og:description"]');
  const ogTitle = text('meta[property="og:title"]');
  const videos = Array.from(document.querySelectorAll('video')).map(v => ({
    src: v.currentSrc || v.src || '',
    duration: Number.isFinite(v.duration) ? v.duration : null,
    poster: v.poster || '',
    readyState: v.readyState
  })).filter(v => v.src);
  const tracks = Array.from(document.querySelectorAll('track')).map(t => ({
    kind: t.kind || '',
    label: t.label || '',
    srclang: t.srclang || '',
    src: t.src || ''
  })).filter(t => t.src);
  const resources = performance.getEntriesByType('resource')
    .map(e => e.name)
    .filter(u => /\.(mp4|m4a|mp3|webm)(\?|$)/i.test(u) || /video|playwm|play_addr/i.test(u))
    .slice(-30);

  const seen = new WeakSet();
  const details = [];
  function scan(obj, depth) {
    if (!obj || typeof obj !== 'object' || depth > 6 || seen.has(obj) || details.length > 8) return;
    seen.add(obj);
    try {
      if ((obj.aweme_id || obj.awemeId || obj.item_id) && (obj.desc || obj.video || obj.author)) {
        details.push(obj);
      }
      for (const key of Object.keys(obj).slice(0, 80)) scan(obj[key], depth + 1);
    } catch (e) {}
  }
  for (const key of Object.keys(window)) {
    if (/INITIAL|RENDER|DATA|STATE|aweme/i.test(key)) {
      try { scan(window[key], 0); } catch (e) {}
    }
  }
  const scripts = Array.from(document.scripts).map(s => s.textContent || '').join('\n');
  const idMatch = url.match(/\/(?:note|video)\/(\d+)/) || scripts.match(/"aweme_id"\s*:\s*"(\d+)"/) || scripts.match(/"awemeId"\s*:\s*"(\d+)"/);
  return {
    url, title, ogTitle, metaDescription, videos, tracks, resources,
    aweme_id: idMatch ? idMatch[1] : '',
    detail: details[0] || null
  };
})()
"""
    value = eval_js(target, js, timeout=20)
    if not isinstance(value, dict):
        raise DouyinTextError(f"Unexpected page info result: {type(value).__name__}")
    return value


def simplify_page_metadata(info: dict[str, Any], source_url: str) -> dict[str, Any]:
    detail = info.get("detail") if isinstance(info.get("detail"), dict) else {}
    author = detail.get("author") if isinstance(detail.get("author"), dict) else {}
    aweme_id = str(detail.get("aweme_id") or detail.get("awemeId") or info.get("aweme_id") or infer_aweme_id(info.get("url") or "") or "")
    desc = str(detail.get("desc") or info.get("metaDescription") or info.get("ogTitle") or info.get("title") or "").strip()
    duration = None
    video = detail.get("video") if isinstance(detail.get("video"), dict) else {}
    if video.get("duration") is not None:
        duration = video.get("duration")
    elif info.get("videos"):
        duration_sec = (info["videos"][0] or {}).get("duration")
        if duration_sec:
            duration = int(float(duration_sec) * 1000)
    metadata: dict[str, Any] = {
        "source_url": info.get("url") or source_url,
        "input_url": source_url,
        "aweme_id": aweme_id,
        "desc": desc,
        "author_nickname": author.get("nickname") or author.get("unique_id") or "",
        "duration_ms": duration,
        "create_time": detail.get("create_time") or detail.get("createTime") or "",
        "page_title": info.get("title") or "",
        "official_tracks": info.get("tracks") or [],
    }
    interaction_stats = extract_interaction_stats(detail)
    if interaction_stats:
        metadata["statistics"] = interaction_stats
    chapter_abstract = detail.get("chapter_abstract") if isinstance(detail, dict) else None
    if chapter_abstract:
        metadata["chapter_abstract"] = chapter_abstract
    chapter_list = detail.get("chapter_list") if isinstance(detail, dict) else None
    if chapter_list:
        metadata["chapter_list"] = chapter_list
    return metadata


def find_media_url(info: dict[str, Any]) -> str:
    candidates = []
    for video in info.get("videos") or []:
        if isinstance(video, dict) and video.get("src"):
            candidates.append(str(video["src"]))
    candidates.extend(str(url) for url in info.get("resources") or [])
    for url in candidates:
        if url.startswith("http") and not url.startswith("blob:"):
            return url
    raise DouyinTextError("Could not find a downloadable media URL on the Douyin page.")


def download_file(url: str, out_path: Path, referer: str | None = None) -> None:
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=120) as resp, out_path.open("wb") as fh:
            shutil.copyfileobj(resp, fh)
    except error.URLError as exc:
        raise DouyinTextError(f"Media download failed: {exc}") from exc


def run_ffmpeg_extract_audio(video_path: Path, wav_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise DouyinTextError("ffmpeg was not found on PATH; cannot extract audio.")
    cmd = [ffmpeg, "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(wav_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise DouyinTextError(f"ffmpeg failed: {result.stderr[-1000:]}")


def run_whisper(wav_path: Path, out_dir: Path, model: str, language: str) -> Path:
    whisper = shutil.which("whisper")
    if whisper:
        cmd = [
            whisper,
            str(wav_path),
            "--language",
            language,
            "--model",
            model,
            "--output_dir",
            str(out_dir),
            "--output_format",
            "all",
            "--verbose",
            "False",
        ]
    else:
        cmd = [
            sys.executable,
            "-m",
            "whisper",
            str(wav_path),
            "--language",
            language,
            "--model",
            model,
            "--output_dir",
            str(out_dir),
            "--output_format",
            "all",
            "--verbose",
            "False",
        ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise DouyinTextError(f"Whisper failed: {result.stderr[-1200:] or result.stdout[-1200:]}")
    srt_path = out_dir / f"{wav_path.stem}.srt"
    if not srt_path.exists():
        matches = sorted(out_dir.glob("*.srt"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not matches:
            raise DouyinTextError("Whisper completed but no SRT output was found.")
        srt_path = matches[0]
    return srt_path


def find_qwen_python(explicit: str | None = None) -> str:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("RIMAGINATION_QWEN_PYTHON"):
        candidates.append(os.environ["RIMAGINATION_QWEN_PYTHON"])
    if os.environ.get("DOUYIN_NOTE_QWEN_PYTHON"):
        candidates.append(os.environ["DOUYIN_NOTE_QWEN_PYTHON"])
    candidates.extend(
        [
            str(Path(os.environ.get("RIMAGINATION_NOTE_CACHE", Path.home() / ".cache" / "rimagination-notes")).expanduser() / "qwen3-asr-venv" / "Scripts" / "python.exe"),
            str(Path(os.environ.get("RIMAGINATION_NOTE_CACHE", Path.home() / ".cache" / "rimagination-notes")).expanduser() / "qwen3-asr-venv" / "bin" / "python"),
            str(Path.home() / ".cache" / "dy-note" / "qwen3-asr-venv" / "Scripts" / "python.exe"),
            str(Path.home() / ".cache" / "dy-note" / "qwen3-asr-venv" / "bin" / "python"),
            str(Path.home() / ".cache" / "douyin-note" / "qwen3-asr-venv" / "Scripts" / "python.exe"),
            str(Path.home() / ".cache" / "douyin-note" / "qwen3-asr-venv" / "bin" / "python"),
            sys.executable,
        ]
    )
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return explicit or sys.executable


def is_chinese_language(value: str | None) -> bool:
    key = (value or "").strip().lower()
    return key in {"", "zh", "zh-cn", "zh_cn", "cn", "chinese", "mandarin"}


def qwen_available(explicit: str | None = None) -> bool:
    if importlib.util.find_spec("qwen_asr"):
        return True
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("RIMAGINATION_QWEN_PYTHON"):
        candidates.append(os.environ["RIMAGINATION_QWEN_PYTHON"])
    if os.environ.get("DOUYIN_NOTE_QWEN_PYTHON"):
        candidates.append(os.environ["DOUYIN_NOTE_QWEN_PYTHON"])
    candidates.extend(
        [
            str(Path(os.environ.get("RIMAGINATION_NOTE_CACHE", Path.home() / ".cache" / "rimagination-notes")).expanduser() / "qwen3-asr-venv" / "Scripts" / "python.exe"),
            str(Path(os.environ.get("RIMAGINATION_NOTE_CACHE", Path.home() / ".cache" / "rimagination-notes")).expanduser() / "qwen3-asr-venv" / "bin" / "python"),
            str(Path.home() / ".cache" / "dy-note" / "qwen3-asr-venv" / "Scripts" / "python.exe"),
            str(Path.home() / ".cache" / "dy-note" / "qwen3-asr-venv" / "bin" / "python"),
            str(Path.home() / ".cache" / "douyin-note" / "qwen3-asr-venv" / "Scripts" / "python.exe"),
            str(Path.home() / ".cache" / "douyin-note" / "qwen3-asr-venv" / "bin" / "python"),
        ]
    )
    return any(candidate and Path(candidate).exists() for candidate in candidates)


def resolve_asr_backend(requested: str, language: str, qwen_python: str | None = None) -> str:
    if requested != "auto":
        return requested
    if is_chinese_language(language) and qwen_available(qwen_python):
        return "qwen3-asr"
    return "whisper"


def run_qwen_asr(
    audio_path: Path,
    out_dir: Path,
    model: str,
    language: str,
    qwen_python: str | None,
    device_map: str,
    dtype: str,
    max_new_tokens: int,
    chunk_seconds: float,
) -> Path:
    helper = Path(__file__).with_name("run_qwen_asr.py")
    if not helper.exists():
        raise DouyinTextError(f"Qwen helper script not found: {helper}")
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / f"{audio_path.stem}.qwen3_asr.json"
    python = find_qwen_python(qwen_python)
    cmd = [
        python,
        str(helper),
        "--audio",
        str(audio_path),
        "--out",
        str(result_path),
        "--model",
        model,
        "--language",
        language,
        "--device-map",
        device_map,
        "--dtype",
        dtype,
        "--max-new-tokens",
        str(max_new_tokens),
        "--chunk-seconds",
        str(chunk_seconds),
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=env)
    if result.returncode != 0:
        detail = result.stderr[-1600:] or result.stdout[-1600:]
        raise DouyinTextError(f"Qwen3-ASR failed using {python}: {detail}")
    if not result_path.exists():
        raise DouyinTextError("Qwen3-ASR completed but no JSON result was found.")
    return result_path


def out_dir_for(metadata: dict[str, Any], base_dir: Path) -> Path:
    aweme_id = metadata.get("aweme_id") or datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_dir / f"dy_note_{aweme_id}"


def extract_from_douyin(
    source_text: str,
    out_dir: Path | None,
    target: str | None,
    keep_tab: bool,
    force: bool,
    asr_backend: str,
    asr_model: str,
    language: str,
    qwen_model: str,
    qwen_python: str | None,
    qwen_device_map: str,
    qwen_dtype: str,
    qwen_max_new_tokens: int,
    qwen_chunk_seconds: float,
) -> dict[str, Any]:
    url = extract_first_url(source_text)
    if out_dir is not None and not force and core_outputs_ready(out_dir):
        return reuse_existing_outputs(out_dir)
    created_target = False
    if target:
        browser_target = target
    else:
        browser_target = open_target(url)
        created_target = True
        time.sleep(2)
    try:
        info = collect_page_info(browser_target)
        metadata = simplify_page_metadata(info, url)
        if out_dir is None:
            out_dir = out_dir_for(metadata, Path.cwd())
        out_dir.mkdir(parents=True, exist_ok=True)
        if not force and core_outputs_ready(out_dir):
            return reuse_existing_outputs(out_dir)
        write_json(out_dir / "page_metadata.json", sanitize_metadata(metadata))
        media_url = find_media_url(info)
        media_path = out_dir / f"{metadata.get('aweme_id') or 'douyin_video'}.mp4"
        wav_path = out_dir / f"{metadata.get('aweme_id') or 'douyin_video'}_16k.wav"
        if not media_path.exists():
            download_file(media_url, media_path, referer=metadata.get("source_url") or url)
        if not wav_path.exists():
            run_ffmpeg_extract_audio(media_path, wav_path)
        resolved_asr_backend = resolve_asr_backend(asr_backend, language, qwen_python)
        if resolved_asr_backend == "qwen3-asr":
            result_path = run_qwen_asr(
                wav_path,
                out_dir,
                qwen_model,
                language,
                qwen_python,
                qwen_device_map,
                qwen_dtype,
                qwen_max_new_tokens,
                qwen_chunk_seconds,
            )
            report = build_from_qwen_result(
                result_path=result_path,
                out_dir=out_dir,
                metadata=load_metadata(out_dir / "page_metadata.json"),
                source_url=metadata.get("source_url") or url,
            )
            report["qwen_result"] = str(result_path)
        else:
            srt_path = run_whisper(wav_path, out_dir, asr_model, language)
            report = build_from_local_transcript(
                source_path=srt_path,
                source_kind="srt",
                out_dir=out_dir,
                metadata_path=out_dir / "page_metadata.json",
                source_url=metadata.get("source_url") or url,
            )
            report["whisper_srt"] = str(srt_path)
        report["media_file"] = str(media_path)
        report["audio_file"] = str(wav_path)
        write_json(out_dir / "run_report.json", report)
        return report
    finally:
        if created_target and not keep_tab:
            close_target(browser_target)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract clean text material from a Douyin video.")
    parser.add_argument("source", nargs="?", help="Douyin URL/share text, unless --from-srt/--from-txt/--from-whisper-json is used.")
    local = parser.add_mutually_exclusive_group()
    local.add_argument("--from-srt", type=Path, help="Build clean text outputs from an existing SRT file.")
    local.add_argument("--from-txt", type=Path, help="Build clean text outputs from an existing plain text transcript.")
    local.add_argument("--from-whisper-json", type=Path, help="Build clean text outputs from an existing Whisper JSON file.")
    local.add_argument("--from-qwen-json", type=Path, help="Build clean text outputs from an existing Qwen3-ASR JSON result.")
    local.add_argument("--from-audio", type=Path, help="Run the selected ASR backend on an existing audio file.")
    parser.add_argument("--metadata-json", type=Path, help="Optional metadata JSON to include in outputs.")
    parser.add_argument("--source-url", help="Optional original source URL for local transcript mode.")
    parser.add_argument("--out-dir", type=Path, help="Output directory. Defaults to ./dy_note_<aweme_id>.")
    parser.add_argument("--target", help="Reuse an existing web-access CDP target id.")
    parser.add_argument("--keep-tab", action="store_true", help="Do not close the browser tab created by this script.")
    parser.add_argument("--force", action="store_true", help="Rebuild outputs even when transcript.txt, segments.json, and metadata.json already exist.")
    parser.add_argument("--asr-backend", choices=["auto", "whisper", "qwen3-asr"], default="auto", help="ASR backend for Douyin URL or --from-audio. auto prefers Qwen3-ASR for Chinese when the shared environment exists; use whisper for foreign-language videos.")
    parser.add_argument("--asr-model", default="medium", help="Whisper model name for ASR fallback/full extraction.")
    parser.add_argument("--language", default="Chinese", help="Whisper language hint.")
    parser.add_argument("--qwen-model", default=DEFAULT_QWEN_MODEL, help="Qwen3-ASR model name or local path.")
    parser.add_argument("--qwen-python", help="Python executable for the shared qwen-asr environment.")
    parser.add_argument("--qwen-device-map", default="auto", help="Qwen device_map: auto, cuda:0, cpu, etc.")
    parser.add_argument("--qwen-dtype", default="auto", help="Qwen dtype: auto, bfloat16, float16, float32.")
    parser.add_argument("--qwen-max-new-tokens", type=int, default=8192, help="Maximum generated tokens for Qwen3-ASR long audio.")
    parser.add_argument("--qwen-chunk-seconds", type=float, default=60.0, help="Chunk length for Qwen3-ASR to avoid GPU OOM; use 0 to disable.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        if args.out_dir and not args.force and core_outputs_ready(args.out_dir):
            report = reuse_existing_outputs(args.out_dir)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if args.from_srt:
            out_dir = args.out_dir or Path.cwd() / f"dy_note_{args.from_srt.stem}"
            report = reuse_existing_outputs(out_dir) if not args.force and core_outputs_ready(out_dir) else build_from_local_transcript(args.from_srt, "srt", out_dir, args.metadata_json, args.source_url)
        elif args.from_txt:
            out_dir = args.out_dir or Path.cwd() / f"dy_note_{args.from_txt.stem}"
            report = reuse_existing_outputs(out_dir) if not args.force and core_outputs_ready(out_dir) else build_from_local_transcript(args.from_txt, "txt", out_dir, args.metadata_json, args.source_url)
        elif args.from_whisper_json:
            out_dir = args.out_dir or Path.cwd() / f"dy_note_{args.from_whisper_json.stem}"
            report = reuse_existing_outputs(out_dir) if not args.force and core_outputs_ready(out_dir) else build_from_local_transcript(args.from_whisper_json, "whisper-json", out_dir, args.metadata_json, args.source_url)
        elif args.from_qwen_json:
            out_dir = args.out_dir or Path.cwd() / f"dy_note_{args.from_qwen_json.stem}"
            report = reuse_existing_outputs(out_dir) if not args.force and core_outputs_ready(out_dir) else build_from_qwen_result(args.from_qwen_json, out_dir, load_metadata(args.metadata_json), args.source_url)
        elif args.from_audio:
            out_dir = args.out_dir or Path.cwd() / f"dy_note_{args.from_audio.stem}"
            if not args.force and core_outputs_ready(out_dir):
                report = reuse_existing_outputs(out_dir)
            else:
                resolved_asr_backend = resolve_asr_backend(args.asr_backend, args.language, args.qwen_python)
                if resolved_asr_backend == "qwen3-asr":
                    result_path = run_qwen_asr(
                        args.from_audio,
                        out_dir,
                        args.qwen_model,
                        args.language,
                        args.qwen_python,
                        args.qwen_device_map,
                        args.qwen_dtype,
                        args.qwen_max_new_tokens,
                        args.qwen_chunk_seconds,
                    )
                    report = build_from_qwen_result(result_path, out_dir, load_metadata(args.metadata_json), args.source_url)
                    report["qwen_result"] = str(result_path)
                else:
                    srt_path = run_whisper(args.from_audio, out_dir, args.asr_model, args.language)
                    report = build_from_local_transcript(srt_path, "srt", out_dir, args.metadata_json, args.source_url)
                    report["whisper_srt"] = str(srt_path)
        else:
            if not args.source:
                parser.error("source is required unless a local transcript option is used")
            report = extract_from_douyin(
                args.source,
                args.out_dir,
                args.target,
                args.keep_tab,
                args.force,
                args.asr_backend,
                args.asr_model,
                args.language,
                args.qwen_model,
                args.qwen_python,
                args.qwen_device_map,
                args.qwen_dtype,
                args.qwen_max_new_tokens,
                args.qwen_chunk_seconds,
            )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except DouyinTextError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
