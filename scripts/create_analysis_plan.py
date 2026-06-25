#!/usr/bin/env python3
"""Create a systematic DyNote analysis plan before extraction or synthesis."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODE_DEFAULTS: dict[str, dict[str, Any]] = {
    "single-video-note": {
        "unit": "one Douyin video",
        "questions": ["What is the video about?", "What can be learned or reused?", "What evidence supports the note?"],
        "evidence": ["share_text", "page_metadata", "doubao_brief", "asr_transcript", "note_budget"],
        "artifacts": ["transcript.txt", "segments.json", "metadata.json", "note_budget.json", "learning_note.md"],
        "stopping": "Stop after ASR transcript, note budget, and uncertainty notes are sufficient for the requested note.",
    },
    "comment-insight": {
        "unit": "one video comment section",
        "questions": ["What do viewers care about?", "What objections or demand signals appear?", "Which comments change the interpretation of the video?"],
        "evidence": ["page_metadata", "comment_sample", "asr_transcript_if_needed", "theme_clusters"],
        "artifacts": ["comments.json", "comments.csv", "comment_insight.md", "sampling_note.md"],
        "stopping": "Stop when comment sample size and coverage are reported and new pages add few new themes.",
    },
    "account-analysis": {
        "unit": "one Douyin account sampled across videos",
        "questions": ["What is the account positioning?", "What recurring formats and hooks exist?", "Which videos deserve deeper extraction?"],
        "evidence": ["video_sample_table", "metadata", "selected_doubao_briefs", "selected_asr_transcripts", "comments_for_key_videos"],
        "artifacts": ["sample_table.csv", "account_analysis.md", "selection_rationale.md"],
        "stopping": "Stop after a balanced sample by recency, visible engagement, and format diversity is analyzed.",
    },
    "topic-research": {
        "unit": "a topic, hashtag, keyword, or competitor set",
        "questions": ["What patterns define the topic?", "Which videos/accounts are representative?", "What gaps or opportunities appear?"],
        "evidence": ["search_query_log", "sample_table", "metadata", "selected_briefs", "selected_comments_or_asr"],
        "artifacts": ["topic_sample.csv", "topic_research.md", "evidence_matrix.json"],
        "stopping": "Stop after sample strategy, inclusion criteria, and remaining blind spots are explicit.",
    },
    "script-mining": {
        "unit": "one or more videos as script and visual examples",
        "questions": ["What is the hook?", "What beat sequence keeps attention?", "Which parts are reusable?"],
        "evidence": ["doubao_visual_hypothesis", "asr_transcript", "keyframes_if_visual_claims_matter", "comments_if_available"],
        "artifacts": ["script_breakdown.md", "hook_bank.md", "shot_or_beat_table.csv"],
        "stopping": "Stop after the reusable template is separated from observations and unverified visual hypotheses.",
    },
    "commerce-analysis": {
        "unit": "one offer, product, store, course, or service video",
        "questions": ["What is being sold?", "What proof and CTA appear?", "What objections or conversion risks appear?"],
        "evidence": ["page_metadata", "asr_transcript", "comments", "keyframes_for_offer_or_price", "external_check_if_factual"],
        "artifacts": ["commerce_analysis.md", "offer_evidence_table.json"],
        "stopping": "Stop after offer, trust proof, objections, and unverifiable claims are separated.",
    },
    "fact-check": {
        "unit": "claims inside one or more videos",
        "questions": ["What exact claims are made?", "Which claims are high-stakes?", "What external evidence supports or contradicts them?"],
        "evidence": ["asr_transcript", "claim_table", "external_sources", "source_quality_notes"],
        "artifacts": ["claim_table.md", "fact_check.md", "source_log.json"],
        "stopping": "Stop only after high-stakes claims have source labels or are marked insufficient evidence.",
    },
    "knowledge-archive": {
        "unit": "one or more videos archived for retrieval",
        "questions": ["What raw material must be preserved?", "What metadata makes it searchable?", "What future questions should this support?"],
        "evidence": ["raw_package", "metadata", "tags", "note_budget", "provenance"],
        "artifacts": ["transcript.txt", "segments.json", "metadata.json", "note_budget.json", "archive_note.md"],
        "stopping": "Stop after provenance, tags, raw files, and coverage limits are written.",
    },
}


EVIDENCE_LADDER = [
    {"level": "E0", "name": "user_input", "meaning": "User-provided URL, share text, or task framing."},
    {"level": "E1", "name": "page_metadata", "meaning": "Observed page title, description, author, duration, interaction fields."},
    {"level": "E2", "name": "doubao_brief", "meaning": "Logged-in Doubao quick interpretation; classify search-derived/visual-claimed/blocked/weak."},
    {"level": "E3", "name": "asr_transcript", "meaning": "Local ASR or provided transcript; supports text claims but may contain recognition errors."},
    {"level": "E4", "name": "comments", "meaning": "Fetched visible comments and replies; useful for audience signal, not representative public opinion."},
    {"level": "E5", "name": "keyframes", "meaning": "Screenshots/keyframes used to confirm visual claims."},
    {"level": "E6", "name": "external_sources", "meaning": "Independent sources for high-stakes factual verification."},
]


def parse_sources(values: list[str]) -> list[dict[str, str]]:
    sources = []
    for index, value in enumerate(values, start=1):
        kind = "url" if value.startswith(("http://", "https://")) else "text"
        sources.append({"id": f"S{index:02d}", "kind": kind, "value": value})
    return sources


def build_plan(mode: str, objective: str, sources: list[str], tier: str) -> dict[str, Any]:
    defaults = MODE_DEFAULTS[mode]
    required_evidence = list(defaults["evidence"])
    if tier == "quick-pass":
        required_evidence = [item for item in required_evidence if item in {"share_text", "page_metadata", "doubao_brief", "metadata", "sample_table", "video_sample_table"}]
    elif tier == "research-pass":
        required_evidence.extend(["sampling_log", "negative_cases", "uncertainty_register"])
    return {
        "schema": "dy-note-analysis-plan-v1",
        "mode": mode,
        "tier": tier,
        "objective": objective,
        "unit_of_analysis": defaults["unit"],
        "research_questions": defaults["questions"],
        "sources": parse_sources(sources),
        "sampling_strategy": {
            "default": sampling_default(mode),
            "avoid": [
                "Do not treat one viral video as representative of a topic.",
                "Do not treat comments as a statistically representative survey.",
                "Do not escalate to batch ASR before a quick sample shows why it is needed.",
            ],
        },
        "evidence_ladder": EVIDENCE_LADDER,
        "required_evidence": required_evidence,
        "planned_artifacts": defaults["artifacts"],
        "analysis_rules": [
            "Separate observations, model summaries, external facts, and agent inferences.",
            "Label Doubao output as search-derived, visual-claimed, blocked, or weak.",
            "Record sample size, collection time, and inclusion criteria for multi-video/comment tasks.",
            "Look for at least one counterexample or uncertainty before writing strong conclusions.",
            "Write scope limits when data is partial, missing, or platform-filtered.",
        ],
        "synthesis_gate": {
            "may_synthesize_when": [
                "The requested tier has enough evidence or missing evidence is explicitly listed.",
                "Raw artifacts and provenance are saved where applicable.",
                "Claims are labeled by evidence level.",
            ],
            "must_not_claim": [
                "Verified keyframe analysis when only Doubao search-derived text exists.",
                "Complete transcript when only title, caption, chapter summary, or partial ASR exists.",
                "Audience consensus from a small or platform-filtered comment sample.",
            ],
        },
        "stopping_criteria": defaults["stopping"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def sampling_default(mode: str) -> str:
    if mode == "account-analysis":
        return "Sample by recency, visible engagement, and format diversity; deep-process only selected videos."
    if mode == "topic-research":
        return "Start with a bounded sample across query variants; record inclusion/exclusion criteria."
    if mode == "comment-insight":
        return "Fetch visible comments and replies at low speed; report row count, main/reply split, and coverage limits."
    if mode == "fact-check":
        return "Extract exact claims first, then prioritize high-stakes or surprising claims for external verification."
    return "Start with one source, choose quick/evidence/research tier, and escalate only when the question needs it."


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a systematic DyNote analysis_plan.json.")
    parser.add_argument("--mode", choices=sorted(MODE_DEFAULTS), default="single-video-note")
    parser.add_argument("--objective", default="Analyze Douyin material into a reliable learning note.")
    parser.add_argument("--source", action="append", default=[], help="URL or share text. May be repeated.")
    parser.add_argument("--tier", choices=["quick-pass", "evidence-pass", "research-pass"], default="evidence-pass")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="Defaults to <out-dir>/analysis_plan.json")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing analysis_plan.json")
    args = parser.parse_args()

    out_path = args.out or args.out_dir / "analysis_plan.json"
    if out_path.exists() and not args.force:
        existing = json.loads(out_path.read_text(encoding="utf-8-sig"))
        if isinstance(existing, dict):
            existing["reused_existing"] = True
        print(json.dumps(existing, ensure_ascii=False, indent=2))
        return 0

    plan = build_plan(args.mode, args.objective, args.source, args.tier)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
