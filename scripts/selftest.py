#!/usr/bin/env python3
"""Lightweight tests for DyNote helpers."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import compute_note_budget as budgeter
import create_analysis_plan as planner
import douyin_web_ai_brief as dwai
import extract_douyin_text as dut
import inspect_workflow_state as state
import score_dy_note as scorer


def test_parse_srt() -> None:
    sample = """1
00:00:00,000 --> 00:00:02,640
为什么都说国产恐怖片的希望在台湾省

2
00:00:02,640 --> 00:00:04,320
其实综合来看就一个原因

3
00:00:04,320 --> 00:00:05,720
因为它真的有鬼
"""
    segments = dut.parse_srt_text(sample)
    assert len(segments) == 3
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 2.64
    assert segments[2]["text"] == "因为它真的有鬼"


def test_make_paragraphs() -> None:
    lines = [
        "为什么都说国产恐怖片的希望在台湾省",
        "其实综合来看就一个原因",
        "因为它真的有鬼",
        "故事发生在台湾省中部。",
        "这里一直流传着一个恐怖传说。",
    ]
    paragraphs = dut.make_paragraphs(lines, max_chars=48)
    assert paragraphs
    joined = "\n".join(paragraphs)
    assert "为什么都说国产恐怖片的希望在台湾省" in joined
    assert "故事发生在台湾省中部。" in joined


def test_build_outputs_from_srt() -> None:
    sample = """1
00:00:00,000 --> 00:00:01,000
第一句话

2
00:00:01,000 --> 00:00:02,000
第二句话。
"""
    with tempfile.TemporaryDirectory() as tmp:
        srt_path = Path(tmp) / "sample.srt"
        metadata_path = Path(tmp) / "metadata.json"
        out_dir = Path(tmp) / "out"
        srt_path.write_text(sample, encoding="utf-8")
        metadata_path.write_text(
            '\ufeff{"aweme_id":"123","desc":"测试视频","duration_ms":2000,'
            '"statistics":{"digg_count":10000,"comment_count":600,"collect_count":2000,"share_count":300,"play_count":100000}}',
            encoding="utf-8",
        )
        report = dut.build_from_local_transcript(
            source_path=srt_path,
            source_kind="srt",
            out_dir=out_dir,
            metadata_path=metadata_path,
            source_url="https://www.douyin.com/video/123",
        )
        assert report["segment_count"] == 2
        assert (out_dir / "transcript.txt").read_text(encoding="utf-8").strip() == "第一句话\n第二句话。"
        md = (out_dir / "transcript.cleaned.md").read_text(encoding="utf-8")
        assert "# 抖音视频文本素材" in md
        assert "第一句话" in md
        budget = json.loads((out_dir / "note_budget.json").read_text(encoding="utf-8"))
        assert budget["quality_metrics"]["quality_tier"] in {"medium", "high"}
        assert report["outputs"]["note_budget"] == "note_budget.json"
        note_path = out_dir / "learning_note.md"
        note_path.write_text("# 学习笔记\n\n这是一个很短的测试笔记。", encoding="utf-8")
        score = scorer.score_note(out_dir, note_path)
        assert score["status"] == "too_short"
        reused = dut.reuse_existing_outputs(out_dir)
        assert reused["reused_existing"] is True
        workflow = state.inspect(out_dir, "single-video-note")
        assert "transcript" in workflow["reusable_artifacts"]
        assert any("ASR" in item for item in workflow["avoid_rework"])


def test_create_analysis_plan() -> None:
    plan = planner.build_plan(
        mode="topic-research",
        objective="分析野外烹饪视频的可复用形式",
        sources=["铁板牛排 炸土豆饼"],
        tier="research-pass",
    )
    assert plan["schema"] == "dy-note-analysis-plan-v1"
    assert plan["mode"] == "topic-research"
    assert "sampling_log" in plan["required_evidence"]
    assert any(item["level"] == "E3" for item in plan["evidence_ladder"])


def test_parse_douyin_web_ai_chapters() -> None:
    sample = """详情
问AI
章节要点
高考没考好是否复读的问题，刘晓艳认为如果是因为紧张没发挥好或不知道没考好的原因，不建议复读。
00:01
引言
提出高考没考好的同学是否要复读的问题。
00:25
紧张没发挥好
如果只是紧张导致没发挥好，不建议复读。
内容由AI生成
"""
    parsed = dwai.parse_chapter_text(sample)
    assert "不建议复读" in parsed["summary"]
    assert len(parsed["timeline"]) == 2
    assert parsed["timeline"][0]["time"] == "00:01"
    assert parsed["timeline"][1]["title"] == "紧张没发挥好"


def test_normalize_douyin_web_ai_source_url() -> None:
    url, aweme_id = dwai.normalize_source_url("https://www.douyin.com/jingxuan?modal_id=7655645985318085322")
    assert aweme_id == "7655645985318085322"
    assert url == "https://www.douyin.com/video/7655645985318085322"


def test_normalize_chapters() -> None:
    chapters = dut.normalize_chapter_list(
        {
            "chapter_list": [
                {"desc": "开头", "detail": "进入主题", "timestamp_ms": 29000},
                {"title": "结尾", "desc": "收束观点", "start_time": 61000},
            ]
        }
    )
    assert chapters[0]["time"] == "00:00:29"
    assert chapters[0]["title"] == "开头"
    assert chapters[0]["desc"] == "进入主题"
    assert chapters[1]["time"] == "00:01:01"
    assert chapters[1]["desc"] == "收束观点"


def test_build_outputs_from_qwen_result() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result_path = Path(tmp) / "qwen_result.json"
        out_dir = Path(tmp) / "out"
        result_path.write_text(
            '{"language":"Chinese","text":"第一句来自 Qwen。\\n第二句继续。","model":"Qwen/Qwen3-ASR-0.6B"}',
            encoding="utf-8",
        )
        report = dut.build_from_qwen_result(
            result_path=result_path,
            out_dir=out_dir,
            metadata={"aweme_id": "qwen-test", "desc": "Qwen 测试"},
            source_url="https://www.douyin.com/video/qwen-test",
        )
        assert report["transcript_source"] == "Qwen3-ASR: Qwen/Qwen3-ASR-0.6B"
        assert report["segment_count"] == 2
        assert "第一句来自 Qwen。" in (out_dir / "transcript.txt").read_text(encoding="utf-8")


def test_build_outputs_from_chunked_qwen_result() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result_path = Path(tmp) / "qwen_chunked.json"
        out_dir = Path(tmp) / "out"
        result_path.write_text(
            '{"model":"Qwen/Qwen3-ASR-0.6B","segments":[{"start":0,"end":60,"text":"第一段。"},{"start":60,"end":120,"text":"第二段。"}]}',
            encoding="utf-8",
        )
        report = dut.build_from_qwen_result(result_path, out_dir, {}, None)
        assert report["segment_count"] == 2
        assert (out_dir / "transcript.txt").read_text(encoding="utf-8").strip() == "第一段。\n第二段。"


def test_asr_backend_argument_accepts_qwen() -> None:
    parser = dut.build_arg_parser()
    args = parser.parse_args(["https://v.douyin.com/example/", "--asr-backend", "qwen3-asr"])
    assert args.asr_backend == "qwen3-asr"


def test_auto_asr_prefers_qwen_for_chinese() -> None:
    original = dut.qwen_available
    try:
        dut.qwen_available = lambda explicit=None: True  # type: ignore[assignment]
        assert dut.resolve_asr_backend("auto", "Chinese") == "qwen3-asr"
        assert dut.resolve_asr_backend("auto", "zh") == "qwen3-asr"
        assert dut.resolve_asr_backend("auto", "English") == "whisper"
    finally:
        dut.qwen_available = original  # type: ignore[assignment]


def test_sparse_transcript_warns_visual_dependency() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        (out_dir / "metadata.json").write_text('{"duration_ms":600000}', encoding="utf-8")
        (out_dir / "transcript.txt").write_text("开头一句。\n结尾一句。", encoding="utf-8")
        (out_dir / "segments.json").write_text('[{"start":0,"end":600,"text":"开头一句。结尾一句。"}]', encoding="utf-8")
        result = budgeter.compute_budget(out_dir)
        assert result["visual_dependency"]["risk"] == "high"
        assert result["visual_dependency"]["needs_visual_review"] is True
        assert result["evidence_warnings"]
        (out_dir / "note_budget.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        workflow = state.inspect(out_dir, "single-video-note")
        assert workflow["warnings"]
        assert "add_visual_evidence_or_warn_sparse_transcript" in workflow["recommended_next_steps"]


def main() -> None:
    test_parse_srt()
    test_make_paragraphs()
    test_build_outputs_from_srt()
    test_create_analysis_plan()
    test_parse_douyin_web_ai_chapters()
    test_normalize_douyin_web_ai_source_url()
    test_normalize_chapters()
    test_build_outputs_from_qwen_result()
    test_build_outputs_from_chunked_qwen_result()
    test_asr_backend_argument_accepts_qwen()
    test_auto_asr_prefers_qwen_for_chinese()
    test_sparse_transcript_warns_visual_dependency()
    print("selftest: ok")


if __name__ == "__main__":
    main()
