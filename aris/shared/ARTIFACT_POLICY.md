# ARTIFACT_POLICY

## 1. 默认入库

以下文件属于稳定文档，允许提交：

- `README.md`
- `RESEARCH_BRIEF.md`
- `EXPERIMENT_PLAN.md`
- `TASK_TRACKER.md`
- `ACCEPTANCE.md`
- 实际代码改动
- 必要的 `README.md` / `development-roadmap.md` / `development-log.md` 同步

## 2. 默认不入库

以下目录仅保留本地或远端：

- `outputs/`
- `logs/`
- `refine-logs/`
- `.cache/`
- `scratch/`

另外也不提交：

- 模型权重
- 数据集副本
- 中间缓存
- 真实 GPU/SSH 配置
- API Key、Cookie、token

## 3. 如何保留实验结论

如果某轮 ARIS 运行有稳定结论，不提交原始日志，改为：

1. 把结论摘要写入 `TASK_TRACKER.md`
2. 把确认后的实现路径写入 `EXPERIMENT_PLAN.md`
3. 如果仓库状态或路线发生变化，再同步 `doc/engineering/development-roadmap.md` 与 `doc/engineering/development-log.md`
