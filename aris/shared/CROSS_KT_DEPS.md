# Cross-KT Dependency Map

> Architecture Map — 记录三个技术线的数据流依赖和共享接口。
> 修改任何 KT 的输出结构前，必须检查下游是否受影响。

## 数据流总览（2026-04-22 重新定位后）

```
┌─────────────────────┐
│  KT1 协同发现        │
│  多任务检测          │
│  (二分类+类型分类)    │
└──────────┬──────────┘
           │ 输出: {协同群组, 协同类型, 证据边}
           ▼
┌─────────────────────┐
│  KT2 传播监控        │
│  LLM+时序预测        │
│  (趋势/画像/立场)    │
└──────────┬──────────┘
           │ 输出: {趋势预测, 用户画像, 立场, 危害性}
           ▼
┌─────────────────────────────────────────────┐
│  KT3 报告研判                                │
│  Agent + RAG                                 │
│  消费 KT1+KT2 全部结果 → 攻击分析报告        │
└─────────────────────────────────────────────┘
```

## KT1 → KT2 接口

**KT1 输出**:
```python
coordination_result = {
    "coordinated_groups": list[dict],       # 协同群组
    "coordination_type": str,               # 协同类型（astroturfing/brigading/...）
    "is_coordinated": bool,                 # 二分类结果
    "confidence": float,                    # 分类置信度
    "evidence_edges": list[dict],           # 证据边（含类型和权重）
    "coordinated_accounts": int,            # 协同账号数
    "coordination_density": float,          # 协同密度
}
```

## KT2 → KT3 接口

**KT2 输出**:
```python
monitoring_result = {
    "trend_prediction": {                   # 趋势预测（关键技术）
        "predicted_volume": list[float],    # 未来 N 小时预测传播量
        "predicted_scope": float,           # 预测传播范围
        "trend_direction": str,             # rising/stable/declining
    },
    "user_profiles": list[dict],            # 用户画像
    "stance_distribution": dict,            # 立场分布
    "harmfulness_score": float,             # 危害性评分
    "source_tracing": dict,                 # 源头追溯结果
    "scope_estimation": dict,               # 范围估计
}
```

## KT3 消费模式

**KT3 Agent 输入**: KT1 + KT2 全部结构化输出，通过 RAG 检索增强
```python
agent_input = {
    "coordination_result": coordination_result,  # from KT1
    "monitoring_result": monitoring_result,       # from KT2
    "rag_context": {                              # RAG 检索结果
        "disarm_techniques": list[dict],          # DISARM 知识库
        "historical_cases": list[dict],           # 历史案例
        "external_evidence": list[dict],          # 外部证据
    }
}
```

**KT3 输出**: 攻击分析报告
```python
risk_report = {
    "attack_analysis": str,                 # 攻击分析（自然语言）
    "disarm_mapping": list[dict],           # DISARM 战术/技术映射
    "recommendations": list[str],           # 处置建议
    "risk_level": str,                      # 风险等级
    "structured_report": dict,              # 结构化报告 JSON
}
```

## 变更协议

修改任何 KT 的输出接口前：
1. 检查此文件确认下游消费者
2. 在 PLAYBOOK.md 的 Harness Window 中标记为跨 KT 变更
3. 触发人工介入（预定义触发器）
4. 同步更新下游消费接口

## KT1 → KT3 接口

**KT1 输出** (coordination_service.py):
```python
coordination_result = {
    "coordinated_accounts": int,        # 协同账号数
    "coordination_density": float,      # 协同密度
    "edge_symmetry_mean": float,        # 边对称性均值
    "coordinated_account_ratio": float, # 协同账号占比
    "max_component_size": int,          # 最大连通分量
    "groups": list[dict],               # 协同群组列表
}
```

**KT3 消费** (evidence_builder.py):
- `coordination_density` → manipulation mass 计算
- `edge_symmetry_mean` → manipulation mass 计算
- `coordinated_account_ratio` → manipulation mass 计算 + phase 特征

**变更影响**: 如果 KT1 修改输出字段名或类型，KT3 evidence_builder 需同步更新。

## KT2 → KT3 接口

**KT2 输出** (propagation_service.py):
```python
propagation_result = {
    "evidence_chains": list[dict],      # 证据链列表
    "key_paths": list[dict],            # 关键路径
    "bridge_ratio": float,              # 桥接比例
    "burstiness": float,                # 突发性 (CV of inter-event times)
    "cross_cluster_spread": int,        # 跨集群传播数
    "originator_concentration": float,  # 源头集中度 (Gini)
}
```

**KT3 消费** (evidence_builder.py):
- `bridge_ratio` → impact mass 计算 + phase 特征
- `burstiness` → impact mass 计算 + phase 分类核心指标
- `cross_cluster_spread` → impact mass 计算 + phase 特征

**变更影响**: 如果 KT2 修改 burstiness 计算方式，KT3 phase_detector 的阈值需重新校准。

## Accounts → KT3 接口

**accounts 输出** (account_service.py):
```python
account_data = {
    "high_automation_ratio": float,     # 高自动化账号占比
    "automation_entropy": float,        # 自动化分数 Shannon 熵
    "regularity_mean": float,           # 行为规律性均值
}
```

**KT3 消费** (evidence_builder.py):
- `high_automation_ratio` → authenticity mass 计算 + phase 特征
- `automation_entropy` → authenticity mass 计算 + regeneration 检测
- `regularity_mean` → authenticity mass 计算

## 共享标识符

| 标识符 | 类型 | 来源 | 消费者 |
|--------|------|------|--------|
| `event_id` | string | 数据采集层 | KT1, KT2, KT3 |
| `claim_id` | string | KT2 propagation | KT3 report |
| `account_id` | string | accounts 服务 | KT1, KT2, KT3 |
| `platform` | string | 数据采集层 | 全部 |

## 变更协议

修改任何 KT 的输出接口前：
1. 检查此文件确认下游消费者
2. 在 PLAYBOOK.md 的 Harness Window 中标记为跨 KT 变更
3. 触发人工介入（预定义触发器）
4. 同步更新下游 evidence_builder.py 的字段映射
