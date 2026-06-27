#!/usr/bin/env python3
"""Archive DyNote raw outputs into a reusable asset package."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRANSCRIPT_FILES = [
    "transcript.txt",
    "transcript.cleaned.md",
    "segments.json",
]

METADATA_FILES = [
    "metadata.json",
    "page_metadata.json",
    "note_budget.json",
    "note_score.json",
    "run_report.json",
    "analysis_plan.json",
]

AI_BRIEF_FILES = [
    "douyin_ai_brief.md",
    "douyin_ai_brief.json",
    "doubao_brief.md",
    "doubao_brief.json",
]

COMMENT_EXCLUDE = {
    "douyin_ai_brief.json",
    "doubao_brief.json",
    "metadata.json",
    "page_metadata.json",
    "note_budget.json",
    "note_score.json",
    "run_report.json",
    "analysis_plan.json",
    "segments.json",
    "asset_manifest.json",
}

LEARNING_CONTRACT = {
    "principle": "资产先行，笔记后置",
    "source_of_truth": "assets/ 下的字幕、转写、评论、元数据和 AI brief 是事实层；学习笔记是按用户问题生成的解释层。",
    "note_generation": [
        "写学习笔记前先读取 assets/asset_manifest.json，确认有哪些可用数据资产。",
        "按用户目标选择证据：内容学习优先 transcripts，用户洞察优先 comments，画面补证参考 ai_briefs。",
        "结论必须能回到原始资产解释来源；证据缺失时写明覆盖范围和不确定性。",
    ],
    "must_not": [
        "不要绕过资产包直接根据一次快读生成最终笔记。",
        "不要把抖音问 AI 或豆包快读写成完整字幕、完整逐帧解析或已核验事实。",
        "不要用新总结覆盖原始评论、字幕、转写或元数据资产。",
    ],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def copy_file(src: Path, dst: Path) -> dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)
    return {
        "source": str(src),
        "path": str(dst),
        "size_bytes": dst.stat().st_size,
    }


def first_existing(out_dir: Path, names: list[str]) -> Path | None:
    for name in names:
        path = out_dir / name
        if path.exists():
            return path
    return None


def glob_first(out_dir: Path, patterns: list[str], exclude: set[str] | None = None) -> Path | None:
    exclude = exclude or set()
    for pattern in patterns:
        for path in sorted(out_dir.glob(pattern)):
            if path.name not in exclude and path.is_file():
                return path
    return None


def glob_first_non_checkpoint(out_dir: Path, patterns: list[str], exclude: set[str] | None = None) -> Path | None:
    exclude = exclude or set()
    for pattern in patterns:
        for path in sorted(out_dir.glob(pattern)):
            if "_main_only_" in path.name:
                continue
            if path.name not in exclude and path.is_file():
                return path
    return None


def find_comment_json(out_dir: Path, explicit: Path | None = None) -> Path | None:
    if explicit:
        return explicit if explicit.exists() else None
    primary = glob_first_non_checkpoint(out_dir, ["douyin_comments_*_full.json", "douyin_comments_*_sample.json"], COMMENT_EXCLUDE)
    if primary:
        return primary
    return glob_first(out_dir, ["douyin_comments_*_main_only_full.json", "douyin_comments_*_main_only_sample.json", "*comments*.json"], COMMENT_EXCLUDE)


def find_comment_csv(out_dir: Path, explicit: Path | None = None, comment_json: Path | None = None) -> Path | None:
    if explicit:
        return explicit if explicit.exists() else None
    if comment_json:
        sibling = comment_json.with_suffix(".csv")
        if sibling.exists():
            return sibling
        if comment_json.name.endswith("_full.json"):
            sibling = comment_json.with_name(comment_json.name[:-10] + "_full.csv")
            if sibling.exists():
                return sibling
        if comment_json.name.endswith("_sample.json"):
            sibling = comment_json.with_name(comment_json.name[:-12] + "_sample.csv")
            if sibling.exists():
                return sibling
    primary = glob_first_non_checkpoint(out_dir, ["douyin_comments_*_full.csv", "douyin_comments_*_sample.csv"])
    if primary:
        return primary
    return glob_first(out_dir, ["douyin_comments_*_main_only_full.csv", "douyin_comments_*_main_only_sample.csv", "*comments*.csv"])


def normalize_comment_rows_from_json(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = read_json(path)
    meta: dict[str, Any] = {"source_json": str(path)}
    rows: list[Any]
    if isinstance(data, dict):
        rows = data.get("rows") or data.get("comments") or []
        for key in [
            "source_url",
            "aweme_id",
            "fetched_at",
            "total_reported",
            "main_comment_count",
            "reply_count",
            "row_count",
            "output_kind",
            "is_sample",
        ]:
            if key in data:
                meta[key] = data[key]
        if isinstance(data.get("coverage"), dict):
            meta["coverage"] = data["coverage"]
            if "is_sample" in data["coverage"]:
                meta["is_sample"] = data["coverage"]["is_sample"]
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    normalized = [dict(row) for row in rows if isinstance(row, dict)]
    return normalized, meta


def read_comment_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows.extend(dict(row) for row in reader)
    return rows


def summarize_comment_rows(rows: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    main = sum(1 for row in rows if str(row.get("level") or "").lower() == "main")
    replies = sum(1 for row in rows if str(row.get("level") or "").lower() == "reply")
    if not main and not replies and rows:
        main = len(rows)
    return {
        "row_count": len(rows),
        "main_comment_count": meta.get("main_comment_count", main),
        "reply_count": meta.get("reply_count", replies),
        "total_reported": meta.get("total_reported"),
        "aweme_id": meta.get("aweme_id"),
        "source_url": meta.get("source_url"),
        "fetched_at": meta.get("fetched_at"),
        "output_kind": meta.get("output_kind"),
        "is_sample": bool(meta.get("is_sample")),
        "coverage": meta.get("coverage"),
    }


def render_comments_markdown(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    title = "# 评论样本" if summary.get("is_sample") else "# 评论全集"
    lines = [
        title,
        "",
        f"- 总行数：{summary.get('row_count') or 0}",
        f"- 主评论：{summary.get('main_comment_count') or 0}",
        f"- 楼中楼回复：{summary.get('reply_count') or 0}",
    ]
    if summary.get("total_reported") is not None:
        lines.append(f"- 页面报告评论数：{summary['total_reported']}")
    if summary.get("aweme_id"):
        lines.append(f"- 作品 ID：{summary['aweme_id']}")
    if summary.get("is_sample"):
        lines.append("- 覆盖范围：评论样本，不是完整评论区")
    lines.extend(["", "## 明细", ""])
    for row in rows:
        level = row.get("level") or "comment"
        nickname = row.get("nickname") or row.get("user_name") or ""
        text = str(row.get("text") or "").replace("\r", " ").replace("\n", " ").strip()
        cid = row.get("cid") or ""
        parent = row.get("parent_cid") or ""
        digg = row.get("digg_count") or ""
        created = row.get("create_time_cn") or row.get("create_time_iso") or ""
        prefix = f"- [{level}]"
        if nickname:
            prefix += f" {nickname}"
        if digg != "":
            prefix += f" 赞={digg}"
        if created:
            prefix += f" 时间={created}"
        if cid:
            prefix += f" cid={cid}"
        if parent:
            prefix += f" parent={parent}"
        lines.append(f"{prefix}：{text}")
    return "\n".join(lines).rstrip() + "\n"


def archive_transcripts(out_dir: Path, assets_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    target = assets_dir / "transcripts"
    for name in TRANSCRIPT_FILES:
        path = out_dir / name
        if path.exists():
            records.append(copy_file(path, target / name))
    for pattern in ["*.srt", "*.vtt"]:
        for path in sorted(out_dir.glob(pattern)):
            if path.is_file():
                records.append(copy_file(path, target / "source_subtitles" / path.name))
    for pattern in ["*.qwen3_asr.json", "*whisper*.json", "*asr*.json"]:
        for path in sorted(out_dir.glob(pattern)):
            if path.name in COMMENT_EXCLUDE or path.name == "segments.json":
                continue
            if path.is_file():
                records.append(copy_file(path, target / "asr_results" / path.name))
    return records


def archive_named_files(out_dir: Path, assets_dir: Path, names: list[str], folder: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name in names:
        path = out_dir / name
        if path.exists():
            records.append(copy_file(path, assets_dir / folder / name))
    return records


def archive_comments(
    out_dir: Path,
    assets_dir: Path,
    comments_json: Path | None = None,
    comments_csv: Path | None = None,
) -> dict[str, Any]:
    target = assets_dir / "comments"
    comment_json = find_comment_json(out_dir, comments_json)
    comment_csv = find_comment_csv(out_dir, comments_csv, comment_json)
    records: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    meta: dict[str, Any] = {}

    if comment_json:
        rows, meta = normalize_comment_rows_from_json(comment_json)
        json_name = "comments.sample.json" if meta.get("is_sample") else "comments.full.json"
        records.append(copy_file(comment_json, target / json_name))
    if comment_csv:
        csv_name = "comments.sample.csv" if meta.get("is_sample") else "comments.full.csv"
        records.append(copy_file(comment_csv, target / csv_name))
        if not rows:
            rows = read_comment_csv(comment_csv)
            meta["source_csv"] = str(comment_csv)

    summary = summarize_comment_rows(rows, meta)
    if rows:
        jsonl_path = target / "comments.rows.jsonl"
        md_path = target / "comments.text.md"
        write_jsonl(jsonl_path, rows)
        md_path.write_text(render_comments_markdown(rows, summary), encoding="utf-8")
        records.append({"path": str(jsonl_path), "size_bytes": jsonl_path.stat().st_size})
        records.append({"path": str(md_path), "size_bytes": md_path.stat().st_size})

    readme = [
        "# 评论资产",
        "",
        "`comments.full.json/csv` 是完整可见评论备份；`comments.sample.json/csv` 是有边界的评论样本；`comments.rows.jsonl` 适合程序分析；`comments.text.md` 适合人工快速浏览。",
        "",
        f"- 总行数：{summary.get('row_count') or 0}",
        f"- 主评论：{summary.get('main_comment_count') or 0}",
        f"- 楼中楼回复：{summary.get('reply_count') or 0}",
    ]
    if summary.get("is_sample"):
        readme.append("- 覆盖范围：样本，不是全部评论；需要完整可见评论时请重新全量抓取。")
    (target / "README.md").parent.mkdir(parents=True, exist_ok=True)
    (target / "README.md").write_text("\n".join(readme).rstrip() + "\n", encoding="utf-8")
    records.append({"path": str(target / "README.md"), "size_bytes": (target / "README.md").stat().st_size})
    return {"summary": summary, "files": records, "has_comments": bool(comment_json or comment_csv)}


def build_asset_package(
    out_dir: Path,
    assets_dir: Path | None = None,
    comments_json: Path | None = None,
    comments_csv: Path | None = None,
) -> dict[str, Any]:
    out_dir = out_dir.resolve()
    assets_dir = (assets_dir or out_dir / "assets").resolve()
    assets_dir.mkdir(parents=True, exist_ok=True)

    transcript_files = archive_transcripts(out_dir, assets_dir)
    metadata_files = archive_named_files(out_dir, assets_dir, METADATA_FILES, "metadata")
    brief_files = archive_named_files(out_dir, assets_dir, AI_BRIEF_FILES, "ai_briefs")
    comments = archive_comments(out_dir, assets_dir, comments_json, comments_csv)

    manifest = {
        "schema": "dy-note-assets-v1",
        "generated_at": now_iso(),
        "out_dir": str(out_dir),
        "assets_dir": str(assets_dir),
        "assets": {
            "transcripts": transcript_files,
            "comments": comments,
            "metadata": metadata_files,
            "ai_briefs": brief_files,
        },
        "learning_contract": LEARNING_CONTRACT,
        "recommended_use": [
            "DyNote 是学习工具：先沉淀数据资产，再按用户问题生成学习笔记。",
            "后续评论洞察、需求聚类和用户研究优先读取 assets/comments/comments.rows.jsonl 或 comments.full.csv。",
            "后续内容总结、RAG 和引用优先读取 assets/transcripts/transcript.txt 与 segments.json。",
            "不要只依赖最终学习笔记；需要复核时回到 assets 下的原始材料。",
        ],
    }
    write_json(assets_dir / "asset_manifest.json", manifest)
    readme = [
        "# DyNote 资产包",
        "",
        "这个目录保存可复用的数据资产。DyNote 的原则是：资产先行，笔记后置。",
        "",
        "学习笔记不是唯一结论，而是基于这些资产、按当前用户问题生成的一种视图。后续换问题、换角度或做复核时，应先回到 `asset_manifest.json` 和原始资产。",
        "",
        "- `transcripts/`：字幕、转写文本、时间片段和本地识别结果。",
        "- `comments/`：完整评论 JSON/CSV 备份、JSONL 明细和可读 Markdown。",
        "- `metadata/`：来源、预算、运行报告和评分。",
        "- `ai_briefs/`：抖音问 AI / 豆包快读结果，作为低等级补充证据。",
        "",
        "入口文件：`asset_manifest.json`。",
    ]
    (assets_dir / "README.md").write_text("\n".join(readme).rstrip() + "\n", encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive DyNote outputs into reusable transcript/comment assets.")
    parser.add_argument("--out-dir", required=True, type=Path, help="DyNote output directory.")
    parser.add_argument("--assets-dir", type=Path, help="Defaults to <out-dir>/assets.")
    parser.add_argument("--comments-json", type=Path, help="Optional explicit douyin_comments_*_full.json path.")
    parser.add_argument("--comments-csv", type=Path, help="Optional explicit douyin_comments_*_full.csv path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_asset_package(args.out_dir, args.assets_dir, args.comments_json, args.comments_csv)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
