# CogGuard MediaCrawler 数据契约

> 事件样本：`event_id=trump_visit_2026_05_21`  
> 数据库：MongoDB `cogguard`  
> 集合：`raw_posts`、`raw_comments`  
> 覆盖平台：`weibo`、`xhs`、`douyin`  
> 生成日期：2026-05-21

本文档基于当前 MongoDB 中目标事件的真实入库数据，以及代码中的标准模型与 MediaCrawler 归一化逻辑整理。标准模型定义见 `system/backend/app/models/post.py`，MediaCrawler 字段映射见 `system/backend/app/core/crawler/social.py`。

## 1. 标准数据模型

### 1.1 StandardPost 字段表

| 字段名 | 类型 | 含义 | 来源平台字段 | 是否必填 | 下游用途 |
|---|---|---|---|---|---|
| `platform` | `str` | CogGuard 平台标识 | 采集任务平台参数：`weibo` / `xhs` / `douyin` | 是 | 跨平台筛选、事件对齐、看板统计、协同检测分平台分析 |
| `post_id` | `str` | 平台内帖子/笔记/视频 ID | weibo: `note_id`; xhs: `note_id`; douyin: `aweme_id`; 通用回退：`id` / `video_id` / `content_id` | 是 | 帖子详情、评论关联、去重、传播图节点 |
| `event_id` | `str \| None` | CogGuard 事件 ID | 导入/预处理阶段写入 | 当前事件必填 | 事件级浏览、跨平台事件聚合、风险报告主键 |
| `source_keyword` | `str \| None` | 触发采集的关键词 | MediaCrawler 行内 `source_keyword` 或导入阶段补充 | 建议必填 | 事件溯源、关键词过滤、采集任务解释 |
| `dedupe_key` | `str \| None` | 跨集合稳定去重键 | 预处理生成：`{event_id}:{platform}:post:{post_id}` | 建议必填 | 幂等导入、增量同步、重复数据治理 |
| `content` | `str` | 帖子正文 | weibo: `content`; xhs: `title` + `desc`; douyin: `desc` / `title`; 通用：`content` / `desc` / `title` | 是 | 搜索、语义相似度、立场/危害分析、协同语义边 |
| `author_id` | `str` | 作者平台 ID | `user_id` / `uid` / `author_id` | 是 | 账号画像、协同账号节点、传播角色识别 |
| `author_name` | `str` | 作者昵称 | `nickname` / `author_name` / `user_name` / `user_nickname` | 是 | 前端展示、详情页、人工复核 |
| `timestamp` | `datetime` | 发布时间 | `create_time` / `create_ts` / `time` / `publish_time` / `pub_ts` | 是 | 时间线、时间同步协同边、趋势预测 |
| `url` | `str` | 原帖 URL | weibo: `note_url`; xhs: `note_url`; douyin: `aweme_url`; 通用：`url` / `share_url` | 否 | 跳转原文、证据链、报告引用 |
| `likes` | `int` | 点赞数 | `liked_count` / `digg_count` / `like_count` | 否，默认 0 | 热度排序、传播影响力、风险因子 |
| `reposts` | `int` | 转发/分享数 | `shared_count` / `share_count` / `repost_count` | 否，默认 0 | 传播范围估计、扩散强度、风险因子 |
| `comments_count` | `int` | 评论数 | `comments_count` / `comment_count` / `video_comment` | 否，默认 0 | 热度排序、评论树入口、传播活跃度 |
| `media_urls` | `list[str]` | 图片、视频、封面、音频等媒体链接 | `media_urls` / `image_list` / `images` / `pictures` / `video_url` / `video_download_url` / `note_download_url` / `music_download_url` / `cover_url` / `video_cover_url` / `play_url` | 否，默认空列表 | 帖子详情、共媒体协同边、多模态证据 |
| `hashtags` | `list[str]` | 标签列表 | `hashtags` / `tag_list` / `tags` | 否，默认空列表 | 共标签协同边、话题聚类、事件浏览筛选 |
| `author_profile` | `dict \| None` | 作者画像快照 | `user_id`、`nickname`、`avatar`、`gender`、`profile_url`、`ip_location`、`sec_uid`、`user_signature`、`tag_list` 等 | 建议必填 | 账号画像、详情页作者卡片、自动化倾向评分 |
| `crawl_job_id` | `int \| None` | 采集任务 ID | Celery 采集任务写入 | 建议必填 | 任务追踪、删除任务时清理关联数据 |
| `raw_data` | `dict \| None` | 原始平台记录保真副本 | MediaCrawler JSONL 原行 | 建议必填 | 字段追溯、平台差异补偿、后续重归一化 |
| `created_at` | `datetime` | 标准模型创建时间 | `StandardPost` 默认生成 | 是 | 系统审计、导入时间追踪 |
| `imported_at` | `datetime` | 数据导入时间 | 预处理/导入阶段写入 | 当前事件存在 | 数据治理、批次审计 |

### 1.2 StandardComment 字段表

| 字段名 | 类型 | 含义 | 来源平台字段 | 是否必填 | 下游用途 |
|---|---|---|---|---|---|
| `platform` | `str` | CogGuard 平台标识 | 采集任务平台参数 | 是 | 跨平台筛选、评论统计、传播分析 |
| `comment_id` | `str` | 平台内评论 ID | weibo: `comment_id`; xhs: `comment_id`; douyin: `comment_id`; 通用回退：`cid` / `id` | 是 | 评论详情、评论树节点、去重 |
| `post_id` | `str` | 所属帖子 ID | weibo/xhs: `note_id`; douyin: `aweme_id`; 通用：`video_id` / `post_id` / `content_id` | 是 | 帖子-评论关联、评论树、传播图边 |
| `event_id` | `str \| None` | CogGuard 事件 ID | 导入/预处理阶段写入 | 当前事件必填 | 事件级评论查询、风险证据收束 |
| `source_keyword` | `str \| None` | 触发采集的关键词 | MediaCrawler 行内 `source_keyword` 或导入阶段补充 | 建议必填 | 事件溯源、关键词过滤 |
| `dedupe_key` | `str \| None` | 稳定去重键 | 预处理生成：`{event_id}:{platform}:comment:{comment_id}` | 建议必填 | 幂等导入、重复评论治理 |
| `content` | `str` | 评论正文 | `content` / `text` | 是 | 评论详情、立场检测、危害性评估、语义证据 |
| `author_id` | `str` | 评论作者平台 ID | `user_id` / `uid` / `author_id` | 是 | 账号画像、互动网络、协同参与统计 |
| `author_name` | `str` | 评论作者昵称 | `nickname` / `author_name` / `user_name` / `user_nickname` | 是 | 前端展示、人工复核 |
| `timestamp` | `datetime` | 评论发布时间 | `create_time` / `time` / `publish_time` / `created_at` | 是 | 评论时间线、传播速度、回复链排序 |
| `reply_to` | `str \| None` | 父评论 ID；为空表示一级评论或平台未提供父级 | `parent_comment_id` / `reply_to`，且会过滤空值、`0`、自身 ID | 否 | 评论树展示、显式回复边、传播分析 |
| `likes` | `int` | 评论点赞数 | `comment_like_count` / `like_count` / `liked_count` | 否，默认 0 | 热评排序、观点影响力 |
| `media_urls` | `list[str]` | 评论图片等媒体链接 | `media_urls` / `pictures` / 其他媒体字段 | 否，默认空列表 | 评论详情、多模态证据 |
| `sub_comment_count` | `int` | 子评论数量 | `sub_comment_count` | 否，默认 0 | 评论树加载提示、互动强度 |
| `author_profile` | `dict \| None` | 评论作者画像快照 | 同 StandardPost 的作者画像字段集合 | 建议必填 | 账号画像、详情页作者卡片、可疑账号识别 |
| `crawl_job_id` | `int \| None` | 采集任务 ID | Celery 采集任务写入 | 建议必填 | 任务追踪、数据清理 |
| `raw_data` | `dict \| None` | 原始平台评论记录保真副本 | MediaCrawler JSONL 原行 | 建议必填 | 字段追溯、评论树修复、后续重归一化 |
| `created_at` | `datetime` | 标准模型创建时间 | `StandardComment` 默认生成 | 是 | 系统审计 |
| `imported_at` | `datetime` | 数据导入时间 | 预处理/导入阶段写入 | 当前事件存在 | 数据治理、批次审计 |

## 2. 三平台字段覆盖情况

### 2.1 目标事件总体规模

| 平台 | posts 数量 | comments 数量 | 总记录数 |
|---|---:|---:|---:|
| weibo | 165 | 2,680 | 2,845 |
| xhs | 98 | 1,905 | 2,003 |
| douyin | 31 | 10,137 | 10,168 |
| 合计 | 294 | 14,722 | 15,016 |

### 2.2 覆盖率统计

| 平台 | posts 数量 | comments 数量 | post `media_urls` 覆盖率 | comment `media_urls` 覆盖率 | post `author_profile` 覆盖率 | comment `author_profile` 覆盖率 | comment `reply_to` 非空比例 | post `raw_data` 保留 | comment `raw_data` 保留 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| weibo | 165 | 2,680 | 0.00% | 0.00% | 100.00% | 100.00% | 12.28% | 100.00% | 100.00% |
| xhs | 98 | 1,905 | 100.00% | 1.73% | 100.00% | 100.00% | 6.46% | 100.00% | 100.00% |
| douyin | 31 | 10,137 | 100.00% | 0.00% | 100.00% | 100.00% | 41.19% | 100.00% | 100.00% |

### 2.3 平台字段覆盖观察

#### weibo

- 入库帖子原始字段主要包括：`note_id`、`content`、`create_time`、`create_date_time`、`liked_count`、`comments_count`、`shared_count`、`note_url`、`user_id`、`nickname`、`avatar`、`gender`、`profile_url`、`ip_location`、`post_details_raw`、`source_keyword`。
- 入库评论原始字段主要包括：`comment_id`、`note_id`、`content`、`create_time`、`create_date_time`、`comment_like_count`、`sub_comment_count`、`parent_comment_id`、`user_id`、`nickname`、`avatar`、`gender`、`profile_url`、`ip_location`。
- 当前目标事件中 `media_urls` 覆盖率为 0，原因是微博样本的媒体信息主要隐含在正文或 `post_details_raw`，当前归一化逻辑没有从 `post_details_raw` 深层提取视频/图片链接。
- `reply_to` 非空比例为 12.28%，说明已保留部分二级评论关系，可支撑初版评论树，但不是完整深层递归评论树。

#### xhs

- 入库帖子原始字段主要包括：`note_id`、`type`、`title`、`desc`、`note_url`、`image_list`、`video_url`、`time`、`liked_count`、`comment_count`、`share_count`、`tag_list`、`xsec_token`、`user_id`、`nickname`、`avatar`、`ip_location`。
- 入库评论原始字段主要包括：`comment_id`、`note_id`、`content`、`create_time`、`like_count`、`sub_comment_count`、`parent_comment_id`、`pictures`、`user_id`、`nickname`、`avatar`、`ip_location`。
- 帖子 `media_urls` 覆盖率为 100%，可直接支持帖子详情页媒体预览和共媒体协同边。
- 评论 `media_urls` 覆盖率为 1.73%，说明图片评论少量存在，但不应作为核心分析依赖。
- `tag_list` 已转为 `hashtags`，适合做话题筛选和共标签协同。

#### douyin

- 入库帖子原始字段主要包括：`aweme_id`、`aweme_type`、`title`、`desc`、`aweme_url`、`cover_url`、`video_download_url`、`music_download_url`、`note_download_url`、`create_time`、`liked_count`、`comment_count`、`share_count`、`user_id`、`nickname`、`avatar`、`sec_uid`、`short_user_id`、`user_unique_id`、`user_signature`、`ip_location`。
- 入库评论原始字段主要包括：`comment_id`、`aweme_id`、`content`、`create_time`、`like_count`、`sub_comment_count`、`parent_comment_id`、`pictures`、`user_id`、`nickname`、`avatar`、`sec_uid`、`short_user_id`、`user_unique_id`、`user_signature`、`ip_location`。
- 帖子 `media_urls` 覆盖率为 100%，可支撑视频详情和媒体证据展示。
- `reply_to` 非空比例为 41.19%，评论树展示价值最高。
- 评论 `media_urls` 当前为 0，评论分析应优先依赖文本、作者、时间、父评论关系和互动量。

## 3. 下游系统开发建议

### 3.1 事件数据浏览页

优先建设事件级数据浏览页，作为后续所有分析模块的入口。页面应以 `event_id` 为主过滤条件，展示三平台帖子与评论总量、关键词分布、时间范围、平台分布、媒体覆盖率、作者画像覆盖率和原始数据保真状态。当前目标事件已有 15,016 条记录，足以支撑事件级分页、筛选、排序和统计卡片。

建议首批接口：

- `GET /api/v1/events/{event_id}/summary`
- `GET /api/v1/events/{event_id}/posts`
- `GET /api/v1/events/{event_id}/comments`

### 3.2 帖子详情页

帖子详情页应围绕 `platform + post_id` 查询，展示标准字段、原文链接、正文、媒体预览、作者画像、互动指标、关联评论、`raw_data` 折叠调试区。小红书和抖音媒体覆盖率为 100%，适合作为详情页媒体预览的首批验证平台；微博详情页需允许媒体为空。

建议首批接口：

- `GET /api/v1/events/{event_id}/posts/{platform}/{post_id}`
- `GET /api/v1/events/{event_id}/posts/{platform}/{post_id}/comments`

### 3.3 评论树展示

评论树应使用 `post_id` 关联帖子，使用 `reply_to` 连接父评论。由于 `reply_to` 只在部分评论中非空，前端需要同时支持两种形态：

- `reply_to is null`：一级评论列表。
- `reply_to` 非空：挂到父评论下；找不到父评论时归入“孤立回复/缺失父节点”分组。

抖音目标事件 `reply_to` 非空比例最高（41.19%），适合作为评论树首测平台。微博和小红书仍能展示一级评论和少量二级关系。

### 3.4 跨平台事件对齐

当前事件级统一依赖 `event_id`，平台内实体依赖 `post_id/comment_id`，导入去重依赖 `dedupe_key`。下一步需要补充事件对齐层：

- 以 `event_id` 汇总多平台数据。
- 以 `source_keyword` 解释采集来源。
- 以文本相似度、标签、时间窗口、URL/媒体相似度构建跨平台 claim/thread。
- 为风险与报告模块生成可引用的 `claim_id` / `thread_id`。

### 3.5 账号画像

当前 `author_profile` 在帖子和评论中覆盖率均为 100%，可立即支撑作者卡片和基础账号画像。建议先做轻量画像聚合：

- 按 `platform + author_id` 聚合发帖数、评论数、点赞总量、活跃时间分布、参与关键词。
- 保留平台特有字段：微博 `gender/profile_url/ip_location`，小红书 `tag_list/xsec_token/ip_location`，抖音 `sec_uid/user_unique_id/user_signature/ip_location`。
- 账号详情页需要展示“原始画像字段”折叠区，避免过早丢失平台差异。

### 3.6 协同检测

现有数据已具备协同检测所需的核心字段：`author_id`、`timestamp`、`content`、`hashtags`、`media_urls`、`post_id`、`platform`。建议开发顺序：

1. 先让协同检测 API 支持 `event_id` 过滤，避免全库扫描或只按平台分析。
2. 在当前共享对象协同基础上增加多行为证据边：时间同步、共标签/共链接、共媒体、语义近似、传播互动。
3. 对微博媒体缺失做降级：微博先用文本 URL/话题和时间同步，待深层媒体提取补齐后再加入共媒体边。
4. 输出证据样本时引用 `raw_data` 和原帖 URL，保证可复核。

### 3.7 传播分析

传播分析应以 `event_id` 为主入口，融合帖子时间线与评论树：

- 用 `timestamp` 构建跨平台发布时间线。
- 用 `post_id -> comments` 和 `reply_to` 构建显式互动边。
- 用 `likes/reposts/comments_count/sub_comment_count` 估计扩散强度。
- 用 `source_keyword`、`hashtags`、文本相似度聚合 claim/thread。
- 产出关键角色：起爆节点、桥接节点、扩散节点、评论场高影响节点。

## 4. 与系统功能闭环的对齐

系统文档定义的主线是：

```text
事件 -> 证据 -> 协同 -> 传播 -> 风险 -> 处置
```

PRD 中三大功能闭环为：

1. 协同发现：发现跨平台协同行为，输出协同判定、协同类型、协同群组和证据边。
2. 传播监控：追溯源头、范围和趋势，输出传播图、关键角色、时间线和趋势预测。
3. 报告研判：消费协同与传播结果，输出风险评分、DISARM 映射、报告和处置建议。

当前 `trump_visit_2026_05_21` 的入库数据已经能支撑“事件 -> 证据”的第一段闭环：三平台数据统一挂到同一 `event_id`，帖子/评论均保留标准字段与 `raw_data`。接下来的工程重点应从“采集是否能跑”转到“事件数据如何被浏览、复核、分析和下游消费”。

## 5. 三个关键技术模块的开发指向

### 5.1 Coordination Discover / Detect：跨平台协同检测

文档要求 Coordination Discover / Detect 从行为对集合输出协同判定、类型标签、群组和证据边。路线图显示共享对象 CooRTweet MVP 已完成，但多行为边构建和显著性筛查仍需加强。

结合当前数据，Coordination Discover / Detect 的近期目标应是：

- 让协同检测以 `event_id` 为输入边界。
- 使用 `timestamp`、`author_id`、`content`、`hashtags`、`media_urls`、`reply_to` 构建多行为证据。
- 输出每条协同边的主要证据类型和可复核样本。
- 增加自然共振与人为协同的显著性筛查参数。

### 5.2 Propagation Analysis：传播监控与趋势预测

文档要求 Propagation Analysis 在传播子图和关键角色基础上输出趋势预测，并补齐立场检测、危害性评估等信号供 Risk Review 消费。路线图显示传播子图、时间线、关键角色已完成，WP4-5 立场/危害尚未启动。

结合当前数据，Propagation Analysis 的近期目标应是：

- 以 `event_id` 聚合帖子和评论时间线。
- 优先利用抖音较完整的评论回复关系验证评论树和互动边。
- 将 `likes/reposts/comments_count/sub_comment_count` 转为传播强度特征。
- 产出 claim/thread 级传播摘要，为报告研判提供输入。

### 5.3 Risk Review：报告研判与报告生成

文档要求 Risk Review 消费 Coordination Discover / Detect、Propagation Analysis 与知识库，输出结构化报告、DISARM 映射和处置建议。路线图显示报告研判 MVP 已完成，但 LLM bridge、Agent+RAG 深度分析，以及预警/报告中心/处置跟踪仍待补齐。

结合当前数据，Risk Review 的近期目标应是：

- 先将报告研判输入从“平台筛选”升级为明确的 `event_id`。
- 把协同证据、传播证据、账号画像证据统一为可审计 evidence pack。
- 将风险报告持久化，并提供报告详情与导出入口。
- 在规则证据稳定后，再接入 LLM bridge 做解释增强，而不是作为第一阶段最终裁决。

## 6. 推荐下一阶段开发目标

推荐下一阶段以“事件数据闭环 MVP”为第一开发目标，而不是立即深入单个算法模块：

1. 新增事件数据 API 与事件数据浏览页，确认 `event_id` 作为系统主入口。
2. 新增帖子详情与评论树展示，验证标准字段、媒体、作者画像和 `raw_data` 可复核。
3. 改造协同检测、传播分析、报告研判入口，使三者都支持 `event_id=trump_visit_2026_05_21`。
4. 在该事件上跑通 `事件 -> 证据 -> 协同 -> 传播 -> 风险 -> 报告/处置建议` 的最小闭环。
5. 闭环跑通后，再分模块增强 Coordination Discover / Detect 多行为协同、Propagation Analysis 立场/危害与趋势预测、Risk Review 报告中心和预警处置。

这样做的原因是：当前真实数据已经入库，但现有功能文档和部分 API 仍以平台/全库为主入口。先建立事件级浏览和详情复核能力，可以让后续协同、传播、风险模块拥有同一份可验证输入，减少算法开发阶段的定位成本。
