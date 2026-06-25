#!/usr/bin/env python3
"""Use logged-in Doubao Web to produce a quick Douyin video brief.

This helper drives the user's current Chrome through the web-access CDP proxy.
It never reads browser profile files, cookies, localStorage, or tokens. If the
current Chrome session is not logged into Doubao, the script stops instead of
opening another browser or silently degrading to a non-authenticated route.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request


PROXY = "http://localhost:3456"
DOUBAO_CHAT_URL = "https://www.doubao.com/chat/"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


class DoubaoBriefError(RuntimeError):
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
        raise DoubaoBriefError(f"web-access CDP proxy request failed: {exc}") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DoubaoBriefError(f"CDP proxy returned non-JSON: {payload[:300]}") from exc


def eval_js(target: str, js: str, timeout: int = 30) -> Any:
    result = http_json("POST", f"/eval?target={parse.quote(target)}", js, timeout=timeout)
    if "error" in result:
        raise DoubaoBriefError(f"CDP eval failed: {result['error']}")
    if "exceptionDetails" in result:
        details = result.get("exceptionDetails") or {}
        raise DoubaoBriefError(f"CDP eval exception: {details.get('text', details)}")
    return result.get("value")


def open_target(url: str) -> str:
    result = http_json("GET", f"/new?url={parse.quote(url, safe='')}", timeout=60)
    target = result.get("targetId")
    if not target:
        raise DoubaoBriefError(f"Could not create browser target: {result}")
    return str(target)


def close_target(target: str) -> None:
    try:
        http_json("GET", f"/close?target={parse.quote(target)}", timeout=10)
    except Exception:
        pass


def click_at(target: str, selector: str) -> Any:
    result = http_json("POST", f"/clickAt?target={parse.quote(target)}", selector, timeout=20)
    if "error" in result:
        raise DoubaoBriefError(f"CDP clickAt failed: {result['error']}")
    return result


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_first_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s，。；、\"'<>]+", text)
    if not match:
        return None
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


def safe_stem(text: str) -> str:
    aweme_id = infer_aweme_id(text)
    if aweme_id:
        return aweme_id
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_prompt(share_text: str, mode: str) -> str:
    share_text = share_text.strip()
    if mode == "evidence":
        return (
            "请解读这个抖音视频，并把结论分成“可由标题/搜索资料推断”和“需要看到画面才能确认”两类。\n\n"
            "请优先输出：视频主题、核心内容、时间线、食材/器具、画面/声音风格、可复用脚本结构。"
            "如果你不能直接观看视频画面，请明确说明，不要把搜索资料说成关键帧证据。\n\n"
            f"{share_text}"
        )
    return (
        "这个视频讲了什么？请直接整理成：视频内容概括、核心内容、按时间线描述、"
        "画面/声音风格、适合复用的短视频脚本结构。\n\n"
        f"{share_text}"
    )


def check_doubao_login(target: str) -> dict[str, Any]:
    js = r"""
(() => {
  const visible = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 80 && r.height > 8 && cs.display !== 'none' &&
      cs.visibility !== 'hidden' && Number(cs.opacity) !== 0;
  };
  const body = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
  const textareas = Array.from(document.querySelectorAll('textarea')).map((el, i) => {
    const r = el.getBoundingClientRect();
    return { index: i, x: r.x, y: r.y, w: r.width, h: r.height, valueLength: el.value.length, visible: visible(el) };
  });
  const hasVisibleTextarea = textareas.some(t => t.visible);
  const hasChatShell = /新对话|历史对话|AI 创作|云盘/.test(body);
  const loginHints = /登录\/注册|手机号登录|验证码登录|扫码登录|立即登录/.test(body);
  const loginLikely = loginHints || /\/login/i.test(location.href);
  return {
    url: location.href,
    title: document.title || '',
    hasVisibleTextarea,
    hasChatShell,
    loginLikely,
    loggedIn: hasVisibleTextarea && hasChatShell && !loginLikely,
    textareas
  };
})()
"""
    value = eval_js(target, js, timeout=20)
    if not isinstance(value, dict):
        raise DoubaoBriefError("Unexpected Doubao login check result.")
    return value


def prepare_textarea(target: str) -> dict[str, Any]:
    js = r"""
(() => {
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 80 && r.height > 8 && cs.display !== 'none' &&
      cs.visibility !== 'hidden' && Number(cs.opacity) !== 0;
  };
  const el = Array.from(document.querySelectorAll('textarea')).find(visible);
  if (!el) return { ok: false, error: 'no visible textarea' };
  el.id = 'dy-note-doubao-input';
  const r = el.getBoundingClientRect();
  return { ok: true, box: { x: r.x, y: r.y, w: r.width, h: r.height } };
})()
"""
    value = eval_js(target, js, timeout=20)
    if not isinstance(value, dict) or not value.get("ok"):
        raise DoubaoBriefError(str((value or {}).get("error") or "Could not locate Doubao input box."))
    return value


def insert_prompt(target: str, prompt: str) -> dict[str, Any]:
    encoded = base64.b64encode(prompt.encode("utf-8")).decode("ascii")
    js = f"""
(() => {{
  try {{
    const text = new TextDecoder().decode(Uint8Array.from(atob({json.dumps(encoded)}), c => c.charCodeAt(0)));
    const el = document.querySelector('#dy-note-doubao-input');
    if (!el) return {{ ok: false, error: 'no textarea' }};
    el.focus();
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    setter.call(el, '');
    el.dispatchEvent(new InputEvent('input', {{ bubbles: true, inputType: 'deleteContentBackward', data: null }}));
    const execOk = document.execCommand('insertText', false, text);
    if (!el.value || el.value.length < text.length * 0.8) {{
      setter.call(el, text);
      el.dispatchEvent(new InputEvent('input', {{ bubbles: true, inputType: 'insertText', data: text }}));
      el.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }}
    return {{ ok: true, execOk, length: el.value.length, preview: el.value.slice(0, 120) }};
  }} catch (e) {{
    return {{ ok: false, error: String(e), stack: e.stack }};
  }}
}})()
"""
    value = eval_js(target, js, timeout=20)
    if not isinstance(value, dict) or not value.get("ok"):
        raise DoubaoBriefError(str((value or {}).get("error") or "Could not insert prompt into Doubao."))
    return value


def click_send(target: str) -> dict[str, Any]:
    js = r"""
(() => {
  const send = Array.from(document.querySelectorAll('button')).find(btn => {
    const r = btn.getBoundingClientRect();
    return r.width >= 30 && r.height >= 30 &&
      r.x > innerWidth * .85 && r.y > innerHeight * .65 &&
      String(btn.className || '').includes('bg-dbx-text-highlight');
  });
  if (!send) return { ok: false, error: 'no send button' };
  const r = send.getBoundingClientRect();
  send.click();
  return { ok: true, box: { x: r.x, y: r.y, w: r.width, h: r.height }, disabled: send.disabled || send.getAttribute('aria-disabled') };
})()
"""
    value = eval_js(target, js, timeout=20)
    if not isinstance(value, dict) or not value.get("ok"):
        raise DoubaoBriefError(str((value or {}).get("error") or "Could not click Doubao send button."))
    return value


def page_state(target: str) -> dict[str, Any]:
    js = r"""
(() => {
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const main = document.querySelector('main');
  const body = clean(document.body.innerText || '');
  const rows = [];
  for (const el of document.querySelectorAll('main *')) {
    const r = el.getBoundingClientRect();
    if (r.width < 50 || r.height < 10 || r.x < 250 || r.y < 45) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) continue;
    const text = clean(el.innerText || el.textContent || '');
    if (text.length < 8) continue;
    if ([...el.children].some(ch => clean(ch.innerText || ch.textContent || '').length > text.length * .90)) continue;
    rows.push({
      tag: el.tagName,
      x: Math.round(r.x),
      y: Math.round(r.y),
      w: Math.round(r.width),
      h: Math.round(r.height),
      cls: String(el.className || '').slice(0, 160),
      text: text.slice(0, 8000)
    });
    if (rows.length >= 120) break;
  }
  return {
    url: location.href,
    title: document.title || '',
    bodyText: body.slice(0, 20000),
    mainText: clean(main ? main.innerText || '' : '').slice(0, 20000),
    textareaValues: Array.from(document.querySelectorAll('textarea')).map(t => t.value),
    rows
  };
})()
"""
    value = eval_js(target, js, timeout=30)
    if not isinstance(value, dict):
        raise DoubaoBriefError("Unexpected Doubao page state result.")
    return value


def is_ui_noise(text: str) -> bool:
    noise = (
        "AI 生成可能有误 请核实",
        "下载电脑版",
        "快速 图像生成 PPT 生成 帮我写作 视频生成 编程 更多",
        "有什么我能帮你的吗",
    )
    return any(item in text for item in noise) and len(text) < 180


def pick_reply(state: dict[str, Any], prompt: str) -> str:
    prompt_norm = normalize_space(prompt)
    prompt_head = prompt_norm[:80]
    candidates: list[str] = []
    for row in state.get("rows") or []:
        text = normalize_space(str(row.get("text") or ""))
        if not text or is_ui_noise(text):
            continue
        if prompt_head and prompt_head in text:
            continue
        cls = str(row.get("cls") or "")
        x = int(row.get("x") or 0)
        if "suggest-message" in cls or "textarea" in row.get("tag", "").lower():
            continue
        score = len(text)
        if "md-box-root" in cls:
            score += 2000
        if 280 <= x <= 700:
            score += 500
        candidates.append((" " * min(score // 100, 60)) + text)
    if candidates:
        selected = max(candidates, key=len).lstrip()
        return selected.strip()

    main_text = normalize_space(str(state.get("mainText") or ""))
    if prompt_norm and prompt_norm in main_text:
        main_text = main_text.replace(prompt_norm, " ")
    for item in (
        "AI 生成可能有误 请核实",
        "下载电脑版",
        "快速 图像生成 PPT 生成 帮我写作 视频生成 编程 更多",
    ):
        main_text = main_text.replace(item, " ")
    return normalize_space(main_text)


def classify_reply(reply: str, full_page_text: str) -> dict[str, Any]:
    text = normalize_space(reply)
    full = normalize_space(full_page_text)
    blocked = bool(re.search(r"无法访问视频画面|无法直接访问|暂不支持豆包查看|无法观看|不能直接观看|无法完成解析", full))
    search = bool(re.search(r"搜索\s*\d+\s*个关键词|参考\s*\d+\s*篇资料|搜索结果|参考资料", full))
    visual = bool(re.search(r"关键帧|镜头|画面|开篇|中途|结尾|场景变化|人物动作", text))
    if blocked:
        level = "blocked"
    elif search:
        level = "search-derived"
    elif visual:
        level = "visual-claimed"
    elif len(text) >= 160:
        level = "summary"
    else:
        level = "weak"
    return {
        "evidence_level": level,
        "blocked": blocked,
        "search_derived": search,
        "visual_claimed": visual,
        "reply_chars": len(text),
    }


def wait_for_reply(target: str, prompt: str, max_wait_seconds: int, poll_seconds: int) -> dict[str, Any]:
    deadline = time.time() + max_wait_seconds
    best_state: dict[str, Any] | None = None
    best_reply = ""
    stable_count = 0
    last_reply = ""
    while time.time() < deadline:
        time.sleep(poll_seconds)
        state = page_state(target)
        reply = pick_reply(state, prompt)
        if len(reply) > len(best_reply):
            best_reply = reply
            best_state = state
        if reply and reply == last_reply and len(reply) >= 80:
            stable_count += 1
        else:
            stable_count = 0
        last_reply = reply
        textareas = state.get("textareaValues") or []
        input_cleared = not textareas or not str(textareas[0]).strip()
        classification = classify_reply(reply, state.get("bodyText") or state.get("mainText") or "")
        if input_cleared and (
            classification["blocked"]
            or classification["search_derived"]
            or stable_count >= 1
            or len(reply) >= 600
        ):
            state["reply"] = reply
            state["classification"] = classification
            state["elapsed_seconds"] = max_wait_seconds - int(deadline - time.time())
            return state
    state = best_state or page_state(target)
    reply = best_reply or pick_reply(state, prompt)
    state["reply"] = reply
    state["classification"] = classify_reply(reply, state.get("bodyText") or state.get("mainText") or "")
    state["elapsed_seconds"] = max_wait_seconds
    state["timed_out"] = True
    return state


def render_markdown(report: dict[str, Any]) -> str:
    classification = report.get("classification") or {}
    lines = [
        "# 豆包视频解读",
        "",
        f"- 模式：{report.get('mode')}",
        f"- 证据等级：{classification.get('evidence_level')}",
        f"- 豆包会话：{report.get('doubao_chat_url') or ''}",
    ]
    if report.get("source_url"):
        lines.append(f"- 原始链接：{report['source_url']}")
    if classification.get("search_derived"):
        lines.append("- 说明：豆包结果包含搜索/参考资料迹象，按检索式解读使用，不要直接当作逐帧视觉证据。")
    if classification.get("blocked"):
        lines.append("- 说明：豆包表示无法访问或观看视频画面，应回落到本地 ASR/抽帧流程。")
    lines.extend(["", "## 豆包回复", "", str(report.get("reply") or "").strip(), ""])
    return "\n".join(lines)


def run_brief(args: argparse.Namespace) -> dict[str, Any]:
    source_text = args.source or ""
    if args.from_file:
        source_text = args.from_file.read_text(encoding="utf-8")
    if not args.check_login and not source_text.strip():
        raise DoubaoBriefError("source text is required unless --check-login is used.")

    created_target = False
    target = args.target
    if not target:
        target = open_target(DOUBAO_CHAT_URL)
        created_target = True
        time.sleep(3)
    try:
        login = check_doubao_login(target)
        if not login.get("loggedIn"):
            return {
                "status": "blocked",
                "reason": "doubao-login-required",
                "message": "当前可用 Chrome 未检测到豆包登录态。请先在这个 Chrome 登录 https://www.doubao.com/chat/ 后重试。",
                "login_check": login,
            }
        if args.check_login:
            return {"status": "ok", "doubao_logged_in": True, "login_check": login}

        prompt = build_prompt(source_text, args.mode)
        prepare_textarea(target)
        click_at(target, "#dy-note-doubao-input")
        inserted = insert_prompt(target, prompt)
        sent = click_send(target)
        state = wait_for_reply(target, prompt, args.max_wait_seconds, args.poll_seconds)
        reply = normalize_space(state.get("reply") or "")
        classification = state.get("classification") or classify_reply(reply, state.get("bodyText") or "")

        out_dir = args.out_dir or Path.cwd() / f"dy_note_doubao_{safe_stem(source_text)}"
        out_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "status": "ok",
            "mode": args.mode,
            "source_url": extract_first_url(source_text),
            "doubao_chat_url": state.get("url"),
            "reply": reply,
            "classification": classification,
            "elapsed_seconds": state.get("elapsed_seconds"),
            "timed_out": bool(state.get("timed_out")),
            "inserted": inserted,
            "sent": sent,
            "login_check": {
                "url": login.get("url"),
                "title": login.get("title"),
                "loggedIn": login.get("loggedIn"),
                "hasVisibleTextarea": login.get("hasVisibleTextarea"),
                "hasChatShell": login.get("hasChatShell"),
            },
            "raw_share_text": source_text.strip(),
        }
        report["outputs"] = {
            "json": str(out_dir / "doubao_brief.json"),
            "markdown": str(out_dir / "doubao_brief.md"),
        }
        write_json(out_dir / "doubao_brief.json", report)
        (out_dir / "doubao_brief.md").write_text(render_markdown(report), encoding="utf-8")
        return report
    finally:
        if created_target and not args.keep_tab:
            close_target(target)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Use logged-in Doubao Web to brief a Douyin video share.")
    parser.add_argument("source", nargs="?", help="Full Douyin share text or URL. Prefer the full copied share text.")
    parser.add_argument("--from-file", type=Path, help="Read full Douyin share text from a UTF-8 text file.")
    parser.add_argument("--out-dir", type=Path, help="Output directory. Defaults to ./dy_note_doubao_<id>.")
    parser.add_argument("--mode", choices=["fast", "evidence"], default="fast", help="Prompt style for Doubao.")
    parser.add_argument("--check-login", action="store_true", help="Only verify the current Chrome has a logged-in Doubao chat page.")
    parser.add_argument("--target", help="Reuse an existing web-access CDP target id.")
    parser.add_argument("--keep-tab", action="store_true", help="Do not close the tab created by this script.")
    parser.add_argument("--max-wait-seconds", type=int, default=180, help="Maximum time to wait for Doubao's answer.")
    parser.add_argument("--poll-seconds", type=int, default=10, help="Polling interval while waiting for the answer.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        report = run_brief(args)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("status") == "ok" else 3
    except DoubaoBriefError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
