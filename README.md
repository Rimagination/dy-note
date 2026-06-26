<p align="center">
  <img src="assets/dy-note-logo-douyin.png" alt="DyNote logo" width="560">
</p>

<p align="center">
  <img alt="Douyin" src="https://img.shields.io/badge/Douyin-video_%2B_comments-FE2C55?style=for-the-badge">
  <img alt="Markdown" src="https://img.shields.io/badge/Markdown-learning_notes-222222?style=for-the-badge&logo=markdown">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-FF6699?style=for-the-badge">
</p>

# DyNote

把抖音视频变成可复用的学习笔记。

DyNote 是一个面向 Codex / Agent 的抖音内容分析 skill。你给它抖音分享文案、视频链接、账号主页、话题关键词或评论分析任务，它会把内容整理成有来源、有证据、可检索、能继续写作和研究的 Markdown 材料。

它适合这些场景：

- 单条视频：总结内容、生成学习笔记、拆脚本、提取可复用选题。
- 评论区：整理用户需求、反对意见、购买顾虑、高频反馈和选题线索。
- 账号与话题：分析定位、栏目结构、钩子模板、内容模式和竞品样本。
- 知识库归档：保存原始材料、证据等级、元数据和后续可追问的笔记。

## 核心特点

- 优先走抖音网页版内置 AI：登录抖音后，DyNote 会优先使用视频页里的 `问AI` / `识别画面`，快速拿到章节要点、时间线和画面上下文。
- 需要可靠原文时再转写：如果你要逐句内容、引用、脚本拆解或事实核查，DyNote 会升级到本地自动语音识别。中文视频优先复用 Qwen3-ASR，外语视频再用 Whisper 系后端。
- 有画面意识：抖音很多视频没有独立字幕。长视频如果转写很少，DyNote 会提醒你补画面理解、关键帧或 OCR，不会把稀疏文本硬写成完整解析。
- 不重复花时间：已有 `douyin_ai_brief.md`、`transcript.txt`、`segments.json`、`metadata.json`、`note_budget.json` 时，会先复用，只补真正缺的证据。
- 继承 Bili Note 的笔记逻辑：先保存原始材料，再根据视频时长、信息密度和互动质量生成适合长度的学习笔记。

## 快速使用

### 1. 安装

把下面这句话发给 Agent：

```text
请帮我安装这个 skill：
https://github.com/Rimagination/dy-note
```

### 2. 分析一条视频

在抖音里点分享，复制完整分享文案，然后发给 Agent：

```text
请用 DyNote 分析这条抖音视频，先走抖音内置 AI，不够再转写：
8.28 x@F.uf gbA:/ 07/06 :9pm 铁板牛排+炸土豆饼 向阳而生 # 助眠 # 治愈 # 美食 # 野外烹饪 # 牛排 https://v.douyin.com/xxxxxxx/ 复制此链接，打开Dou音搜索，直接观看视频！
```

你也可以直接说：

```text
请用 DyNote 把这条抖音视频整理成学习笔记，保留来源和证据等级。
```

### 3. 分析评论、账号或话题

```text
请用 DyNote 分析这条抖音视频和评论区，重点看用户需求、反对意见和可复用选题。
```

```text
请用 DyNote 分析这个抖音账号的内容定位、栏目结构和选题模式。
```

```text
请用 DyNote 围绕“野外烹饪”这个话题做样本分析，先低成本筛选，再挑值得深挖的视频。
```

### 4. 保存到你的知识库

```text
帮我存放在：“D:\知识库\短视频分析” 里。
```

### 5. 复用已有结果

```text
请用 DyNote 先检查已有输出目录，不要重复跑抖音内置 AI、豆包、下载视频或本地自动语音识别。
```

## 默认路线

DyNote 会先判断你真正想要什么，再决定证据深度：

| 你的目标 | 默认路线 | 适合输出 |
| --- | --- | --- |
| 先知道视频讲什么 | 抖音网页版 `问AI` / `章节要点` | 快速摘要、时间线、选题判断 |
| 做学习笔记 | 先拿原始材料，再按 `note_budget.json` 写笔记 | `learning_note.md` |
| 要逐句内容或引用 | 字幕轨优先，没有再本地自动语音识别 | `transcript.cleaned.md`、`transcript.txt` |
| 拆镜头、商品、画面文字 | `识别画面`、关键帧、OCR 或人工检查 | 画面证据、镜头/场景分析 |
| 看用户反馈 | 抓取评论样本并聚类 | 评论洞察、反对意见、需求列表 |
| 做账号或话题研究 | 先采样，再深挖关键视频 | 样本表、模式总结、研究简报 |

备用路线：如果抖音内置 AI 不可用，DyNote 可以用已登录豆包网页版做快读；如果豆包结果是搜索派生内容，会标注为草稿或假设，不会当作逐帧视觉证据。

## 输出内容

一次完整分析通常有两层结果：

- 主笔记：给人读的总结、学习笔记、脚本拆解、评论洞察或研究简报。
- 原始材料包：给复核、续写和追问用的结构化证据。

常见文件：

| 文件 | 用途 |
| --- | --- |
| `douyin_ai_brief.md` / `douyin_ai_brief.json` | 抖音网页版 `问AI` 的章节要点、时间线和证据等级 |
| `doubao_brief.md` / `doubao_brief.json` | 备用豆包快读结果 |
| `transcript.cleaned.md` | 适合阅读的视频文本材料 |
| `transcript.txt` | 适合继续总结、检索或写作的纯文本 |
| `segments.json` | 结构化片段，方便后续查证 |
| `metadata.json` | 来源、作者、时长和输出清单 |
| `note_budget.json` | 推荐笔记长度、写作粒度和画面依赖提示 |
| `learning_note.md` | 最终学习笔记 |
| `note_score.json` | 笔记长度和信噪比检查 |

## 依赖与环境

第一次使用、换机器、浏览器路线失败，或准备转写音频前，让 Agent 检查环境：

```text
请帮我检查 DyNote 的运行环境，并告诉我当前能走抖音内置 AI、备用豆包快读、中文 Qwen3-ASR、本地文本整理还是 Whisper 兜底。
```

Agent 会运行：

```powershell
python scripts/check_environment.py
```

依赖按能力分层：

| 能力 | 需要什么 | 说明 |
| --- | --- | --- |
| 基础整理 | Python 3.10+、已安装本 skill | 整理已有文本、检查输出目录 |
| 抖音内置 AI | Chrome、`web-access`、当前 Chrome 已登录抖音 | 默认快读路线 |
| 豆包备用快读 | Chrome、`web-access`、当前 Chrome 已登录豆包 | 抖音内置 AI 不可用时使用 |
| 中文转写 | `ffmpeg`、共享 Qwen3-ASR 环境 | 中文或未指定语言优先 |
| 外语转写 | `ffmpeg`、Whisper / faster-whisper | 外语视频优先 |
| 评论与研究 | 网络可用、对应抓取能力 | 抓不到时会说明覆盖范围 |

DyNote 和 [Bili Note](https://github.com/Rimagination/bili-note) 会共享可复用资源。默认共享目录：

```text
%USERPROFILE%\.cache\rimagination-notes
```

Qwen3-ASR 虚拟环境默认放在：

```text
%USERPROFILE%\.cache\rimagination-notes\qwen3-asr-venv
```

只要任意一个 skill 已经引导你安装过 Qwen3-ASR，另一个 skill 会优先复用同一套环境和模型缓存。

## 登录和隐私

- 抖音内置 AI 路线需要你已经在当前 Chrome 登录抖音网页版。
- 备用豆包路线需要你已经在当前 Chrome 登录豆包网页版。
- DyNote 只让浏览器自己加载页面，不会导出或保存 Cookie、localStorage、token、签名参数等登录凭据。
- 抖音视频链接和临时媒体地址可能包含签名信息，DyNote 会避免把这些敏感临时 URL 写进最终笔记。

## 写笔记的原则

- 先保存原始材料，再写总结。
- 快读适合草稿、筛选和视觉假设；发布级结论要补转写、关键帧、评论或外部来源。
- 长视频、长转写、高评论或高互动视频要写得更结构化。
- 短视频或低信息密度视频不要硬扩成长文。
- 评论区只保留有分析价值的内容：需求、反对意见、补充案例、争议点和转化阻力。
- 写学习笔记时优先遵守 `note_budget.json`，用推荐长度和写作粒度控制详略。

## 什么时候会重跑

默认会复用已有产物。只有这些情况才建议重跑：

- 换了视频链接或分享文案
- 分析目标变了
- 旧文件缺失、过期或质量不够
- 需要更高证据等级，例如从快读升级到完整转写
- 你明确要求重新跑

需要强制重跑时，在脚本命令里加：

```powershell
--force
```

## 相关文件

- `SKILL.md`：Codex 使用这个 skill 时读取的完整工作流说明。
- `scripts/check_environment.py`：检查 web-access proxy、ffmpeg、Whisper、Qwen3-ASR 和本地模型缓存。
- `scripts/douyin_web_ai_brief.py`：使用当前已登录 Chrome 中的抖音网页版 `问AI / 识别画面` 提取视频章节要点和时间线。
- `scripts/doubao_video_brief.py`：备用路线，使用当前已登录 Chrome 中的豆包网页版快速解读抖音分享文案。
- `scripts/extract_douyin_text.py`：从抖音链接、本地音频或本地转写文件生成文本素材。
- `scripts/compute_note_budget.py`：按转写长度、时长、评论量和互动质量生成 `note_budget.json`。
- `scripts/inspect_workflow_state.py`：检查输出目录已有产物，推荐下一步并避免返工。
- `scripts/setup_qwen_asr_env.py`：创建或复用共享 Qwen3-ASR 环境。
- `scripts/run_qwen_asr.py`：调用 Qwen3-ASR-0.6B，可按 chunk 分段避免显存溢出。
- `scripts/score_dy_note.py`：把最终 Markdown 与 `note_budget.json` 比较，判断笔记过短、过长或合适。
- `references/douyin-video-text-notes.md`：实现细节、场景模式、证据分层、已知限制和后续改进建议。

## 社区友链

- [Bili Note](https://github.com/Rimagination/bili-note)：同系列 B 站视频与图文笔记 skill，DyNote 的笔记预算、原始材料优先和学习型笔记思路都继承自它。
- [LINUX DO](https://linux.do/)：一个关注开发者、开源项目与 AI 工具交流的社区。感谢社区佬友对开源工具和 Agent 工作流的讨论与反馈。

## 致谢

DyNote 的设计和实现参考、依托了这些主要项目与生态：

- [Bili Note](https://github.com/Rimagination/bili-note)：同系列项目，提供了原始材料归档、笔记预算和学习型笔记的核心设计参考。
- [抖音](https://www.douyin.com/)：视频、页面信息、评论和互动数据来源。
- [豆包](https://www.doubao.com/)：备用网页快读路线，用于抖音内置 AI 不可用时生成草稿。
- [Qwen3-ASR](https://huggingface.co/Qwen/Qwen3-ASR-0.6B)：可选中文本地自动语音识别后端。
- [FFmpeg](https://ffmpeg.org/)：可选音频处理和转码。
- [OpenAI Whisper](https://github.com/openai/whisper) 与 [faster-whisper](https://github.com/SYSTRAN/faster-whisper)：可选外语视频转写后端。

## 许可证

本项目使用 MIT License，详见 `LICENSE`。
