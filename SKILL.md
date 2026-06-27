---
name: dy-note
description: "DyNote: systematically and efficiently extract raw Douyin/DY video data and analyze videos, comments, accounts, hashtags, and short-video scenes into evidence-graded learning notes, summaries, research briefs, scripts, and knowledge-base material. Use when the user asks to 抓取/提取/整理 抖音视频字幕、视频文案、ASR 转写、Qwen3-ASR 中文转写、原始材料归档、学习笔记、analysis plan、note budget、避免返工、复用已有素材、评论洞察、账号分析、赛道/话题研究、竞品拆解、电商/本地生活视频分析、事实核查、自动搜索素材, save Douyin content as Markdown/TXT, or use subtitle/local ASR as the factual spine with logged-in Douyin Web built-in AI / Doubao fallback as visual or quick-reading supplements."
---

# DyNote

DyNote 是面向 Codex 这类 Agent 的抖音学习工具，不是一次性摘要器。核心原则是“数据资产先行，学习笔记后置”：先把字幕/转写、评论、元数据和 AI 快读沉淀为可复用资产，再按用户需求生成可追溯的学习笔记、总结和写作材料。默认目标不是字幕工程文件，而是先落一份原始数据包：`douyin_ai_brief.md`、`douyin_ai_brief.json`、`transcript.cleaned.md`、`transcript.txt`、`segments.json`、`metadata.json`、`note_budget.json`，并用 `assets/` 归档可复用资产。默认把独立字幕轨或本地自动语音识别转写当作事实主干；当转写密度低、任务需要画面理解或用户只要快速筛选时，再用已登录抖音网页版的“问AI / 识别画面”补充，豆包只作为抖音 AI 不可用时的备用快读或待核验假设。

联网或登录态操作必须先使用 `web-access`。不要读取、复制或打印 Cookie、msToken、a_bogus、x-secsdk-web-signature、临时签名视频 URL 等敏感参数；脚本只让已授权 Chrome 页面自己加载内容。

DyNote 与 Bili Note 共享可复用本地资源。默认共享目录是 `%USERPROFILE%\.cache\rimagination-notes`，Qwen3-ASR 环境默认是 `%USERPROFILE%\.cache\rimagination-notes\qwen3-asr-venv`。如果任一 skill 已经安装过 Qwen3-ASR，另一个 skill 必须优先复用，不要重复安装。Hugging Face、Whisper 和 faster-whisper 缓存按本机通用缓存复用。

## 浏览器与登录态硬规则

- 抖音内置 AI 和豆包备用路线都只使用 `web-access` 连接到用户当前可用的 Chrome。不要启动无登录态 Playwright 浏览器，不要用静态 curl 抓登录页，不要导出或保存 `storageState`、Cookie、localStorage 或 token。
- 抖音内置 AI 路线需要当前 Chrome 已登录抖音网页版。它主要用于低转写密度、画面文字、镜头/场景或快速筛选；打开视频后使用页面右侧 `问AI`，必要时点击可见的 `识别画面` 把当前帧加入问答上下文。
- 如果抖音页面没有 `问AI` / `识别画面` 或未生成 `章节要点`，记录为 `weak` 或 `blocked`，先确保字幕/本地自动语音识别事实主干可用，再考虑豆包备用、关键帧或 OCR。
- 在向豆包发送内容前，必须确认 `https://www.doubao.com/chat/` 在当前 Chrome 中已登录且有可见聊天输入框、侧边栏/新对话等用户态界面。
- 如果未检测到豆包登录态，停止并返回 `blocked: doubao-login-required`，提示用户先在同一个 Chrome 登录豆包。不要静默降级到其他浏览器。
- 豆包备用快速解读优先使用用户复制的完整抖音分享文本，不要只喂最终 `douyin.com/video/...`，因为完整分享文案更容易触发豆包的搜索/参考资料式视频概述。
- 豆包输出需要做证据分级：`search-derived` 是检索式概述，`visual-claimed` 是声称包含画面/镜头细节，`blocked` 是豆包无法访问视频画面，`weak` 是信息不足。不要把检索式概述说成逐帧视觉解析，也不要让豆包替代完整字幕或本地转写。

## 抖音字幕现实与默认路线

抖音和 B 站不同：很多抖音视频没有可直接抓取的独立字幕文件。先按用户任务分流，不要固定把所有视频都下载转写。

- 用户只是问“这个视频讲什么”、想做选题筛选、草稿或快速理解时，可以走已登录抖音网页版内置 AI 快读；但输出必须标注为快读/视觉假设，不写成完整字幕提取。已有 `douyin_ai_brief.json` 时先复用；如果不可用，再用豆包 `fast` 备用。
- 用户要学习笔记、可靠原文、逐句内容、引用、脚本拆解、事实核查或可发布材料时，先找已有 SRT/VTT/TXT；没有可用字幕轨或转写时，主要依赖本地自动语音识别。中文或未指定语言优先共享 Qwen3-ASR，明确外语视频再用 Whisper 系后端。
- 用户要镜头、画面文字、贴纸文字、操作步骤、商品/价格/场景细节，或 `note_budget.json` 显示转写密度低时，不能只靠音频转写；优先补抖音 `问AI / 识别画面`、关键帧、截图或 OCR。抖音 AI 仍不能提取完整字幕；豆包 `evidence` 只作为抖音 AI 不行时的备用视觉假设。

抖音字幕常见两种形态：

- 独立字幕轨：创作者使用平台字幕功能或上传 SRT 后，网页播放器可能叠加渲染 VTT 字幕。若能抓到这类轨道，可作为逐句文本材料。
- 画面内嵌文字：字幕、贴纸或手动排版文字已经焊在画面里，没有独立文件。音频转写只能识别人声，不能读取这类画面文字，必须补视觉证据。

如果视频较长，但 `note_budget.json` 中 `visual_dependency.risk` 为 `medium` 或 `high`，必须提醒用户：转写文本过少，完整理解可能依赖画面，不能把稀疏本地自动语音识别结果写成完整笔记。抖音问 AI、豆包和关键帧结果必须作为补充证据审计，不能替代原文主干。

## 场景模式路由

先判断用户真正要完成的任务，再决定证据深度和工具路线：

- `single-video-note`：默认模式。单条视频/分享文本 -> 字幕/本地自动语音识别做事实主干；转写稀疏或任务需要画面时补抖音问 AI、关键帧/OCR；抖音 AI 不可用时豆包才作为备用假设，输出可读笔记。
- `comment-insight`：用户关心评论、痛点、需求、FAQ、反对意见或爆点反馈时，加载 `douyin-comments`。默认只抓前 100 条主评论及这些主评论的楼中楼，输出 `_sample.json/csv`，并明确提示这不是全部评论。用户明确要完整评论资产、复核全部可见评论或样本不足时，再用 `--full` 做全量抓取。抓到的 JSON/CSV 必须归档到 `assets/comments/`，再输出用户洞察，而不是只把评论写进一次性总结。
- `account-analysis`：账号主页或多条视频 -> 定位、内容支柱、钩子模板、系列化栏目、发布节奏和可复用选题。
- `topic-research`：话题、关键词、赛道、竞品或“自动搜索” -> 先低成本收集标题/简介/话题/样本链接，再按需要升级到 ASR、评论和关键帧。
- `script-mining`：拆脚本、镜头、叙事节奏、开头钩子、转场、结尾 CTA；脚本文案以字幕/本地转写为主，抖音内置 AI 或备用豆包只给画面假设，重要结论要用转写/抽帧校验。
- `commerce-analysis`：带货、本地生活、探店、课程或服务视频 -> 卖点、信任证据、价格/优惠、CTA、转化阻力和评论需求。
- `fact-check`：涉及医学、法律、投资、新闻或强事实判断时，区分视频原文、抖音内置 AI/豆包概述和外部来源；高风险结论必须联网核验并标注来源。
- `knowledge-archive`：用户要沉淀资料库、Obsidian、RAG 或写作素材时，保留来源 URL、作者、时间、证据等级、关键词和后续可检索标签。

成本分层默认从轻到重：

- `quick-pass`：分享文本、页面元数据、抖音内置 AI，必要时备用豆包 `fast`；适合秒级判断、选题筛选和草稿，但必须标注不是完整字幕/全文证据。
- `evidence-pass`：独立字幕轨或 ASR 全文、关键帧/OCR、评论样本；适合要引用、拆解或发布的内容。
- `research-pass`：批量视频、账号/话题搜索、竞品对比和评论聚类；范围大时先给样本计划和 token/时间风险。

## 系统化分析协议

默认按“问题 -> 取证 -> 分析 -> 审计”推进，不要把工具输出直接等同于结论：

1. `research-question`：写清要回答的问题、分析单位和场景模式。复杂任务先生成 `analysis_plan.json`。
2. `sampling-plan`：账号、话题、评论或竞品任务必须说明样本怎么选、样本量是多少、为什么足够或不足。
3. `evidence-ladder`：把证据分为用户输入、页面元数据、独立字幕轨/本地自动语音识别转写、抖音内置 AI、备用豆包快读、评论、关键帧/OCR、外部来源。字幕/转写是事实主干；抖音 AI 和豆包是快读或视觉补充。结论必须标注依赖哪一层。
4. `synthesis-gate`：合成前先读取 `assets/asset_manifest.json` 或确认同等原始材料，检查证据等级、覆盖范围和反例/不确定性；缺证据时先写范围限制，不要补故事。
5. `audit-trail`：最终笔记或研究简报保留来源 URL、采集时间、输出文件、样本范围、`note_budget.json` 和无法验证的点。

## 高效执行与复用策略

- 先检查已有产物，再决定下一步。已有 `douyin_ai_brief.json` 时，不要重复问抖音内置 AI；已有 `doubao_brief.json` 时，不要重复问豆包；已有 `transcript.txt`、`segments.json`、`metadata.json` 时，不要重跑 ASR；已有 `note_budget.json` 且未过期时，不要重算预算。
- `analysis_plan.json` 只在复杂任务或目标变化时创建；已有计划默认复用。目标、来源、模式或证据等级变化时才用 `--force` 重建。
- 先走最便宜的 `quick-pass`，只有当研究问题无法回答、证据等级不足、或用户要可发布笔记/事实核查时，才升级到 `evidence-pass` 或 `research-pass`。评论区任务的 `quick-pass` 是前 100 条主评论及对应楼中楼样本；全量可见评论属于更重的资产补齐步骤。
- 不要为了“完整流程”固定执行所有步骤。单条视频如果已有高质量转写，可直接预算和写笔记；评论洞察如果只问观众反馈，可以先抓 100 条评论样本，不必先全量 ASR，也不必默认抓完整评论区。
- 重新运行昂贵步骤前必须说明触发条件：输入变了、旧文件缺失/损坏/过期、证据等级不足，或用户明确要求更高质量。

## 原始材料与学习笔记默认策略

- 默认先建立数据资产，再写学习笔记。不要只把抖音内置 AI、豆包概述或未经审计的本地自动语音识别文本直接当最终笔记。
- `douyin_ai_brief.json`、`doubao_brief.json`、`transcript.txt`、`segments.json`、`metadata.json`、评论 JSON/CSV 和关键帧截图都属于原始数据；最终学习笔记必须能回到这些材料解释来源。
- 默认把字幕/转写和完整评论整理成资产包：`assets/transcripts/` 保存字幕、转写和片段；`assets/comments/` 保存完整评论 JSON/CSV、JSONL 明细和可读 Markdown；`assets/asset_manifest.json` 是后续再分析的入口。
- `assets/asset_manifest.json` 是事实入口；`learning_note.md` 是从资产生成的一种学习视图，不是资产本身。用户换问题、换场景或要求复核时，优先复用资产重新组织笔记，不要重跑或覆盖原始材料。
- 写笔记前先确认用户需求：内容学习、脚本复盘、评论洞察、事实核查、写作素材或知识库归档。再从资产中选择证据和结构，不要先脑补结论再找材料。
- 每次生成转写材料后读取 `note_budget.json`。它根据视频时长、转写字数、片段/证据块、评论数和互动质量给出推荐笔记长度。
- 长视频、长转写、高评论或高互动视频要写更长、更结构化的笔记；短视频或低信息密度视频避免过度扩写。
- 互动质量是“值得多写”的辅助信号，不替代证据。扩写必须来自视频原文、评论样本、关键帧、外部核验，或已明确降级为视觉假设的抖音内置 AI/豆包快读。
- 学习型笔记要让读者像学完一个短课题：获得概念、判断标准、方法步骤、适用边界、坑点和可迁移用法。不要只写“视频讲了什么”。

## 默认流程

1. 读清用户要的是哪种场景模式：单条视频笔记、评论洞察、账号分析、话题研究、脚本拆解、电商分析、事实核查，还是知识库归档。
2. 首次使用、换机器、或准备跑完整抖音链接流程时，先检查环境：

```powershell
$skill = "$env:USERPROFILE\.codex\skills\dy-note"
$py = "python"
& $py "$skill\scripts\check_environment.py"
```

3. 如果有输出目录，先运行或心中执行 `inspect_workflow_state.py`，复用已有计划、抖音内置 AI brief、豆包 brief、转写、评论、预算和评分。
4. 评论、账号、话题、竞品、事实核查或批量研究任务先用 `create_analysis_plan.py` 生成 `analysis_plan.json`；已有计划且目标没变时不要重建。单条视频任务也要在脑中执行同样的证据闸门。
5. 如果已经有 SRT、Whisper JSON 或 TXT，优先走本地整理路线，避免重复下载和转写；脚本会生成 `note_budget.json`。
6. 如果用户要求可靠全文、学习笔记、逐句内容、引用、脚本拆解或事实核查，优先使用 `extract_douyin_text.py` 取得字幕轨或本地自动语音识别转写。默认 `--asr-backend auto`：中文或未指定语言优先共享 Qwen3-ASR，明确外语视频优先 Whisper。默认复用已有输出；需要重跑时加 `--force`。
7. 如果用户只是快速理解、选题筛选或先拿草稿，且当前 Chrome 已登录抖音网页版，可以跑 `douyin_web_ai_brief.py`；已有可用 `douyin_ai_brief.json` 时先读旧结果。抖音内置 AI 不可用、弱，或 `note_budget.json` 显示低转写密度时，再用 `doubao_video_brief.py` 的 `fast/evidence` 模式备用，但必须标注为假设。
8. 评论、账号、话题、竞品或批量研究任务先做 `quick-pass` 样本，不要直接对大量视频逐条 ASR；样本结论不足时再升级到 `evidence-pass` 或 `research-pass`。大评论区默认用 `fetch_douyin_comments.py` 抓前 100 条主评论及对应楼中楼；需要完整可见评论时再显式加 `--full`，不要黑盒等待一轮全量抓取。
9. 每次得到转写、字幕、评论 JSON/CSV、抖音 AI brief 或豆包 brief 后，运行 `archive_dy_note_assets.py` 生成或更新 `assets/`。评论区任务必须保留评论样本或完整评论资产，不能只输出评论摘要。
10. 写学习笔记前，先打开 `assets/asset_manifest.json`，再按用户需求读取 `transcript.cleaned.md`、`segments.json`、完整评论、`douyin_ai_brief.md`、`doubao_brief.md` 或 `analysis_plan.json`，检查证据是否足以回答研究问题。再打开 `note_budget.json`，按推荐长度和 `writing_guidance` 写学习型笔记；如果 `visual_dependency.needs_visual_review=true`，必须在笔记和回复中提醒画面证据不足，或先补抖音 `问AI / 识别画面`、关键帧/OCR。对外部 AI 回答逐项做证据审计，不要把它们的扩写混成视频原文。
11. 如果识别出片名、人名、地名明显错，优先在最终说明里标注可疑词；用户要求校对时再做替换、二次 ASR 或补关键帧。
12. 用户明确要 SRT/VTT/时间轴时，才单独交付字幕文件；无论是否单独交付，都要在 `assets/transcripts/` 里保留可复用文本资产。

## 常用命令

### 0. 检查已有工作状态

已有输出目录时先检查状态，决定下一步，不要盲目重跑：

```powershell
& $py "$skill\scripts\inspect_workflow_state.py" `
  --out-dir ".\dy_note_output" `
  --mode "single-video-note"
```

重点看：

- `reusable_artifacts`：可以直接复用的产物。
- `recommended_next_steps`：真正缺的下一步。
- `avoid_rework`：明确不要重复做的昂贵步骤。
- `stale.note_budget` / `stale.note_score`：预算或评分是否因新材料而过期。

### 1. 创建系统化分析计划

复杂任务先生成计划，再采集数据。单条视频可省略显式文件，但账号/话题/评论/竞品/事实核查任务建议保留：

```powershell
& $py "$skill\scripts\create_analysis_plan.py" `
  --mode "topic-research" `
  --tier "quick-pass" `
  --objective "分析这个赛道里什么视频形式值得复用" `
  --source "铁板牛排 炸土豆饼 野外烹饪" `
  --out-dir ".\dy_note_research"
```

如果 `analysis_plan.json` 已存在，脚本默认复用旧计划；只有目标、来源、模式或证据等级改变时才加 `--force` 覆盖。

常用模式：`single-video-note`、`comment-insight`、`account-analysis`、`topic-research`、`script-mining`、`commerce-analysis`、`fact-check`、`knowledge-archive`。

### 2. 从已有 SRT 生成干净文本

```powershell
& $py "$skill\scripts\extract_douyin_text.py" `
  --from-srt "D:\微信推送\douyin_subtitles_7647145112421633320\7647145112421633320_16k.srt" `
  --metadata-json "D:\微信推送\douyin_subtitles_7647145112421633320\official_detail_summary.json" `
  --out-dir "D:\微信推送\dy_note_7647145112421633320"
```

### 3. 从 Whisper JSON 或 TXT 生成干净文本

```powershell
& $py "$skill\scripts\extract_douyin_text.py" `
  --from-whisper-json ".\audio_16k.json" `
  --out-dir ".\dy_note_output"

& $py "$skill\scripts\extract_douyin_text.py" `
  --from-txt ".\raw_transcript.txt" `
  --source-url "https://www.douyin.com/video/..." `
  --out-dir ".\dy_note_output"
```

### 4. 安装或检查共享 Qwen3-ASR 本地环境

Qwen3-ASR 是中文视频优先使用的本地自动语音识别后端。首次使用时安装到共享 venv，复用现有 CUDA Torch；DyNote 和 Bili Note 共用同一套环境：

```powershell
& $py "$skill\scripts\setup_qwen_asr_env.py"
& $py "$skill\scripts\check_environment.py"
```

看到 `routes.qwen3_asr=OK` 后再使用 Qwen 后端。本机默认 venv 路径是：

```text
%USERPROFILE%\.cache\rimagination-notes\qwen3-asr-venv
```

为兼容早期原型，脚本仍会探测旧路径 `%USERPROFILE%\.cache\dy-note\qwen3-asr-venv` 和 `%USERPROFILE%\.cache\douyin-note\qwen3-asr-venv`。

### 5. 从抖音链接完整提取

先按 `web-access` 要求启动并检查 CDP proxy，再运行：

```powershell
& $py "$skill\scripts\extract_douyin_text.py" `
  "https://v.douyin.com/xxxxxxx/" `
  --out-dir "D:\微信推送\dy_note_output" `
  --asr-model medium `
  --language Chinese
```

如果输出目录已有 `transcript.txt`、`segments.json` 和 `metadata.json`，脚本默认复用并跳过浏览器、下载和 ASR。确实要重跑时加：

```powershell
--force
```

中文长视频默认优先用 Qwen3-ASR-0.6B。8GB 显存建议保留默认 60 秒分段，避免整段长音频 OOM：

```powershell
& $py "$skill\scripts\extract_douyin_text.py" `
  "https://v.douyin.com/xxxxxxx/" `
  --out-dir "D:\微信推送\dy_note_output_qwen" `
  --asr-backend qwen3-asr `
  --qwen-model "Qwen/Qwen3-ASR-0.6B" `
  --qwen-chunk-seconds 60 `
  --language Chinese
```

脚本会输出：

- `transcript.cleaned.md`：适合阅读和继续写笔记的 Markdown。
- `transcript.txt`：纯文本正文，适合喂给总结、RAG 或写作流程。
- `segments.json`：按原始字幕/ASR 片段保留的结构化文本。
- `metadata.json`：来源、作者、作品 ID、片段数、生成时间和输出清单。
- `note_budget.json`：按时长、转写字数、片段数、评论量和互动质量生成的推荐学习笔记长度，以及转写过稀时的画面依赖提示。
- `page_metadata.json`、视频、音频、Whisper SRT 或 Qwen JSON：完整流程产生的中间材料，供排错和回查使用。

### 6. 从已有音频使用 Qwen 转写

```powershell
& $py "$skill\scripts\extract_douyin_text.py" `
  --from-audio "D:\微信推送\video_16k.wav" `
  --asr-backend qwen3-asr `
  --qwen-chunk-seconds 60 `
  --metadata-json ".\metadata.json" `
  --out-dir ".\dy_note_qwen"
```

### 7. 复用已打开的 web-access target

如果已经用 `web-access` 打开抖音页面并拿到 target id：

```powershell
& $py "$skill\scripts\extract_douyin_text.py" `
  "https://www.douyin.com/video/7647145112421633320" `
  --target "CDP_TARGET_ID" `
  --keep-tab `
  --out-dir ".\dy_note_output"
```

不要关闭用户已有 tab；只有脚本自己新建的 tab 可以自动关闭。

### 8. 用抖音内置 AI 快速解读视频

先按 `web-access` 要求启动并检查 CDP proxy。脚本会使用当前 Chrome 打开抖音视频页，优先读取页面 `问AI` 生成的 `章节要点` 和时间线；如果传入的是 `jingxuan?modal_id=...`，会自动归一到更稳定的 `/video/<id>` 页面：

```powershell
& $py "$skill\scripts\douyin_web_ai_brief.py" `
  "https://www.douyin.com/jingxuan?modal_id=7655645985318085322" `
  --out-dir ".\dy_note_douyin_ai_7655645985318085322"
```

如果任务依赖当前画面内容，可尝试把暂停帧加入抖音 AI 输入框：

```powershell
& $py "$skill\scripts\douyin_web_ai_brief.py" `
  "https://www.douyin.com/jingxuan?modal_id=7655645985318085322" `
  --identify-frame `
  --out-dir ".\dy_note_douyin_ai_frame"
```

脚本会输出：

- `douyin_ai_brief.md`：抖音内置 AI 的章节要点、时间线、识别画面状态和局限。
- `douyin_ai_brief.json`：来源 URL、归一化 URL、作品 ID、证据等级、时间线和输出路径。

证据等级为 `weak` 或 `blocked` 时，继续跑备用豆包、本地自动语音识别、关键帧或 OCR；如果只是拿草稿或选题筛选，`douyin-web-ai-chapters` 通常已经够用。

### 9. 用已登录豆包作为备用快读

当抖音内置 AI 不可用、弱、或需要交叉对照时，再走豆包备用路线。先按 `web-access` 要求启动并检查 CDP proxy。脚本会自己打开当前 Chrome 的豆包页并确认登录态；未登录时会停止，不会换浏览器：

```powershell
& $py "$skill\scripts\doubao_video_brief.py" --check-login
```

推荐传入完整分享文本，而不是只传最终视频 URL：

```powershell
& $py "$skill\scripts\doubao_video_brief.py" `
  "8.28 x@F.uf gbA:/ 07/06 :9pm 铁板牛排+炸土豆饼 向阳而生 # 助眠 # 治愈 # 美食 # 野外烹饪 # 牛排 https://v.douyin.com/xxxxxxx/ 复制此链接，打开Dou音搜索，直接观看视频！" `
  --out-dir "D:\微信推送\dy_note_doubao_7580609296384249123" `
  --mode fast
```

要判断豆包是否真的有画面证据，用 `evidence` 模式：

```powershell
& $py "$skill\scripts\doubao_video_brief.py" `
  --from-file ".\douyin_share.txt" `
  --out-dir ".\dy_note_doubao_evidence" `
  --mode evidence
```

脚本会输出：

- `doubao_brief.md`：豆包视频概述、时间线或阻塞说明。
- `doubao_brief.json`：会话 URL、证据等级、是否搜索派生、是否被阻塞、原始分享文本和输出路径。

证据等级为 `blocked` 或 `weak` 时，继续跑完整 ASR/抽帧路线；等级为 `search-derived` 时可作为快速草稿，但最终说明要标注它不是逐帧视觉证据。

### 10. 重新计算学习笔记预算

如果后来补了评论 JSON、改了元数据，或只想根据已有输出重算预算：

```powershell
& $py "$skill\scripts\compute_note_budget.py" `
  --out-dir ".\dy_note_output" `
  --comments-json ".\dy_note_output\douyin_comments_7580609296384249123_full.json"
```

写最终学习笔记前必须看 `note_budget.json` 中的：

- `recommended_note_chars_min` / `recommended_note_chars_max`：默认笔记字数区间。
- `quality_multiplier` / `quality_metrics`：互动质量为何让笔记变长或变短。
- `granularity` / `writing_guidance`：短视频、长讲解、高互动视频分别该用什么粒度写。

写完最终 Markdown 后，用预算做一次长度和信噪比校验：

```powershell
& $py "$skill\scripts\score_dy_note.py" `
  --out-dir ".\dy_note_output" `
  --note-path ".\dy_note_output\learning_note.md" `
  --out ".\dy_note_output\note_score.json"
```

### 11. 归档字幕和评论资产

抓完字幕/转写、评论或 AI brief 后，更新资产包：

```powershell
& $py "$skill\scripts\archive_dy_note_assets.py" `
  --out-dir ".\dy_note_output"
```

如果评论文件在别的目录，可以显式传入：

```powershell
& $py "$skill\scripts\archive_dy_note_assets.py" `
  --out-dir ".\dy_note_output" `
  --comments-json ".\douyin_comments_765xxxx_full.json" `
  --comments-csv ".\douyin_comments_765xxxx_full.csv"
```

资产包包含：

- `assets/transcripts/transcript.txt`、`segments.json`：后续总结、检索和引用的事实主干。
- `assets/comments/comments.sample.json`、`comments.sample.csv`：默认评论样本备份，通常是前 100 条主评论及对应楼中楼。
- `assets/comments/comments.full.json`、`comments.full.csv`：显式 `--full` 后的完整可见评论备份。
- `assets/comments/comments.rows.jsonl`：适合继续做评论聚类、用户需求分析和二次处理。
- `assets/comments/comments.text.md`：适合人工快速浏览的评论全集。
- `assets/asset_manifest.json`：资产入口和覆盖范围。

### 12. 高效抓取评论区

大评论区不要一上来黑盒等待完整评论。默认先抓评论样本：前 100 条主评论及这些主评论下的楼中楼。

```powershell
& $py "$skill\scripts\fetch_douyin_comments.py" `
  "https://www.douyin.com/video/7655645985318085322" `
  --out-dir ".\dy_note_output" `
  --basename "douyin_comments_7655645985318085322"
```

默认输出：

- `douyin_comments_<aweme_id>_sample.json`
- `douyin_comments_<aweme_id>_sample.csv`
- 以及 `douyin_comments_<aweme_id>_main_only_sample.json/csv` checkpoint

如果用户确实需要完整可见评论，再全量抓取：

```powershell
& $py "$skill\scripts\fetch_douyin_comments.py" `
  "https://www.douyin.com/video/7655645985318085322" `
  --out-dir ".\dy_note_output" `
  --basename "douyin_comments_7655645985318085322" `
  --full `
  --main-count 50 `
  --main-page-limit 300 `
  --reply-count 50 `
  --reply-page-limit 50 `
  --main-delay 0.15 `
  --reply-delay 0.05
```

抓完任一阶段都要运行 `archive_dy_note_assets.py`。如果 `coverage.is_sample=true`，最终说明必须提示“这不是全部评论，只是样本”；同时报告 `coverage.total_reported`、`row_count`、主评论数、楼中楼数和 `reported_gap`，不要把平台报告数直接说成已抓取行数。

## 输出口径

- 说清楚文本来源：独立字幕轨、页面文案、已有 SRT/VTT/TXT，还是本地自动语音识别。
- 给用户可复用材料时优先指向 `assets/asset_manifest.json`，不要只给最终学习笔记；评论区分析必须保留 `assets/comments/` 下的样本或完整备份，并说明覆盖范围。
- 最终学习笔记要说明它基于哪些资产生成：字幕/转写、评论、元数据、抖音问 AI、豆包备用或关键帧/OCR。不要把某一版总结说成唯一答案。
- Qwen3-ASR-0.6B 往往比 Whisper 更像可读稿，会自动补标点；但对白、方言、背景音、chunk 边界仍可能错听或插入噪声，不要把它当校对后的定稿。
- 抖音内置 AI 很适合在转写密度低时补章节要点、时间线和画面理解；`识别画面` 只能证明当前帧被加入输入框，不能自动等同于完整逐帧分析或完整字幕提取。
- 豆包 `fast` 模式现在是备用路线；只有抖音问 AI 不可用或质量弱时再用。如果结果包含“搜索 N 个关键词 / 参考 N 篇资料”，按检索式解读使用，不要称为“豆包已看完关键帧”。
- 豆包 `blocked` 结果通常会写“无法访问视频画面”或类似措辞；这时不要继续追问编造，直接回落到本地 ASR/关键帧补充。
- 抖音页面的 `caption`、简介和话题标签不等于完整字幕。只有完整逐句文本才可称为字幕/转写。
- 如果播放器/页面没有独立字幕轨，画面内嵌字幕、贴纸文字和商品/价格信息不能靠本地自动语音识别读取；需要抖音 `问AI / 识别画面`、关键帧、OCR、备用豆包视觉假设或人工检查。
- 如果长视频的转写文本明显很少，必须把 `note_budget.json` 的 `visual_dependency` 提示转述给用户，不要写成“已完整解析”。
- ASR 文本可能有错字，尤其是片名、人名、方言、专有名词和背景音乐压过人声的片段。
- 给用户文件时优先给 `transcript.cleaned.md` 和 `transcript.txt`；`segments.json` 供程序处理。
- 写学习笔记时优先遵守 `note_budget.json`。预算偏长时补概念卡、方法步骤、评论洞察、坑点和自测题；预算偏短时避免把短视频硬扩成长文。
- 如果只抓到简介、章节摘要或部分片段，明确说明覆盖范围，不要写成“已提取完整视频文本”。

## 抖音视频注意事项

- 短链会跳转到 `/video/<aweme_id>` 或 `/note/<aweme_id>`；脚本会通过 Chrome 获取最终 URL。
- 页面可能没有独立字幕轨；中文或未指定语言默认优先共享 Qwen3-ASR，明确外语视频再走 Whisper 系后端。
- 播放器能开关的字幕通常更可能是独立轨道；无法关闭的画面文字通常是内嵌画面，不能按字幕文件处理。
- 临时视频 URL 可能包含签名，不能写入文档、日志或最终回答。
- 抖音风控敏感；不要批量快速打开大量视频，不要复制浏览器凭据。
- 完整流程依赖 `ffmpeg` 和一个 ASR 后端；本地整理已有 SRT/TXT 不依赖它们。
- Qwen3-ASR 单次处理 17 分钟音频会在 8GB 显存上 OOM；使用分段参数，默认 `--qwen-chunk-seconds 60`。

## 相关文件

- `scripts/check_environment.py`：检查 web-access proxy、ffmpeg、Whisper、Qwen3-ASR 和本地模型缓存。
- `scripts/archive_dy_note_assets.py`：把字幕/转写、完整评论、AI brief、元数据和预算整理成 `assets/` 可复用资产包。
- `scripts/compute_note_budget.py`：按转写长度、时长、评论量和互动质量生成 `note_budget.json`，指导学习笔记长短，并提示长视频转写过稀时的画面依赖风险。
- `scripts/create_analysis_plan.py`：按场景模式生成 `analysis_plan.json`，记录研究问题、采样策略、证据阶梯和合成闸门。
- `scripts/douyin_web_ai_brief.py`：使用当前已登录 Chrome 中的抖音网页版“问AI / 识别画面”提取视频章节要点和时间线。
- `scripts/doubao_video_brief.py`：备用路线，使用当前已登录 Chrome 中的豆包网页版，对完整抖音分享文本做快速解读、登录态检查和证据分级。
- `scripts/extract_douyin_text.py`：从抖音链接、本地音频或本地转写文件生成文本素材。
- `scripts/fetch_douyin_comments.py`：通过 web-access CDP proxy 分阶段抓取抖音主评论和楼中楼，支持主评论 checkpoint、续抓回复、进度输出和覆盖率统计。
- `scripts/inspect_workflow_state.py`：检查输出目录已有产物，推荐下一步并提示哪些步骤不要返工。
- `scripts/run_qwen_asr.py`：调用 Qwen3-ASR-0.6B，可按 chunk 分段避免显存溢出。
- `scripts/score_dy_note.py`：把最终 Markdown 与 `note_budget.json` 比较，判断笔记过短、过长或合适。
- `scripts/setup_qwen_asr_env.py`：创建/更新共享的 Qwen3-ASR Python 环境。
- `scripts/selftest.py`：轻量自测，覆盖 SRT/Qwen 解析、合段和本地输出生成。
- `references/douyin-video-text-notes.md`：实现细节、场景模式、证据分层、已知限制和后续改进建议。
