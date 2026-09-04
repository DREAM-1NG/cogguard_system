# Baseline Methods for Coordination Discover Evaluation

## Task Definition

Coordination Discover evaluates a two-stage task: **coordination discovery -> coordination discrimination**.

- **Coordination discovery** builds a multi-relation coordination graph, enriches it with LM-based object/node/community representations, and uses GNN message passing to discover coordinated account communities, key account pairs, and shared objects. This is the primary task when using X/Twitter IO Archive style positive IO archives.
- **Coordination discrimination** uses labeled IO/control or coordinated/organic data to test whether the discovered graph signals can distinguish coordinated attacks from spontaneous behavior. This is where supervised ranking/classification metrics are reported.

Bot detection, troll identification, and misinformation classification are auxiliary related tasks. Their metrics can be reported as characterization signals, but they are not the primary Coordination Discover objective.

## 1. Primary Baseline: CooRTweet Percentile Method

**Source**: CooRTweet R package (Giglietto et al., 2020)
**Status**: ✅ 已有代码基础 (detector.py 中的 detect_groups)
**Implementation**: 复用现有 `flag_speed_share()` 逻辑

**Method**:
- 检测账号在时间窗口内共享同一 object (URL/hashtag)
- 计算配对账号的共享速度 (time delta)
- 使用 percentile threshold (默认 5%) 标记快速共享

**Metrics**:
- Precision/Recall/F1 (需要标注数据)
- Network density
- Group size distribution

**Effort**: 🟢 Low (1-2 天) — 只需扩展现有代码支持多 object 类型

---

## 2. Secondary Baseline: Single-Channel Ablations

**Purpose**: 验证 C2 (多通道覆盖) 声明
**Status**: ⚠️ 需实现

**Variants**:
1. **Time-only**: 只用时间戳同步 (±5min window)
2. **URL-only**: 只用共享链接
3. **Media-only**: 只用共享媒体哈希
4. **Template-fingerprint-only**: 只用行为型模板/字符级近重复指纹，不使用文本语义理解
5. **Cascade-only**: 只用转发/评论关系

**Comparison Target**: PSL 三通道融合 (Object + Template Fingerprint + Cascade)

**Effort**: 🟡 Medium (3-4 天) — 需要实现 5 个独立检测器

---

## 3. Our Method: LM-enhanced Multi-relation GNN

**Status**: 🚧 需实现；当前 `twitter_io_experiment.py` 中已有 learnable relation attention v0，可作为第一版过渡。

**Method**:
- 构建多关系、动态、有向协同图。
- 使用 LM 做 object canonicalization、node/community embedding、Node Selection 后的 LLM annotation。
- 使用 R-GCN / HAN-like message passing 学习 relation attention、edge score、node embedding 和 community embedding。
- Setting A 做自监督协同社区发现；Setting B 做有标签协同区分。

**Role in evaluation**:
- 这是 Coordination Discover 的主方法，不再只是 optional baseline。
- `learnable_relation_attention_v0` 是主方法的轻量前身。
- CooRTweet、single-channel、static multi-relation、Leiden/static graph 是网络科学/统计基线。

**Effort**: 🔴 High (7-10 天) — 第一版建议先用纯 PyTorch 实现轻量 GNN，避免一开始引入 PyTorch Geometric。

---

## 4. Optional Baseline: Cross-Platform Method (Cinus WWW 2025)

**Source**: "Cross-Platform Coordinated Inauthentic Behavior" (Cinus et al., 2025)
**Status**: ❌ 不适用 (当前只做单平台)

**Reason**: Coordination Discover 范围限定在单平台窗口内检测，跨平台属于未来工作

---

## Implementation Priority

| Method | Priority | Effort | Rationale |
|--------|----------|--------|-----------|
| CooRTweet percentile | **P0** | 🟢 Low | M1 baseline，必须有 |
| Single-channel ablations | **P1** | 🟡 Medium | C2 声明的核心对比 |
| learnable_relation_attention_v0 | **P1** | 🟡 Medium | 从静态融合过渡到学习型融合 |
| LM-enhanced multi-relation GNN | **P0/P1** | 🔴 High | Coordination Discover 主方法 |
| External GNN baselines | **P2** | 🔴 High | CARE-GNN / PC-GNN / HAN / MAGNN / HGT / R-GCN |
| Cinus cross-platform | **P3** | N/A | 超出 Coordination Discover 范围 |

---

## Evaluation Protocol

### Setting A: discovery-only

**Dataset**: X/Twitter Information Operations Archive.

**Goal**: Validate whether the method can construct interpretable coordination graphs and discover account communities from positive IO archives.

**Primary metrics**:
- Network/community: node_count, edge_count, density, component_count, cluster_count, largest_cluster_size, modularity
- Discovery quality: cluster density/conductance, object concentration, relation/channel breakdown
- Evidence quality: top-K edge/account/object audit precision
- Robustness: cluster stability across time-window, language, and campaign/month slices

**Baselines**:
- CooRTweet-style URL sharing
- hashtag_share
- retweet_target
- reply_target
- quote_target / mention_target
- multi_relation_static
- learnable_relation_attention_v0
- Leiden/Louvain on static weighted graph

**Our method**:
- LM-enhanced multi-relation GNN

**Ablations**:
- without LM
- without GNN
- without relation attention
- static-only

### Setting B: labeled detection

**Datasets**: Guo & Vosoughi 2022 state-backed IO dataset; Seckin et al. 2025 labeled IO datasets.

**Goal**: Test whether graph signals discovered in Setting A can distinguish coordinated attacks from organic or self-organized behavior.

**Primary metrics**:
- Ranking: AUPRC, Precision@K, Recall@K
- Threshold selection / classification: MaxF1, AUROC
- Fixed-threshold diagnostics only: F1@0.5; fixed-threshold macro-averaged metrics are not included in paper main tables
- Community alignment: FM-score, NMI, ARI, Purity

**Baselines**:
- All Setting A baselines
- CARE-GNN / PC-GNN / HAN / MAGNN / HGT / R-GCN as auxiliary graph-learning baselines when the data is converted to a labeled graph benchmark

**Our method**:
- LM-enhanced multi-relation GNN

### Auxiliary Metrics

- False discovery control: observed FDP vs target α; hot-topic vs cold-topic comparison
- Coverage: detected edge count; multi-channel vs single-channel edge ratio
- Interpretability: evidence sample audit (Likert 1-5); edge type distribution
- Characterization-only signals: bot score, toxicity, stance, harmfulness, sentiment; these do not feed back into Coordination Discover coordination decisions

---

## Next Steps
1. ✅ 完成此文档
2. ⏭️ 创建 DATA_SOURCES.md (明确数据获取路径)
3. ⏭️ 实现 CooRTweet baseline (M1 milestone)
4. ⏭️ 搜索 Sharma KDD 2021 的公开代码
