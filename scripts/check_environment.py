#!/usr/bin/env python3
"""Check optional dependencies for DyNote."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib import error, request


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def command_version(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=8)
    except Exception:
        return None
    first = (result.stdout or "").splitlines()
    return first[0].strip() if first else ""


def proxy_ready() -> bool:
    try:
        with request.urlopen("http://localhost:3456/targets", timeout=3) as resp:
            return resp.status == 200
    except error.URLError:
        return False


def whisper_cache() -> list[dict[str, object]]:
    cache = Path.home() / ".cache" / "whisper"
    if not cache.exists():
        return []
    rows = []
    for path in sorted(cache.glob("*.pt")):
        rows.append({"name": path.name, "size_mb": round(path.stat().st_size / 1024 / 1024, 1)})
    return rows


def shared_cache_dir() -> Path:
    return Path(os.environ.get("RIMAGINATION_NOTE_CACHE", Path.home() / ".cache" / "rimagination-notes")).expanduser()


def qwen_venv_python_paths(venv: Path) -> list[Path]:
    return [venv / "Scripts" / "python.exe", venv / "bin" / "python"]


def can_import_whisper() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import whisper"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=12,
        )
    except Exception:
        return False
    return result.returncode == 0


def qwen_python_candidates() -> list[Path]:
    candidates = []
    for env_name in ("RIMAGINATION_QWEN_PYTHON", "DOUYIN_NOTE_QWEN_PYTHON"):
        if os.environ.get(env_name):
            candidates.append(Path(os.environ[env_name]).expanduser())
    for venv in [
        shared_cache_dir() / "qwen3-asr-venv",
        Path.home() / ".cache" / "dy-note" / "qwen3-asr-venv",
        Path.home() / ".cache" / "douyin-note" / "qwen3-asr-venv",
    ]:
        candidates.extend(qwen_venv_python_paths(venv))
    return candidates


def probe_qwen_python() -> dict[str, object]:
    scripts = [str(path) for path in qwen_python_candidates() if path.exists()]
    if not scripts:
        scripts = [sys.executable]
    probe_code = (
        "import json, sys\n"
        "info={'python':sys.executable}\n"
        "try:\n"
        " import torch\n"
        " info['torch']=getattr(torch,'__version__','unknown')\n"
        " info['cuda_available']=bool(torch.cuda.is_available())\n"
        " info['cuda_device_count']=torch.cuda.device_count() if torch.cuda.is_available() else 0\n"
        "except Exception as e:\n"
        " info['torch_error']=str(e)\n"
        "try:\n"
        " import qwen_asr\n"
        " info['qwen_asr']='OK'\n"
        "except Exception as e:\n"
        " info['qwen_asr_error']=str(e)\n"
        "print(json.dumps(info, ensure_ascii=False))\n"
    )
    for python in scripts:
        try:
            result = subprocess.run(
                [python, "-c", probe_code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception as exc:
            return {"python": python, "error": str(exc)}
        if result.returncode == 0 and result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"python": python, "error": result.stdout[-500:]}
    return {"python": scripts[0], "error": "probe failed"}


def main() -> int:
    ffmpeg = shutil.which("ffmpeg")
    whisper = shutil.which("whisper")
    whisper_import = can_import_whisper()
    qwen_probe = probe_qwen_python()
    shared_cache = shared_cache_dir()
    report = {
        "shared_resources": {
            "cache_dir": str(shared_cache),
            "qwen3_asr_venv": str(shared_cache / "qwen3-asr-venv"),
            "huggingface_cache": os.environ.get("HF_HOME") or str(Path.home() / ".cache" / "huggingface"),
            "whisper_cache": str(Path.home() / ".cache" / "whisper"),
            "faster_whisper_cache": str(Path.home() / ".cache" / "faster-whisper"),
            "qwen_python_candidates": [str(path) for path in qwen_python_candidates()],
        },
        "web_access_proxy": "OK" if proxy_ready() else "MISSING",
        "ffmpeg": command_version([ffmpeg, "-version"]) if ffmpeg else None,
        "whisper_cli": whisper,
        "whisper_python_import": "OK" if whisper_import else "MISSING",
        "whisper_cache": whisper_cache(),
        "qwen3_asr": qwen_probe,
        "routes": {
            "analysis_plan": "OK" if (Path(__file__).with_name("create_analysis_plan.py")).exists() else "MISSING create_analysis_plan.py",
            "workflow_state": "OK" if (Path(__file__).with_name("inspect_workflow_state.py")).exists() else "MISSING inspect_workflow_state.py",
            "local_transcript_cleanup": "OK",
            "asset_archive": "OK" if (Path(__file__).with_name("archive_dy_note_assets.py")).exists() else "MISSING archive_dy_note_assets.py",
            "douyin_comments": "OK" if (Path(__file__).with_name("fetch_douyin_comments.py")).exists() else "MISSING fetch_douyin_comments.py",
            "note_budget": "OK" if (Path(__file__).with_name("compute_note_budget.py")).exists() else "MISSING compute_note_budget.py",
            "note_score": "OK" if (Path(__file__).with_name("score_dy_note.py")).exists() else "MISSING score_dy_note.py",
            "douyin_browser_extract": "OK" if proxy_ready() else "NEEDS web-access proxy",
            "douyin_web_ai_brief": "OK" if proxy_ready() and (Path(__file__).with_name("douyin_web_ai_brief.py")).exists() else "NEEDS web-access proxy and douyin_web_ai_brief.py",
            "doubao_web_brief_fallback": "OK" if proxy_ready() else "NEEDS web-access proxy; login is checked by doubao_video_brief.py --check-login",
            "audio_asr": "OK" if ffmpeg and (whisper or whisper_import) else "NEEDS ffmpeg and whisper",
            "qwen3_asr": "OK" if qwen_probe.get("qwen_asr") == "OK" else "NEEDS shared qwen-asr environment; run scripts/setup_qwen_asr_env.py",
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
