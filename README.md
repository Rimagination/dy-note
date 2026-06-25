<p align="center">
  <img src="assets/dy-note-logo-douyin.png" alt="DyNote logo" width="560">
</p>

<p align="center">
  <img alt="Douyin" src="https://img.shields.io/badge/Douyin-video_%2B_comments-FE2C55?style=for-the-badge">
  <img alt="Markdown" src="https://img.shields.io/badge/Markdown-learning_notes-222222?style=for-the-badge&logo=markdown">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-FF6699?style=for-the-badge">
</p>

# DyNote

DyNote 是一个面向短视频研究和知识库的抖音笔记工具：用完整分享文案、页面信息、豆包网页快读、本地自动语音识别、评论样本和证据预算，把抖音视频整理成可学习、可检索、可继续写作的 Markdown 笔记。

它的核心特点是：

- 先快后稳：优先用已登录豆包网页快速理解视频；需要可靠原文、引用或拆解时，再升级到本地自动语音识别、关键帧或评论样本。
- 避免返工：先检查已有 `doubao_brief.md`、`transcript.txt`、`segments.json`、`metadata.json` 和 `note_budget.json`，只补真正缺的证据。
- 证据分级：区分分享文案、页面元数据、豆包检索式概述、本地转写、评论样本、关键帧和外部核查，不把草稿当成事实。
- 动态长度：根据视频时长、文本量、评论量和互动质量控制笔记详略，避免所有短视频都被压成同样长度。

DyNote 的目标不是把视频粗暴压成几句摘要，而是把短视频变成有来源、有证据、可复用、能继续研究和写作的材料。

## 适合什么

- 快速判断一条抖音视频讲了什么，是否值得继续深挖。
- 把视频整理成学习笔记、脚本拆解、选题素材或写作素材。
- 分析评论区的需求、痛点、反对意见、复购信号和转化阻力。
- 分析账号定位、内容栏目、选题模式、钩子模板和系列化打法。
- 研究某个话题、赛道、竞品或本地生活/电商内容套路。
- 对涉及事实判断的视频做来源标注、证据分级和外部核查。

## 输出内容

一次完整分析通常包含两层结果：给人读的主笔记，以及给复核、续写和追问用的原始材料包。主笔记会按证据预算组织学习收获、核心判断、脚本结构、方法步骤、评论洞察和局限；材料包保存豆包概述、转写文本、结构化片段、元数据、评论样本、预算和评分。

<details>
<summary>展开完整输出清单</summary>

常见主笔记包含：

- 视频讲了什么
- 学完你应该获得什么
- 一句话总论
- 核心信息与证据等级
- 脚本结构、镜头节奏或内容套路
- 可复用选题、表达方式和评论洞察
- 适用边界、风险和需要核查的点
- 来源、覆盖范围和局限

常见原始材料包含：

- `analysis_plan.json`：复杂任务的分析计划
- `doubao_brief.md` / `doubao_brief.json`：豆包快速概述和证据等级
- `transcript.cleaned.md`：可阅读的视频文本
- `transcript.txt`：纯文本转写
- `segments.json`：结构化片段
- `metadata.json`：来源、作者、时长和输出清单
- `note_budget.json`：推荐笔记长度和写作粒度
- `learning_note.md`：最终学习笔记
- `note_score.json`：笔记长度和信噪比检查结果

</details>

## 快速使用

### 1. 安装

把下面这句话发给 Agent：

```text
请帮我安装这个 skill：
https://github.com/Rimagination/dy-note
```

### 2. 分析一条抖音视频

在抖音里点击分享，复制完整分享文案，然后把它发给 Agent。完整分享文案通常比单独的视频 URL 更适合快读，因为里面带有标题、话题和短链。

```text
请用 DyNote 分析这条抖音视频，先走豆包快读，不够再转写：
8.28 x@F.uf gbA:/ 07/06 :9pm 铁板牛排+炸土豆饼 向阳而生 # 助眠 # 治愈 # 美食 # 野外烹饪 # 牛排 https://v.douyin.com/xxxxxxx/ 复制此链接，打开Dou音搜索，直接观看视频！
```

如果你更关心学习笔记，可以说：

```text
请用 DyNote 把这条抖音视频整理成学习笔记，保留来源和证据等级。
```

如果你更关心评论区，可以说：

```text
请用 DyNote 分析这条抖音视频和评论区，重点看用户需求、反对意见和可复用选题。
```

账号、话题或竞品分析也可以直接说：

```text
请用 DyNote 分析这个抖音账号的内容定位、栏目结构和选题模式。
```

### 3. 指定保存位置

如果你有固定文件夹，或者想保存到 Obsidian / 知识库里，再加一句保存路径：

```text
帮我存放在：“D:\知识库\短视频分析” 里。
```

### 4. 复用已有结果

如果已经跑过一次，可以让 Agent 先检查哪些文件能复用：

```text
请用 DyNote 先检查已有输出目录，不要重复跑豆包、下载视频或本地自动语音识别。
```

Agent 会按需要运行：

```powershell
python scripts/inspect_workflow_state.py --out-dir ".\dy_note_output" --mode "single-video-note"
```

## 依赖与环境检测

第一次使用、换机器、浏览器路线失败，或准备转写音频前，先让 Agent 检查环境：

```text
请帮我检查 DyNote 的运行环境，并告诉我当前能走豆包快读、中文 Qwen3-ASR、本地文本整理还是 Whisper 兜底。
```

Agent 会运行：

```powershell
python scripts/check_environment.py
```

DyNote 和 Bili Note 会共享可复用资源。默认共享目录是：

```text
%USERPROFILE%\.cache\rimagination-notes
```

其中 Qwen3-ASR 虚拟环境默认放在：

```text
%USERPROFILE%\.cache\rimagination-notes\qwen3-asr-venv
```

因此，只要任意一个 skill 已经引导你安装过 Qwen3-ASR，另一个 skill 会优先复用同一套环境和模型缓存。Hugging Face 模型缓存、Whisper 缓存和 faster-whisper 缓存也按本机通用缓存复用，不会绑定到某一个 skill。

依赖按能力分层理解：

| 层级 | 用来做什么 | 需要什么 | 缺失时怎么办 |
| --- | --- | --- | --- |
| 必需 | 启动 skill、检查已有材料、整理已有文本 | Python 3.10+、已安装本 skill | 先修复 Python 或重新安装 skill |
| 登录浏览器 | 豆包快读、抖音页面加载 | Chrome、`web-access`、当前 Chrome 已登录对应网页 | 未登录时停止，并提示先登录 |
| 中文转写 | 中文视频高可读转写 | `ffmpeg`、共享 Qwen3-ASR 环境 | 运行 `scripts/setup_qwen_asr_env.py`，两个 skill 共用 |
| 外语转写 | 外语视频转写 | `ffmpeg`、Whisper / faster-whisper | 只有外语视频或 Qwen 不适合时再装 |
| 评论与研究 | 评论洞察、账号/话题研究 | 对应抓取能力和网络可用性 | 抓不到时说明覆盖范围 |

默认策略：中文或未指定语言的视频优先 Qwen3-ASR；明确是外语视频时优先 Whisper 系后端。需要手动指定时，可以用 `--asr-backend qwen3-asr` 或 `--asr-backend whisper`。

## 证据等级

DyNote 会区分不同来源的可靠性：

- 用户给的分享文案
- 抖音页面标题、简介和元数据
- 豆包网页的快速解读
- 本地自动语音识别转写
- 评论区样本
- 关键帧或截图
- 外部来源核查

豆包很适合快速理解视频，但如果结果是搜索派生内容，DyNote 不会把它当成“已经逐帧看过视频”。需要可靠原文时，会回落到本地自动语音识别或关键帧检查。

## 登录和隐私

豆包路线需要你已经在当前 Chrome 登录豆包网页版。DyNote 只让浏览器自己加载页面，不会导出或保存 Cookie、localStorage、token、签名参数等登录凭据。

抖音视频链接和临时媒体地址可能包含签名信息。DyNote 会避免把这些敏感临时 URL 写进最终笔记。

## 写笔记的原则

- 先判断用户真正要解决什么问题，再决定是快读、转写、评论洞察、脚本拆解还是事实核查。
- 先保存原始材料，再写总结；最终笔记要能回到原始材料解释来源。
- 长视频、长转写、高评论或高互动视频要写得更结构化；短视频或低信息密度视频不要硬扩成长文。
- 豆包快读适合做草稿、筛选和视觉假设；发布级结论要用本地自动语音识别、关键帧、评论或外部来源补证。
- 评论区只保留有分析价值的内容：需求、反对意见、补充案例、争议点和转化阻力。
- 写学习笔记时优先遵守 `note_budget.json`，用推荐长度和写作粒度控制详略。

## 什么时候会重跑

默认会复用已有产物。只有这些情况才建议重跑：

- 换了视频链接或分享文案
- 分析目标变了
- 旧文件缺失、过期或明显质量不够
- 需要更高证据等级，例如从快读升级到完整转写
- 你明确要求重新跑

需要强制重跑时，在脚本命令里加：

```powershell
--force
```

## 相关文件

- `SKILL.md`：Codex 使用这个 skill 时读取的完整工作流说明。
- `scripts/check_environment.py`：检查 web-access proxy、ffmpeg、Whisper、Qwen3-ASR 和本地模型缓存。
- `scripts/setup_qwen_asr_env.py`：创建或复用共享 Qwen3-ASR 环境，默认位于 `%USERPROFILE%\.cache\rimagination-notes\qwen3-asr-venv`。
- `scripts/compute_note_budget.py`：按转写长度、时长、评论量和互动质量生成 `note_budget.json`。
- `scripts/create_analysis_plan.py`：按场景模式生成 `analysis_plan.json`。
- `scripts/doubao_video_brief.py`：使用当前已登录 Chrome 中的豆包网页版快速解读抖音分享文案。
- `scripts/extract_douyin_text.py`：从抖音链接、本地音频或本地转写文件生成文本素材。
- `scripts/inspect_workflow_state.py`：检查输出目录已有产物，推荐下一步并避免返工。
- `scripts/run_qwen_asr.py`：调用 Qwen3-ASR-0.6B，可按 chunk 分段避免显存溢出。
- `scripts/score_dy_note.py`：把最终 Markdown 与 `note_budget.json` 比较，判断笔记过短、过长或合适。

## 社区友链

- [Bili Note](https://github.com/Rimagination/bili-note)：同系列 B 站视频与图文笔记 skill，DyNote 的笔记预算、原始材料优先和学习型笔记思路都继承自它。
- [LINUX DO](https://linux.do/)：一个关注开发者、开源项目与 AI 工具交流的社区。感谢社区佬友对开源工具和 Agent 工作流的讨论与反馈。

## 致谢

DyNote 的设计和实现参考、依托了这些主要项目与生态：

- [Bili Note](https://github.com/Rimagination/bili-note)：同系列项目，提供了原始材料归档、笔记预算和学习型笔记的核心设计参考。
- [抖音](https://www.douyin.com/)：视频、页面信息、评论和互动数据来源。
- [豆包](https://www.doubao.com/)：可选的网页快读路线，用于快速理解视频内容和生成草稿。
- [Qwen3-ASR](https://huggingface.co/Qwen/Qwen3-ASR-0.6B)：可选中文本地自动语音识别后端。
- [FFmpeg](https://ffmpeg.org/)：可选音频处理和转码。
- [OpenAI Whisper](https://github.com/openai/whisper) 与 [faster-whisper](https://github.com/SYSTRAN/faster-whisper)：可选外语视频转写后端。

## 许可证

本项目使用 MIT License，详见 `LICENSE`。
