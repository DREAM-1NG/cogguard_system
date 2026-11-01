# RUNNERS

本文件只说明“如何在本仓使用 ARIS 工作空间”，不复制上游 skill 实现。外部 skill 安装请按上游文档执行：

- 上游 README：<https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep>
- Codex/Claude 兼容说明：<https://raw.githubusercontent.com/wanshuiyin/Auto-claude-code-research-in-sleep/main/docs/CODEX_CLAUDE_REVIEW_GUIDE.md>

## 1. 通用前置步骤

1. 从 `release-0.2` 起目标技术分支
2. 进入目标 `aris/tech-*` 工作空间
3. 阅读 `README.md`、`RESEARCH_BRIEF.md`、`ACCEPTANCE.md`
4. 确认允许修改路径与禁止修改路径

## 2. Claude Code 路径

适用场景：

- 已按上游 README 安装外部 ARIS skills
- 需要直接使用 `/research-refine`、`/experiment-plan`、`/auto-review-loop`

推荐步骤：

1. 进入目标技术目录，例如 `aris/tech-01-coordination/`
2. 启动 Claude Code
3. 第一轮先基于本目录文档收敛计划，不直接跳进编码
4. 使用本地 `RESEARCH_BRIEF.md` 作为唯一 brief 来源
5. 产出的稳定计划和结论回写到 `EXPERIMENT_PLAN.md` 与 `TASK_TRACKER.md`

建议原则：

- `AUTO_PROCEED: false`
- `human checkpoint: true`
- `code review: true`

## 3. Codex 路径

适用场景：

- 你希望保留本仓 `AGENTS.md` / `aris/` 文档约束
- 可选安装上游 `skills-codex`，也可以只按本地文档手动执行等价流程

推荐步骤：

1. 在仓库根或目标技术目录启动 Codex
2. 先阅读根 `AGENTS.md` 与目标 `aris/tech-*` 文档
3. 把 `RESEARCH_BRIEF.md` 和 `ACCEPTANCE.md` 作为首轮上下文
4. 实现后，把稳定结论回写到 `TASK_TRACKER.md`

注意：

- Codex 路径同样不在仓库根创建单一 `RESEARCH_BRIEF.md`
- 如果 runner 需要仓库根 cwd，就在根目录启动，但第一条输入必须显式指定目标 `aris/tech-*` 工作空间

## 4. 远端 GPU

只有在技术线确实需要句向量、中文编码器或批量实验时才切远端 GPU。使用前先复制并填写 `GPU_SETUP_TEMPLATE.md`，但不要把真实凭据提交到仓库。
