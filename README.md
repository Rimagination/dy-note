<p align="center">
  <img src="assets/dy-note-logo-douyin.png" alt="DyNote logo" width="560">
</p>

<p align="center">
  <img alt="Douyin" src="https://img.shields.io/badge/Douyin-video_%2B_comments-FE2C55?style=for-the-badge">
  <img alt="Markdown" src="https://img.shields.io/badge/Markdown-learning_notes-222222?style=for-the-badge&logo=markdown">
  <img alt="Codex Skill" src="https://img.shields.io/badge/Codex-Skill-00A1D6?style=for-the-badge">
</p>

# DyNote

把抖音视频变成可复用的学习笔记。

DyNote 是一个 Codex Skill。你给它抖音链接、分享文案、账号、话题或评论区任务，它会尽量复用已有材料，按需要调用豆包网页、本地自动语音识别（ASR）、评论抓取和笔记预算，把短视频内容整理成更可靠、更好读的 Markdown。

## 适合做什么

- 总结一条抖音视频讲了什么
- 把视频转成学习笔记、脚本拆解或写作素材
- 分析评论区的需求、痛点和反对意见
- 分析账号定位、内容栏目和选题模式
- 研究某个话题、赛道或竞品的视频套路
- 分析带货、探店、本地生活视频的卖点和转化点
- 对视频中的关键事实做来源标注和核查

## 它怎么工作

DyNote 默认不是一上来就重跑所有步骤，而是先看已经有什么，再补真正缺的证据。

典型流程：

1. 检查已有输出，避免重复跑豆包、下载视频或 ASR。
2. 需要复杂分析时，先生成一份分析计划。
3. 保存原始材料，例如转写文本、片段 JSON、元数据、评论和豆包概述。
4. 根据视频长度、文本量、评论量和互动质量计算笔记预算。
5. 生成学习笔记、研究简报、脚本拆解或评论洞察。
6. 写完后可检查笔记是否过短、过长或缺证据。

## 快速使用

在 Codex 里直接说：

```text
用 $dy-note 分析这个抖音视频，先走豆包快读，不够再转写。
```

或者：

```text
用 $dy-note 把这个抖音链接整理成学习笔记。
```

如果你已经有输出目录，可以先检查哪些东西能复用：

```powershell
$skill = "$env:USERPROFILE\.codex\skills\dy-note"
$py = "python"

& $py "$skill\scripts\inspect_workflow_state.py" `
  --out-dir ".\dy_note_output" `
  --mode "single-video-note"
```

## 常见输出

- `analysis_plan.json`：复杂任务的分析计划
- `doubao_brief.md`：豆包快速概述
- `transcript.cleaned.md`：可阅读的视频文本
- `transcript.txt`：纯文本转写
- `segments.json`：结构化片段
- `metadata.json`：来源、作者、时长和输出清单
- `note_budget.json`：推荐笔记长度和写作粒度
- `learning_note.md`：最终学习笔记
- `note_score.json`：笔记长度和信噪比检查结果

## 证据等级

DyNote 会区分不同来源的可靠性：

- 用户给的分享文案
- 抖音页面标题、简介和元数据
- 豆包网页的快速解读
- 本地 ASR 转写
- 评论区样本
- 关键帧或截图
- 外部来源核查

豆包很适合快速理解视频，但如果结果是搜索派生内容，DyNote 不会把它当成“已经逐帧看过视频”。需要可靠原文时，会回落到本地 ASR 或关键帧检查。

## 登录和隐私

豆包路线需要你已经在当前 Chrome 登录豆包网页版。DyNote 只让浏览器自己加载页面，不会导出或保存 Cookie、localStorage、token、签名参数等登录凭据。

抖音视频链接和临时媒体地址可能包含签名信息。DyNote 会避免把这些敏感临时 URL 写进最终笔记。

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

## 一句话

DyNote 的目标不是“把视频粗暴转成一段摘要”，而是把抖音内容变成有来源、有证据、可复用、能继续写作和研究的笔记材料。
