#!/usr/bin/env python3
"""Extract Douyin Web built-in AI chapter briefs from the user's Chrome.

This helper drives the user's current Chrome through the web-access CDP proxy.
It never reads browser profile files, cookies, localStorage, request signatures,
or signed media URLs. The browser loads Douyin normally; the script only reads
visible DOM text and can click visible "问AI" / "识别画面" controls.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


PROXY = "http://localhost:3456"
TIME_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


class DouyinWebAIError(RuntimeError):
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
        raise DouyinWebAIError(f"web-access CDP proxy request failed: {exc}") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DouyinWebAIError(f"CDP proxy returned non-JSON: {payload[:300]}") from exc


def eval_js(target: str, js: str, timeout: int = 30) -> Any:
    result = http_json("POST", f"/eval?target={parse.quote(target)}", js, timeout=timeout)
    if "error" in result:
        raise DouyinWebAIError(f"CDP eval failed: {result['error']}")
    if "exceptionDetails" in result:
        details = result.get("exceptionDetails") or {}
        raise DouyinWebAIError(f"CDP eval exception: {details.get('text', details)}")
    return result.get("value")


def open_target(url: str) -> str:
    result = http_json("GET", f"/new?url={parse.quote(url, safe='')}", timeout=60)
    target = result.get("targetId")
    if not target:
        raise DouyinWebAIError(f"Could not create browser target: {result}")
    return str(target)


def close_target(target: str) -> None:
    try:
        http_json("GET", f"/close?target={parse.quote(target)}", timeout=10)
    except Exception:
        pass


def extract_first_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s，。；、\"'<>]+", text or "")
    if not match:
        return None
    return match.group(0).rstrip(").,，。")


def infer_aweme_id(text: str) -> str | None:
    for pattern in (
        r"/(?:note|video)/(\d{10,24})",
        r"(?:aweme_id|modal_id|item_id|group_id)=(\d{10,24})",
        r"\b(\d{16,24})\b",
    ):
        match = re.search(pattern, text or "")
        if match:
            return match.group(1)
    return None


def normalize_source_url(source: str) -> tuple[str | None, str | None]:
    url = extract_first_url(source) or (source.strip() if source.strip().startswith(("http://", "https://")) else None)
    aweme_id = infer_aweme_id(source)
    if aweme_id:
        return f"https://www.douyin.com/video/{aweme_id}", aweme_id
    return url, None


def safe_stem(source: str) -> str:
    return infer_aweme_id(source) or datetime.now().strftime("%Y%m%d_%H%M%S")


def clean_lines(text: str) -> list[str]:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\u200b\ufeff\xa0]+", " ", text)
    return [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n") if line.strip()]


def parse_chapter_text(text: str) -> dict[str, Any]:
    """Parse Douyin AI's visible "章节要点" section from page text."""
    lines = clean_lines(text)
    candidates: list[dict[str, Any]] = []
    starts = [index for index, line in enumerate(lines) if "章节要点" in line]
    if not starts and "内容由AI生成" in text:
        starts = [0]

    for start in starts:
        section: list[str] = []
        for line in lines[start + 1 :]:
            if "以上为历史记录" in line or line in {"评论", "相关推荐", "TA的作品"}:
                break
            if "内容由AI生成" in line:
                break
            if "章节要点" in line:
                continue
            section.append(line)
        parsed = parse_chapter_section(section)
        if parsed["summary"] or parsed["timeline"]:
            candidates.append(parsed)

    if not candidates:
        return {"summary": "", "timeline": [], "raw_section": ""}
    candidates.sort(key=lambda item: (len(item["timeline"]), len(item["summary"])), reverse=True)
    return candidates[0]


def parse_chapter_section(section: list[str]) -> dict[str, Any]:
    summary_parts: list[str] = []
    timeline: list[dict[str, str]] = []
    index = 0
    while index < len(section):
        line = section[index]
        if TIME_RE.match(line):
            break
        if not should_skip_line(line):
            summary_parts.append(line)
        index += 1

    while index < len(section):
        line = section[index]
        if not TIME_RE.match(line):
            index += 1
            continue
        time_value = line
        index += 1
        title = ""
        if index < len(section) and not TIME_RE.match(section[index]):
            title = section[index]
            index += 1
        desc_parts: list[str] = []
        while index < len(section) and not TIME_RE.match(section[index]):
            if not should_skip_line(section[index]):
                desc_parts.append(section[index])
            index += 1
        timeline.append({"time": time_value, "title": title, "description": " ".join(desc_parts).strip()})

    raw_section = "\n".join(section)
    return {
        "summary": " ".join(summary_parts).strip(),
        "timeline": timeline,
        "raw_section": raw_section,
    }


def should_skip_line(line: str) -> bool:
    return line in {
        "问AI",
        "问问 AI",
        "问问AI",
        "详情",
        "评论",
        "相关推荐",
        "内容由AI生成",
        "下一章",
        "倍速",
        "智能",
        "清屏",
        "连播",
    }


def collect_page_state(target: str, click_ask_ai: bool = False) -> dict[str, Any]:
    js = f"""
(() => {{
  const isVisible = (el) => {{
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  }};
  const textOf = (el) => (el.innerText || el.textContent || '').trim();
  const clickLabel = (labels) => {{
    const candidates = Array.from(document.querySelectorAll('button, div, span, a, [role="button"], [role="tab"]'));
    for (const el of candidates) {{
      const text = textOf(el).replace(/\\s+/g, '');
      if (!isVisible(el)) continue;
      if (labels.some((label) => text === label.replace(/\\s+/g, '') || text.includes(label.replace(/\\s+/g, '')))) {{
        el.click();
        return {{clicked: true, text: textOf(el), tag: el.tagName, id: el.id || '', className: el.className || ''}};
      }}
    }}
    return {{clicked: false}};
  }};
  const clickedAskAI = {str(click_ask_ai).lower()} ? clickLabel(['问AI', '问问 AI', '问问AI']) : {{clicked: false}};
  const bodyText = (document.body && document.body.innerText) || '';
  const cardTexts = Array.from(document.querySelectorAll('section, article, aside, main, [role="tabpanel"], [class], [id]'))
    .map((el) => textOf(el))
    .filter((text) => text && (text.includes('章节要点') || text.includes('内容由AI生成') || text.includes('识别画面已加入输入框')))
    .filter((text, index, array) => array.indexOf(text) === index)
    .slice(0, 8);
  return {{
    url: location.href,
    documentTitle: document.title,
    clickedAskAI,
    hasAskAI: bodyText.includes('问AI') || bodyText.includes('问问 AI') || bodyText.includes('问问AI') || bodyText.includes('章节要点'),
    hasIdentifyFrame: bodyText.includes('识别画面'),
    frameJoinedInput: bodyText.includes('识别画面已加入输入框'),
    bodyText: bodyText.slice(0, 70000),
    cardTexts: cardTexts.map((text) => text.slice(0, 30000)),
    metaDescription: document.querySelector('meta[name="description"]')?.content || '',
  }};
}})()
"""
    value = eval_js(target, js, timeout=30)
    return value if isinstance(value, dict) else {}


def click_identify_frame(target: str) -> dict[str, Any]:
    js = """
(() => {
  const isVisible = (el) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };
  const textOf = (el) => (el.innerText || el.textContent || '').trim();
  const candidates = Array.from(document.querySelectorAll('button, div, span, a, [role="button"]'));
  for (const el of candidates) {
    const text = textOf(el).replace(/\\s+/g, '');
    if (isVisible(el) && text.includes('识别画面')) {
      el.click();
      return {clicked: true, text: textOf(el), tag: el.tagName, id: el.id || '', className: el.className || ''};
    }
  }
  return {clicked: false};
})()
"""
    clicked = eval_js(target, js, timeout=20)
    time.sleep(1.0)
    state = collect_page_state(target)
    return {
        "clicked": bool(isinstance(clicked, dict) and clicked.get("clicked")),
        "frame_context_added": bool(state.get("frameJoinedInput")),
        "raw": clicked,
    }


def choose_chapter_source(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    texts = [str(item) for item in state.get("cardTexts") or []]
    texts.append(str(state.get("bodyText") or ""))
    best_text = ""
    best_parse = {"summary": "", "timeline": [], "raw_section": ""}
    for text in texts:
        parsed = parse_chapter_text(text)
        if len(parsed["timeline"]) > len(best_parse["timeline"]) or (
            len(parsed["timeline"]) == len(best_parse["timeline"]) and len(parsed["summary"]) > len(best_parse["summary"])
        ):
            best_text = text
            best_parse = parsed
    return best_text, best_parse


def evidence_level(parsed: dict[str, Any], frame: dict[str, Any] | None) -> str:
    has_chapters = bool(parsed.get("summary") or parsed.get("timeline"))
    frame_added = bool(frame and frame.get("frame_context_added"))
    if has_chapters and frame_added:
        return "douyin-web-ai-chapters+frame-context"
    if has_chapters:
        return "douyin-web-ai-chapters"
    if frame_added:
        return "douyin-web-ai-frame-context"
    return "weak"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 抖音内置 AI 视频解读",
        "",
        f"- 来源：{report.get('source_url') or report.get('source_text') or ''}",
        f"- 页面：{report.get('page_url') or ''}",
        f"- 作品 ID：{report.get('aweme_id') or ''}",
        f"- 证据等级：{report.get('evidence_level') or ''}",
        f"- 状态：{report.get('status') or ''}",
        "",
    ]
    summary = str(report.get("summary") or "").strip()
    if summary:
        lines.extend(["## 章节要点", "", summary, ""])
    timeline = report.get("timeline") or []
    if timeline:
        lines.extend(["## 时间线", ""])
        for item in timeline:
            desc = f"：{item.get('description')}" if item.get("description") else ""
            lines.append(f"- [{item.get('time')}] {item.get('title') or '章节'}{desc}")
        lines.append("")
    frame = report.get("identify_frame") or {}
    if frame:
        lines.extend(
            [
                "## 识别画面",
                "",
                f"- 点击识别画面：{'是' if frame.get('clicked') else '否'}",
                f"- 当前帧加入输入框：{'是' if frame.get('frame_context_added') else '否'}",
                "",
            ]
        )
    if report.get("limitations"):
        lines.extend(["## 局限", ""])
        lines.extend(f"- {item}" for item in report["limitations"])
        lines.append("")
    raw = str(report.get("raw_ai_section") or "").strip()
    if raw:
        lines.extend(["## 原始 AI 片段", "", "```text", raw[:5000], "```", ""])
    return "\n".join(lines)


def write_outputs(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    report["outputs"] = {
        "json": str(out_dir / "douyin_ai_brief.json"),
        "markdown": str(out_dir / "douyin_ai_brief.md"),
    }
    (out_dir / "douyin_ai_brief.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "douyin_ai_brief.md").write_text(render_markdown(report), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    source_text = (args.from_file.read_text(encoding="utf-8-sig") if args.from_file else args.source or "").strip()
    if not source_text and not args.target:
        raise DouyinWebAIError("source URL/share text is required unless --target is used.")

    original_url = extract_first_url(source_text)
    normalized_url, aweme_id = normalize_source_url(source_text)
    target = args.target
    created_target = False
    if not target:
        if not normalized_url:
            raise DouyinWebAIError("Could not find a Douyin URL or aweme id in source text.")
        open_url = original_url if args.identify_frame and original_url and "douyin.com" in original_url else normalized_url
        target = open_target(open_url)
        created_target = True
        time.sleep(max(args.wait_seconds, 1.0))

    try:
        state = collect_page_state(target, click_ask_ai=True)
        time.sleep(max(args.wait_seconds, 0.5))
        state = collect_page_state(target)
        raw_text, parsed = choose_chapter_source(state)
        frame_result = click_identify_frame(target) if args.identify_frame else None
        if not (parsed.get("summary") or parsed.get("timeline")) and normalized_url and normalized_url != state.get("url"):
            if created_target and not args.keep_tab:
                close_target(target)
            target = open_target(normalized_url)
            created_target = True
            time.sleep(max(args.wait_seconds, 1.0))
            state = collect_page_state(target, click_ask_ai=True)
            time.sleep(max(args.wait_seconds, 0.5))
            state = collect_page_state(target)
            raw_text, parsed = choose_chapter_source(state)
        level = evidence_level(parsed, frame_result)
        status = "ok" if level.startswith("douyin-web-ai") else ("blocked" if not state.get("hasAskAI") else "weak")
        limitations: list[str] = []
        if status != "ok":
            limitations.append("当前页面没有提取到抖音内置 AI 的章节要点；可能未登录、功能未灰度到账号、页面未加载完成或该视频暂不支持。")
        if args.identify_frame and frame_result and not frame_result.get("frame_context_added"):
            limitations.append("已尝试点击“识别画面”，但没有检测到“识别画面已加入输入框”的页面提示。")

        report: dict[str, Any] = {
            "schema": "dy-note-douyin-web-ai-brief-v1",
            "status": status,
            "source_text": source_text,
            "source_url": original_url or normalized_url,
            "normalized_url": normalized_url,
            "aweme_id": aweme_id or infer_aweme_id(str(state.get("url") or "")),
            "page_url": state.get("url"),
            "page_title": state.get("documentTitle"),
            "meta_description": state.get("metaDescription"),
            "douyin_web_ai": {
                "ask_ai_detected": bool(state.get("hasAskAI")),
                "identify_frame_detected": bool(state.get("hasIdentifyFrame")),
                "chapter_detected": bool(parsed.get("summary") or parsed.get("timeline")),
            },
            "identify_frame": frame_result,
            "evidence_level": level,
            "summary": parsed.get("summary") or "",
            "timeline": parsed.get("timeline") or [],
            "raw_ai_section": parsed.get("raw_section") or raw_text[:5000],
            "limitations": limitations,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        out_dir = args.out_dir or Path.cwd() / f"dy_note_douyin_ai_{safe_stem(source_text or str(report.get('page_url') or ''))}"
        write_outputs(out_dir, report)
        return report
    finally:
        if created_target and not args.keep_tab:
            close_target(target)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract Douyin Web built-in AI chapter brief from current Chrome.")
    parser.add_argument("source", nargs="?", help="Douyin URL or copied share text.")
    parser.add_argument("--from-file", type=Path, help="Read Douyin URL/share text from a UTF-8 file.")
    parser.add_argument("--target", help="Existing web-access CDP target id. The script will not close it.")
    parser.add_argument("--out-dir", type=Path, help="Output directory. Defaults to ./dy_note_douyin_ai_<id>.")
    parser.add_argument("--identify-frame", action="store_true", help="Click the visible Douyin '识别画面' button when available.")
    parser.add_argument("--keep-tab", action="store_true", help="Keep a tab opened by this script.")
    parser.add_argument("--wait-seconds", type=float, default=2.5, help="Seconds to wait after opening/clicking the page.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    try:
        result = run(args)
    except DouyinWebAIError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
