# Data Sources for Coordination Discover Evaluation

## 1. Real-World Data Collection

### 1.1 MediaCrawler (Social Media)

**Status**: ✅ 已集成到 `new-system/backend`
**Implementation**: [social.py](../../../new-system/backend/app/core/crawler/social.py)
**Supported Platforms**: 微博、抖音、小红书、快手、B站、贴吧、知乎

**Current Capabilities**:
- ✅ 关键词搜索 (search mode)
- ✅ 帖子内容提取 (content + metadata)
- ✅ 评论批量采集 (comments via JSONL)
- ✅ 时间戳、URL、转发数、点赞数
- ⚠️ 媒体 URL 提取 (部分平台支持)
- ❌ 转发关系图 (cascade structure) — **需要扩展**

**Configuration Required**:
```bash
# .env
MEDIACRAWLER_LOGIN_TYPE=cookie
MEDIACRAWLER_COOKIES=<platform_cookies>
```

**Known Issues**:
1. **转发关系缺失** — 当前只采集 `shared_count`，无法构建 cascade 通道
2. **媒体哈希缺失** — 需要下载图片/视频并计算 perceptual hash
3. **Cookie 过期** — 需要定期更新登录凭证

**Repair Plan**:
- [ ] 扩展 `weibo_content_line_to_post()` 提取转发链 (repost_id, root_id)
- [ ] 添加媒体下载 + pHash 计算模块
- [ ] 实现 cookie 自动刷新机制

---

### 1.2 NewsCrawler (News Articles)

**Status**: ✅ 已集成到 `new-system/backend`
**Implementation**: [news.py](../../../new-system/backend/app/core/crawler/news.py)
**Supported Platforms**: 通用新闻站点 (via news_extractor_core)

**Current Capabilities**:
- ✅ URL 模式提取 (单篇文章)
- ✅ 标题、正文、发布时间、作者
- ✅ 图片 URL 提取
- ❌ 评论区采集 — **不支持**
- ❌ 关键词搜索 — **需要上游支持**

**Use Case for Coordination Discover**:
- 新闻评论区的协同行为检测 (需要扩展评论采集)
- 跨站点内容复制检测 (URL/语义通道)

**Repair Plan**:
- [ ] 评估是否需要新闻评论区数据 (优先级低)
- [ ] 如需要，扩展 news_extractor_core 支持评论 API

---

## 2. Public Datasets

### 2.1 Bot Detection Benchmarks

| Dataset | Year | Platform | Size | Labels | Coordination? | Status |
|---------|------|----------|------|--------|---------------|--------|
| **Twibot-22** | 2022 | Twitter | 1M users | Bot/Human | ❌ | 🔍 待搜索 |
| **Twibot-20** | 2020 | Twitter | 229K users | Bot/Human | ❌ | 🔍 待搜索 |
| **Cresci-2017** | 2017 | Twitter | 37K users | Bot/Human | ⚠️ 部分 | 🔍 待搜索 |
| **TweepFake** | 2020 | Twitter | 25K users | Bot/Human | ❌ | 🔍 待搜索 |
| **Botwiki** | 2019 | Twitter | 2.5K bots | Bot only | ❌ | 🔍 待搜索 |

**Limitation**: 这些数据集主要用于 bot 检测，不一定包含协同行为标注。需要检查是否有 coordinated campaigns 子集。

---

### 2.2 Coordinated Behavior Datasets

| Dataset | Source Paper | Platform | Coordination Type | Status |
|---------|--------------|----------|-------------------|--------|
| **CatchSync Dataset** | Jiang KDD 2014 | Sina Weibo | Synchronous posting | 🔍 待搜索 |
| **Sharma KDD 2021 Data** | Sharma et al. | Twitter | Coordinated campaigns | 🔍 待搜索 |
| **Tardelli PNAS 2024 Data** | Tardelli et al. | Twitter | Temporal archetypes | 🔍 待搜索 |
| **Cinus WWW 2025 Data** | Cinus et al. | Multi-platform | Cross-platform CIB | 🔍 待搜索 |

**Action Items**:
- [ ] 搜索论文附录/GitHub 仓库是否提供数据下载链接
- [ ] 联系作者请求数据访问 (如果公开不可用)
- [ ] 检查数据使用协议 (学术 vs 商业)

---

### 2.3 Synthetic Data (MockCrawler)

**Status**: ✅ 已实现
**Implementation**: [mock.py](../../../new-system/backend/app/core/crawler/mock.py)
**Use Case**: M0 (Sanity) 里程碑的管线测试

**Current Capabilities**:
- ✅ 生成已知协同群体 (configurable group size)
- ✅ 时间窗口内共享 URL/hashtag
- ✅ 可控噪声注入 (random posts)

**Limitations**:
- ❌ 无语义相似度模拟 (所有帖子内容随机)
- ❌ 无转发关系图 (cascade structure)
- ❌ 无热门话题模拟 (无法测试 FDR 压力)

**Enhancement Plan**:
- [ ] 添加语义模板生成 (基于 LLM 生成相似文本)
- [ ] 添加转发树生成 (随机 DAG)
- [ ] 添加热门话题模式 (高频 object + 大量自然共振)

---

## 3. Data Collection Plan

### Phase 1: Repair & Validate (Week 1)

**Goal**: 确保 MediaCrawler 能采集完整数据

**Tasks**:
1. ✅ 检查 MediaCrawler 集成状态 (已完成)
2. ⏭️ 配置微博 cookies 并测试采集
3. ⏭️ 扩展 social.py 提取转发关系
4. ⏭️ 实现媒体下载 + pHash 计算
5. ⏭️ 运行 M0 (Sanity) 测试验证数据管线

**Deliverable**: 能够采集包含 5 类 object 的微博数据

---

### Phase 2: Real Data Collection (Week 2)

**Goal**: 采集 1-2 周真实微博数据

**Sampling Strategy**:
- **热门话题** (3-5 个): 选择微博热搜榜 Top 10 话题，采集 500-1000 条帖子/话题
- **冷门话题** (2-3 个): 选择低热度话题 (< 1000 讨论)，采集 200-500 条帖子/话题
- **时间跨度**: 连续 7-14 天，每天采集 2-3 次

**Expected Output**:
- 5K-10K 帖子
- 20K-50K 评论
- 覆盖多种行为模式 (自然讨论、营销号、疑似协同)

---

### Phase 3: Public Dataset Search (Week 1-2, parallel)

**Goal**: 获取至少 1 个带标注的协同行为数据集

**Priority**:
1. **P0**: CatchSync / Sharma KDD 2021 数据 (直接相关)
2. **P1**: Cresci-2017 coordinated subset (如果存在)
3. **P2**: Twibot-22 (用于 bot vs human 对比)

**Search Channels**:
- 论文 GitHub 仓库
- 作者个人主页 / Google Scholar
- Zenodo / Figshare / OSF
- 邮件联系作者

---

## 4. Data Requirements Summary

### For M1 (Baseline)
- ✅ MockCrawler 合成数据 (已有)
- ⏭️ 真实微博数据 (1K+ 帖子，无需标注)

### For M2 (Main Method)
- ⏭️ 真实微博数据 (5K+ 帖子，无需标注)
- ⏭️ 至少 1 个公开数据集 (用于对比)

### For M3 (Decision)
- ⏭️ 热门话题数据 (用于 C3 FDR 压力测试)
- ⏭️ 多样化话题 (用于 C2 多通道覆盖验证)

### For M4 (Polish)
- ⏭️ 标注数据 (100-200 个账号对，用于 C4 证据诊断性人工审计)
- ⏭️ 失败案例集 (用于 B5 失败分析)

---

## 5. Next Steps

**Immediate Actions** (本周):
1. ⏭️ 配置 MediaCrawler 微博 cookies
2. ⏭️ 测试采集 1 个热门话题 (验证数据完整性)
3. ⏭️ 搜索 CatchSync / Sharma 数据集下载链接
4. ⏭️ 扩展 social.py 支持转发关系提取

**Blocked Items**:
- 媒体哈希计算 (需要 imagehash 库 + 下载逻辑)
- 语义编码器选择 (需要先完成文献补查，确定 baseline)
- 标注数据生成 (需要先运行 PSL，再人工审计输出)
