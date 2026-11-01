# TASK_TRACKER

## 当前状态

- 工作空间已建立：是
- 代码实现已开始：是（基础设施就位，PSL 核心待实现）
- 技术路线已收敛：是（Pair Surprisal Layer，8.6/10）
- 当前关注点：PSL 核心算法实现（WP1-WP2）

## 已确认假设

- 继续沿用现有 `coordination` 服务与 API 入口
- 前端只做与返回结构直接相关的最小适配
- 不引入参考子仓改动
- detect_groups() 引擎完全冻结不修改

## 已完成

- [x] 建立技术线 01 独立 ARIS 工作空间
- [x] 5 轮 research-refine 迭代（5.9 → 8.6/10）
- [x] 基础设施：detect_groups(), flag_speed_share(), network builder, stats
- [x] 20 个实验设计（M0-M4 里程碑）
- [x] 文献综述（14 篇论文）
- [x] 创新性审查（CCF C+ 对比，8.0/10 低-中风险）

## 待办

- [ ] WP1: 多通道 Object 提取（url/hashtag/media/cascade）
- [ ] WP2: PairSurprisalLayer 核心（significance.py）
- [ ] WP3: SemanticPairAdapter（semantic.py）
- [ ] WP4: Cascade 检测（回复链追溯）
- [ ] WP5: API 参数扩展
- [ ] WP6: 前端适配
- [ ] WP7: 端到端测试

## 会话记录

- 2026-04-08：建立技术线 01 独立 ARIS 工作空间
- 2026-04-08~09：5 轮 research-refine，方案收敛至 PSL（8.6/10）
- 2026-04-09：创新性审查（CCF C+ 对比，8.0/10 低-中风险）
- 2026-04-14：Harness 重构，同步实际代码状态
- 2026-05-10：deep-interview 6 轮 Socratic（Contrarian + Simplifier），ambiguity 100% → 18.25%；合并落盘 systemDesign.md 单文件（含错位矩阵 M1–M5、ADR-001 PSL primary + fallback 文字契约、T1–T6 时序原则、M0–M6 里程碑、24 条文献 9 字段综述）
