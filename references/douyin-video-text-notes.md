# DyNote Video Text Notes

## Scope

DyNote extracts and analyzes readable Douyin material for notes, writing, research, and knowledge-base reuse. It is not a general subtitle editor. Prefer clean prose outputs over timestamp-heavy files unless the user explicitly asks for subtitles.

## Extraction Routes

1. Local transcript cleanup: SRT, Whisper JSON, Qwen JSON, or TXT -> `transcript.cleaned.md`, `transcript.txt`, `segments.json`, `metadata.json`.
2. Logged-in Douyin Web AI brief: Douyin URL/share text -> current Chrome Douyin page -> built-in `问AI` / `识别画面` -> `douyin_ai_brief.md`, `douyin_ai_brief.json` with evidence classification.
3. Browser video extraction: Douyin URL -> web-access Chrome tab -> video URL -> local media file -> 16 kHz WAV -> Whisper or Qwen3-ASR -> clean text outputs.
4. Logged-in Doubao fallback brief: full Douyin share text -> current Chrome Doubao chat -> `doubao_brief.md`, `doubao_brief.json` with evidence classification.
5. Official page text: description, author, duration, chapters, and summary are metadata. Treat them as context, not as full transcript.

## Douyin Subtitle Reality And Task Routing

Douyin is not like Bilibili for transcript availability. Many videos have no independent subtitle file, so DyNote should route by the user's requested task instead of always downloading audio and running ASR.

Default routing:

- Quick understanding, topic triage, first draft, or "what is this video about": use logged-in Douyin Web built-in AI first when available. Use Doubao only as a fallback or cross-check.
- Detailed learning note, exact wording, quoteable transcript, script mining, fact-checking, or publishable material: use an available SRT/VTT/TXT first; otherwise run local ASR. Chinese or unspecified language should prefer shared Qwen3-ASR; foreign-language videos should use Whisper-family backends.
- Visual claims, on-screen text, stickers, step-by-step demonstrations, product/price proof, shot sequence, or scene details: use Douyin `识别画面`, keyframes/screenshots, OCR, or manual visual checks. Doubao `evidence` is only a fallback hypothesis. ASR alone is insufficient.

Douyin subtitles commonly appear in two forms:

- Independent subtitle track: creators may use platform-generated subtitles or upload SRT; the web player can render a VTT-like track. If captured, this is usable transcript evidence.
- Burned-in on-screen text: captions, stickers, overlays, and manually rendered text are part of the video frame. They have no separate subtitle file. Audio transcription cannot read them; use OCR/keyframes or visual interpretation.

If `note_budget.json` reports `visual_dependency.risk` as `medium` or `high`, surface that warning to the user. Do not turn sparse ASR into a confident full-video note. Either supplement visual evidence or explicitly label the note as based only on available audio/text evidence.

## Raw Package And Learning Notes

DyNote follows the same product logic as BiliNote: preserve raw material first, then write a knowledge-learning note from the evidence. A good run should leave enough local material for a later agent to re-check the summary without opening Douyin again.

Raw material includes:

- `transcript.cleaned.md` and `transcript.txt`: readable transcript material.
- `segments.json`: ordered transcript segments for evidence lookup.
- `metadata.json` and `page_metadata.json`: source URL, author, duration, interaction stats when available, output list, and generation time.
- `note_budget.json`: recommended note length and granularity.
- `douyin_ai_brief.md` and `douyin_ai_brief.json`: built-in Douyin AI chapters, timeline, optional current-frame context, and evidence level.
- `doubao_brief.md` and `doubao_brief.json`: fallback fast search/visual hypothesis with evidence level.
- comment JSON/CSV from `douyin-comments`, when the task needs audience or interaction signals.
- screenshots/keyframes, when visual claims matter.

Do not skip the raw package when the user asks for a useful note. Short final answers can still be delivered, but the durable local output should keep the source material and budget.

## Efficient Execution Protocol

Systematic does not mean exhaustive. Before running any expensive step, inspect existing artifacts and choose the smallest next action that can answer the research question.

Use `inspect_workflow_state.py --out-dir <dir> --mode <mode>` when an output directory already exists. It reports:

- reusable artifacts
- stale budget or score files
- recommended next steps
- steps to avoid rerunning
- conditions that justify `--force`

Reuse rules:

- Reuse `analysis_plan.json` unless the objective, mode, tier, source set, or sampling strategy changed.
- Reuse `douyin_ai_brief.json` unless the source URL changed, the page AI result was weak, or the task now needs frame evidence.
- Reuse `doubao_brief.json` unless Douyin Web AI is unavailable/weak, the full share text changed, or the task now requires fallback `evidence` mode.
- Reuse `transcript.txt`, `segments.json`, and `metadata.json` unless the source media changed, the transcript is visibly bad, or a higher-fidelity backend is requested.
- Reuse comment JSON/CSV unless the requested sample scope changed, replies were previously excluded but now required, or the sample is incomplete.
- Reuse `note_budget.json` unless transcript, metadata, or comments are newer.
- Reuse `note_score.json` unless the note or budget is newer.

Escalation rules:

- `quick-pass -> evidence-pass`: only when the answer depends on exact wording, visual proof, comments, or publishable reliability.
- `evidence-pass -> research-pass`: only when a single video/sample cannot answer a topic, account, competitor, or market question.
- `ASR -> keyframes`: only when visual claims matter and are not already supported by reliable screenshots or user-provided images.
- `Douyin Web AI -> Doubao`: only when the built-in Douyin AI is unavailable, weak, or needs a cross-check.
- `Douyin Web AI / Doubao -> local ASR`: only when quick AI is blocked/weak, when exact wording matters, or when the user wants durable transcript material.

Use `--force` only when an artifact is stale, corrupt, partial, created from the wrong source, or below the requested evidence tier.

## Systematic Analysis Protocol

For anything beyond a casual one-off brief, run DyNote as a small research workflow:

1. Define the research question.
2. Choose the unit of analysis: video, comment section, account, topic, script pattern, commerce offer, or factual claim.
3. Choose the evidence tier: `quick-pass`, `evidence-pass`, or `research-pass`.
4. Write a sampling plan when the task involves more than one video/comment/account.
5. Collect raw artifacts and provenance.
6. Separate observations, model summaries, external facts, and agent inferences.
7. Synthesize only after the evidence gate passes.
8. Write scope limits and uncertainty.

Use `create_analysis_plan.py` for comment, account, topic, competitor, commerce, fact-check, and batch workflows. The generated `analysis_plan.json` should travel with the raw package.

### Evidence ladder

| Level | Evidence | Use | Common failure |
| --- | --- | --- | --- |
| `E0` | User input/share text | Task framing and initial source | May contain marketing copy or copied text errors |
| `E1` | Page metadata | Title, author, duration, visible stats, tags | Caption/hashtags are not full transcript |
| `E2` | Douyin Web AI brief | Built-in page chapters, timeline, and optional current-frame context | Chapter abstracts are not full transcript or full keyframe coverage |
| `E2b` | Doubao fallback brief | Fast interpretation and visual/search hypothesis | Search-derived output is not verified keyframe analysis |
| `E3` | Subtitle track / ASR transcript | Textual claims, narration, dialogue | ASR can mishear names; both may miss burned-in on-screen text |
| `E4` | Comments | Audience language, objections, demand | Not representative of all viewers; platform filtering exists |
| `E5` | Keyframes/screenshots/OCR | Visual details, on-screen text, offer proof, scene sequence | Sparse frames can miss transitions or off-screen context |
| `E6` | External sources | High-stakes factual verification | Source quality and freshness must be checked |

### Sampling rules

- Account analysis: sample by recency, visible engagement, and format diversity. Do not only pick the top video.
- Topic research: record query terms, collection time, inclusion criteria, and exclusions.
- Comment insight: report total rows, main/reply split, and whether replies were included.
- Competitor research: keep a table of account/video/source, reason selected, visible metrics, and extraction depth.
- Batch ASR: process a small pilot set before scaling; deep-process only videos that change the answer.

### Conclusion strength

Label conclusions by strength:

- `observed`: directly seen in transcript, metadata, comments, or keyframes.
- `supported`: supported by multiple evidence types, such as ASR plus comments.
- `hypothesis`: plausible pattern from Douyin Web AI, Doubao fallback, or a small sample.
- `needs-check`: requires keyframes, more samples, or external verification.
- `unsupported`: do not use as a conclusion.

Before writing a strong conclusion, look for at least one counterexample, missing segment, negative comment theme, or alternative explanation. This is the smallest useful anti-bias check.

## Note Budget Logic

`compute_note_budget.py` generates `note_budget.json` from transcript text, segments, metadata, and optional comments. The budget is intentionally a writing guide, not a hard rule.

Budget inputs:

- video duration, from metadata or final segment time
- transcript character count
- estimated evidence blocks from transcript length and segment count
- fetched comment row count, when available
- interaction stats such as likes, comments, collects, shares, plays/views, and publish time

Budget outputs:

- `recommended_note_chars_min` / `recommended_note_chars_max`: default learning-note length range
- `quick_note_chars`: compact brief target
- `deep_note_chars`: upper bound for especially valuable videos
- `transcript_density_chars_per_minute`: how much transcript text exists per minute of video
- `visual_dependency`: risk and warnings when the video is long but transcript text is sparse
- `quality_multiplier`: interaction-based multiplier, normally 0.85-1.4
- `quality_metrics`: why the multiplier changed
- `granularity`: `micro_video`, `short_deep_note`, `structured_explainer`, `medium_deep_dive`, or high-interaction variants
- `writing_guidance`: concrete writing instruction for the note

Use the budget this way:

- Long videos or long transcripts should keep more structure, examples, and evidence.
- Long videos with sparse transcripts should not be expanded from ASR alone. Supplement Douyin Web AI frame evidence, keyframes, OCR, or label the limitation.
- High-interaction videos deserve more attention to audience feedback, reusable hooks, and why the video worked.
- Low-information short videos should not be padded. Summarize the core scene, value, and transferable idea.
- Comments can raise note length only when they add real signal: objections, demand, correction, experience, or reusable language.

After writing the final Markdown note, run `score_dy_note.py --out-dir <raw-output-dir> --note-path <note.md>`. A `too_short` result means the note likely dropped concepts, examples, methods, comments, or boundaries. A `too_long` result means it may be repeating transcript detail instead of distilling learning value.

## Analysis Scenario Router

Use scenario modes to keep the work aligned with the user's real goal:

| Mode | Use when | Minimum evidence | Typical output |
| --- | --- | --- | --- |
| `single-video-note` | One Douyin link/share text needs a summary, transcript, or reusable notes | Share text + Douyin Web AI quick brief; add subtitle/ASR for exact wording and visual evidence when transcript is sparse | `douyin_ai_brief.md`, `transcript.cleaned.md`, concise final brief |
| `comment-insight` | User asks about comments, pain points, demand, objections, FAQ, audience reaction, or "what people care about" | Comment sample plus video metadata; add ASR when comments refer to specific claims | Themes, representative comment clusters, user language, demand signals |
| `account-analysis` | User gives an account/homepage, several videos, or asks about positioning | Recent/sample videos, titles, topics, visible metrics, repeated formats | Positioning map, content pillars, hook patterns, series ideas, publishing rhythm |
| `topic-research` | User asks about a hashtag, keyword, niche, competitor set, or automatic search | Search results/sample list first; escalate only high-value samples | Market/topic map, sample table, pattern summary, candidate videos to process deeply |
| `script-mining` | User wants script拆解, 镜头拆解, hook, rhythm, storyboard, or remix material | Douyin Web AI visual hypothesis + ASR; keyframes when visual claims matter | Hook library, scene sequence, narration structure, reusable script template |
| `commerce-analysis` | Video sells products, local services, courses, store visits, or other offers | Title/description/ASR plus comment sample when possible | Offer, promise, trust proof, objections, CTA, conversion risks |
| `fact-check` | Medical, legal, finance, news, safety, or strong factual claims | Transcript/claim extraction plus web verification from authoritative sources | Claim table, source-backed verdicts, uncertainty notes |
| `knowledge-archive` | User wants Obsidian/RAG/Markdown corpus material | Source URL, author, date, evidence level, transcript/brief | Stable Markdown note with metadata, tags, backlinks, and provenance |

When multiple modes apply, run the cheapest pass that can answer the first decision. For example, an account analysis can start with titles and Douyin Web AI briefs, then choose only the best or most ambiguous videos for ASR.

## Evidence And Cost Tiers

Use a three-tier escalation model:

1. `quick-pass`: full Douyin share text, final page URL, title, hashtags, visible metadata, and logged-in Douyin Web AI output. Use Doubao `fast` only as fallback. Best for "should I care about this?", quick summaries, and topic triage.
2. `evidence-pass`: independent subtitle track or ASR transcript, selected keyframes/screenshots/OCR, comment sample, and manual spot checks. Best for publishable notes, script拆解, commerce analysis, and claims that need support.
3. `research-pass`: batch collection across videos/accounts/search terms, comment clustering, competitor comparison, and repeated pattern scoring. Best for strategic research; report sample size and selection criteria.

Do not spend `research-pass` effort by default just because the user asks whether something is possible. Start with a compact sample, then explain what a larger run would add.

## Douyin Web AI Brief Route

Use this route when the user wants a fast "what is this video about" answer, a rough timeline, first-pass note material, or a visual/context hypothesis. It must use the current web-access Chrome session and the user's logged-in Douyin Web page.

Practical behavior verified on `https://www.douyin.com/jingxuan?modal_id=7655645985318085322`:

- The modal URL can be normalized to `https://www.douyin.com/video/7655645985318085322`.
- The video page exposes a built-in `问AI` area with `章节要点`, a summary paragraph, and timeline items.
- When the video is paused, a visible `识别画面` button can add the current frame to the AI input. This is useful frame context, but it is not automatically a complete frame-by-frame analysis.

Do not:

- Launch a separate unauthenticated browser.
- Export or persist cookies, localStorage, storageState, tokens, or request signatures.
- Call hidden Douyin APIs directly.
- Treat `章节要点` as a complete transcript or complete visual coverage.

Evidence levels:

- `douyin-web-ai-chapters`: useful quick brief from Douyin's built-in page AI; good for triage and drafts.
- `douyin-web-ai-frame-context`: the current paused frame was added to the AI input; still verify visual claims when accuracy matters.
- `weak`: the AI UI exists but no useful chapter/answer was extracted.
- `blocked`: the page has no usable AI UI or appears not logged in/unsupported.

## Doubao Web Brief Route

Use this route only as a fallback or cross-check when Douyin Web AI is unavailable, weak, or the user explicitly asks for Doubao. It must use the current web-access Chrome session and verify that Doubao Web is logged in before submitting anything.

Do not:

- Launch a separate unauthenticated browser.
- Export or persist cookies, localStorage, storageState, tokens, or request signatures.
- Call hidden Doubao APIs directly.
- Present search-derived output as verified keyframe or frame-by-frame visual analysis.

Prefer the full copied Douyin share text because it gives Doubao the title, hashtags, short link, and natural query context. Passing only the final `/video/<id>` URL can trigger "unable to access video" behavior.

Evidence levels:

- `search-derived`: useful quick brief; likely based on Doubao search/reference material plus title/context.
- `visual-claimed`: Doubao claims visual/shot details; verify against local keyframes when accuracy matters.
- `blocked`: Doubao says it cannot access or watch the video. Fall back to ASR/keyframes.
- `weak`: too little detail; fall back or ask for screenshots/share text.

## Scenario-Specific Notes

### Single-video learning note

When the user asks for a note or summary without specifying another mode, produce a learning note rather than a raw transcript dump. Use `note_budget.json` before writing. Recommended structure:

1. `# 标题`
2. `## 学完你应该获得什么`: 3-8 concrete takeaways.
3. `## 一句话总论`: the video's core claim or value.
4. `## 内容地图`: timeline, scene/argument structure, or topic map.
5. `## 核心概念/方法`: explain what matters and how to use it elsewhere.
6. `## 关键细节与证据`: cite transcript, Douyin Web AI brief, Doubao fallback, comments, or keyframes without overloading the note.
7. `## 可迁移用法`: prompts, script patterns, checklists, or next actions.
8. `## 坑点、边界与不确定`: ASR errors, visual uncertainty, missing comments, or facts needing verification.
9. `## 来源与原始材料`: URL, author, evidence level, local raw files, and note budget summary.

For a cooking/outdoor/ASMR video, the learning note can focus on materials, sequence, sensory pacing, editing rhythm, audience demand, and reusable script/shot patterns. For a knowledge video, focus on concepts, claims, reasoning, and practice steps.

### Comment insight

Use comment analysis when the user asks what viewers think, why a video converted, what objections appear, or what future videos should answer. Do not treat comments as a statistically representative survey unless the sample strategy and count support it. Preserve representative phrases, but avoid exposing private contact details or unnecessary personal data.

### Account and topic research

For accounts, prefer a structured sample: recent videos, best-performing visible videos, and recurring series. For topic research, record the search query, collection time, sample size, and why each sample was selected. Separate "format patterns" from "content claims"; the former can be inferred from titles and descriptions, while the latter often needs ASR or verification.

### Script and visual mining

Douyin Web AI is the default fast visual/story hypothesis route. Doubao can still help when full share text triggers search-backed interpretation, but treat visual details from either route as hypotheses unless confirmed with screenshots/keyframes. For script mining, combine:

- opening hook and first 3 seconds
- problem/promise setup
- scene or beat sequence
- proof/authority moments
- CTA or retention loop
- reusable template in the user's target style

### Commerce and local life

Capture the offer, target audience, proof, price/discount if visible, scarcity, CTA, trust-building devices, and comment objections. If the video involves local services, separate store/location facts from creator opinions. Do not infer sales volume from likes/comments alone.

### Fact-checking

Use external verification for high-stakes claims. Label each claim by source:

- `video-text`: directly from transcript or visible page text.
- `doubao-search-derived`: from Doubao's search-backed brief.
- `external-source`: from independent web verification.
- `inference`: the agent's own synthesis from available evidence.

When evidence is missing, say what is missing instead of forcing a verdict.

### Knowledge archive

For durable notes, use stable filenames, keep source URL/author/date/evidence level, and include tags such as topic, account, product, scene type, and workflow status. Store raw `segments.json` next to cleaned Markdown when future retrieval or citation lookup matters.

## Output Patterns

Prefer task-shaped outputs:

- Single video: raw package, note budget, learning note, transcript links, uncertainty.
- Comment insight: analysis plan, sample count, theme clusters, quote snippets, demand signals, suggested follow-up content.
- Account analysis: sampling table, positioning, content pillars, repeated hooks, best next experiments.
- Topic research: analysis plan, sample table, observed patterns, gaps, videos worth deeper processing.
- Script mining: hook bank, beat sheet, reusable script template, visual uncertainty.
- Commerce: offer analysis, CTA, objections, trust signals, conversion ideas, unverifiable claims.
- Fact-check: claim table with source labels, external source log, confidence and limits.
- Knowledge archive: Markdown note with metadata, tags, evidence level, and raw package paths.

## Known Limitations

- Douyin pages often expose no `<track>` subtitle source.
- A player subtitle switch suggests an independent subtitle track may exist; text that cannot be turned off is probably burned into the video frame and requires OCR/keyframes or visual interpretation.
- `caption` fields may contain only hashtags.
- Chapter abstracts can summarize the video but do not replace full transcript text.
- Doubao may produce rich summaries after "search N keywords / reference N sources"; these are valuable drafts but not proof that Doubao inspected keyframes.
- Signed media URLs should be considered sensitive temporary transport details. Do not print them in final answers or write them to docs.
- Whisper can misrecognize titles and names. For note workflows, report likely ASR errors and correct only when context is strong or the user asks for cleanup.
- Qwen3-ASR-0.6B is available as an optional local backend. It usually produces more readable Chinese prose and punctuation than Whisper, but local setup is heavier.
- On an 8GB RTX 4070 Laptop GPU, direct 17-minute audio transcription OOMs. Use chunking; `--qwen-chunk-seconds 60` has been tested successfully.
- Chunk boundaries can create small discontinuities or noisy phrases, especially where dialogue/background audio is ambiguous.

## Output Quality Checks

- `inspect_workflow_state.py` should identify reusable artifacts before rerunning browser, Douyin Web AI, Doubao, ASR, comment fetch, budget, or score stages.
- `transcript.cleaned.md` should start with source metadata and then the text body.
- `analysis_plan.json` should exist for comment/account/topic/competitor/commerce/fact-check/batch workflows.
- `transcript.txt` should remove timecodes and preserve readable natural line breaks; line breaks are acceptable when ASR has little punctuation.
- `segments.json` should preserve original segment order for later evidence lookup.
- `note_budget.json` should exist after `extract_douyin_text.py` runs. If it is missing, run `compute_note_budget.py --out-dir <output>`.
- If `note_budget.json.visual_dependency.needs_visual_review` is true, the final reply and note must warn about sparse transcript coverage or add visual evidence first.
- `score_dy_note.py` should report `ok` for a finished learning note when the user expects a durable note rather than a quick chat answer.
- Qwen `segments.json` stores chunk-level text, not word-level timestamps. It is enough for note material, not precise subtitles.
- Final user replies should link the text outputs first and mention ASR uncertainty when applicable.

## Future Improvements

- Add optional chunk overlap and deduplication for smoother Qwen boundaries.
- Add optional glossary-based post-processing for film titles, names, and technical terms.
- Add optional batch sampling helpers for account/topic research and comment clustering.
