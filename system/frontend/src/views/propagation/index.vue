<!--
  传播监测页面
-->
<template>
  <div class="propagation-page">
    <PageHeader title="传播监测">
      <template #description>
        展示传播路径、共享对象、角色分析、证据链与传播时间线。
      </template>
    </PageHeader>

    <div class="action-bar">
      <a-space wrap>
        <a-input v-model:value="eventId" size="small" placeholder="事件 ID" style="width: 220px" allow-clear />
        <a-input v-model:value="platform" size="small" placeholder="平台，可选" style="width: 140px" allow-clear />
        <a-date-picker
          v-model:value="observedUntil"
          size="small"
          show-time
          value-format="YYYY-MM-DDTHH:mm:ss"
          placeholder="观测截止时间"
          style="width: 208px"
          allow-clear
        />
        <a-select v-model:value="observationRatio" size="small" style="width: 136px">
          <a-select-option :value="0.1">观测阶段：10%</a-select-option>
          <a-select-option :value="0.3">观测阶段：30%</a-select-option>
          <a-select-option :value="0.5">观测阶段：50%</a-select-option>
        </a-select>
        <a-button type="primary" @click="handleAnalyze" :loading="analyzing">
          同步数据库传播结果
        </a-button>
        <a-button @click="handlePredict" :loading="predicting" :disabled="!eventId.trim()">
          刷新趋势预测
        </a-button>
      </a-space>
      <span v-if="lastSyncedAt" class="sync-hint">最近同步：{{ lastSyncedAt }}</span>
    </div>

    <a-tabs v-model:activeKey="activeTab" class="propagation-tabs">
      <a-tab-pane key="path" tab="传播路径">
        <a-row :gutter="16" style="margin-bottom: 16px">
          <a-col :xs="24" :xl="16">
            <a-card size="small" title="传播路径" :loading="analyzing && !analysisReady" class="analysis-card path-card">
              <div v-if="diffusionReady" class="path-visual-layout">
                <div class="path-node-control">
                  <span class="path-node-control-label">显示节点</span>
                  <a-slider
                    v-model:value="diffusionPendingNodeLimit"
                    class="path-node-slider"
                    :min="diffusionSliderMin"
                    :max="diffusionSliderMax"
                    :step="diffusionSliderStep"
                    :tooltipOpen="false"
                    @change="handleDiffusionLimitChange"
                    @afterChange="handleDiffusionLimitCommit"
                  />
                  <span class="path-node-control-count">
                    {{ diffusionVisibleCount }} / {{ diffusionTotalNodes }}
                  </span>
                  <a-button size="small" type="link" @click="showFullDiffusionGraph">全量</a-button>
                </div>
                <div class="path-graph-shell">
                  <div ref="pathGraphRef" class="path-graph" />
                </div>
              </div>
              <a-empty v-if="!diffusionReady" description="暂无可展示的分层传播路径" :image-style="{ height: '36px' }" />
            </a-card>
          </a-col>

          <a-col :xs="24" :xl="8">
            <a-card size="small" title="层级分析" :loading="analyzing && !analysisReady" class="analysis-card layer-card">
              <div v-if="displayLayerRows.length" class="layer-visual">
                <div v-for="item in displayLayerRows" :key="item.level" class="layer-row">
                  <span class="layer-name">{{ item.label }}</span>
                  <strong>{{ formatRatio(item.ratio) }}</strong>
                  <div class="layer-track">
                    <div class="layer-bar" :style="{ width: `${ratioPercent(item.ratio)}%` }" />
                  </div>
                </div>
              </div>
              <div ref="layerChartRef" class="layer-chart" />
              <a-empty v-if="!displayLayerRows.length" description="暂无层级分布" :image-style="{ height: '36px' }" />
            </a-card>
          </a-col>
        </a-row>
      </a-tab-pane>

      <a-tab-pane key="objects" tab="传播对象">
        <a-card size="small" style="margin-bottom: 16px" :loading="analyzing && !analysisReady">
          <template #title>高频共享对象</template>
          <div v-if="activeClaimGroup" class="claim-object-layout">
            <section class="primary-hashtag-panel">
              <div class="claim-group-title">
                <span>高频共享对象 · {{ activeClaimGroup.label }}</span>
                <a-space :size="4">
                  <a-tag>{{ activeClaimGroup.items.length }} 条</a-tag>
                  <a-dropdown v-model:open="claimGroupMenuOpen" :trigger="['click']">
                    <a-button size="small" type="text" aria-label="切换共享对象类别">...</a-button>
                    <template #overlay>
                      <a-menu @click="handleClaimGroupMenuClick">
                        <a-menu-item v-for="group in claimGroups" :key="group.type">
                          {{ group.label }} · {{ group.items.length }}
                        </a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </a-space>
              </div>
              <div class="hashtag-cloud">
                <button
                  v-for="item in visibleClaimGroupItems(activeClaimGroup)"
                  :key="item.object_id"
                  type="button"
                  class="hashtag-pill"
                  @click="openClaimDetail(item)"
                >
                  <span>{{ item.display }}</span>
                  <small>{{ item.share_count }} 次</small>
                </button>
              </div>
              <a-button
                v-if="activeClaimGroup.items.length > CLAIM_GROUP_COLLAPSED_LIMIT"
                type="link"
                size="small"
                class="claim-more-button"
                @click="showMoreClaimGroup(activeClaimGroup.type)"
              >
                {{ isClaimGroupExpanded(activeClaimGroup.type) ? '收起' : '... 查看全部' }}
              </a-button>
            </section>
          </div>
          <a-empty v-else description="数据库中暂无可展示的高频共享对象" :image-style="{ height: '40px' }" />
        </a-card>
      </a-tab-pane>

      <a-tab-pane key="evidence" tab="角色分析">
        <a-row :gutter="16" style="margin-bottom: 16px">
          <a-col :xs="24" :lg="12">
            <a-card size="small" title="起爆节点" :loading="analyzing && !analysisReady">
              <a-list v-if="keyRoles?.originators?.length" :dataSource="keyRoles.originators" size="small">
                <template #renderItem="{ item }">
                  <a-list-item>
                    <a-button type="link" class="role-link-button" @click="locateUserOnPath(item.account_id)">{{ item.author_name || item.account_id }}</a-button>
                    <template #actions><a-tag color="red">出度 {{ item.out_degree }}</a-tag></template>
                  </a-list-item>
                </template>
              </a-list>
              <a-empty v-else description="暂无起爆节点结果" :image-style="{ height: '30px' }" />
            </a-card>
          </a-col>
          <a-col :xs="24" :lg="12">
            <a-card size="small" title="扩散节点" :loading="analyzing && !analysisReady">
              <a-list v-if="keyRoles?.amplifiers?.length" :dataSource="keyRoles.amplifiers" size="small">
                <template #renderItem="{ item }">
                  <a-list-item>
                    <a-button type="link" class="role-link-button" @click="locateUserOnPath(item.account_id)">{{ item.author_name || item.account_id }}</a-button>
                    <template #actions><a-tag color="blue">入度 {{ item.in_degree }}</a-tag></template>
                  </a-list-item>
                </template>
              </a-list>
              <a-empty v-else description="暂无扩散节点结果" :image-style="{ height: '30px' }" />
            </a-card>
          </a-col>
        </a-row>

        <a-card size="small" title="关键证据链摘要" style="margin-bottom: 16px" :loading="analyzing && !analysisReady">
          <a-list v-if="evidenceChains.length" :dataSource="evidenceChains.slice(0, 5)" item-layout="vertical">
            <template #renderItem="{ item }">
              <a-list-item>
                <div class="chain-header">
                  <a-space wrap>
                    <a-tag color="purple">{{ item.claim_id }}</a-tag>
                    <a-tag>{{ item.share_count }} 次传播</a-tag>
                    <a-tag color="red">源头 {{ item.originator.author_name || item.originator.account_id }}</a-tag>
                    <a-tag color="gold">关键路径 {{ item.key_paths.length }} 条</a-tag>
                  </a-space>
                </div>
                <div class="chain-body">
                  <div>首条路径：{{ item.key_paths[0]?.explanation || '暂无关键路径说明' }}</div>
                  <div>支撑帖子：{{ item.supporting_posts.length }} 条，首发时间 {{ formatTimestamp(item.originator.first_ts) }}</div>
                </div>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else description="暂无关键证据链摘要" :image-style="{ height: '40px' }" />
        </a-card>
      </a-tab-pane>

      <a-tab-pane key="timeline" tab="时间线">
        <a-card size="small" title="传播时间线" style="margin-bottom: 16px" :loading="analyzing && !analysisReady">
          <div v-if="timeline.length > 0" class="timeline-wrap">
            <a-timeline mode="left">
              <a-timeline-item
                v-for="(item, index) in timeline.slice(0, 50)"
                :key="`${item.post_id}-${index}`"
                :color="item.author_id.includes('coord') ? 'red' : 'blue'"
              >
                <p :class="['timeline-head', { 'timeline-entry-focused': timelineFocusPostId === item.post_id }]">
                  <a-button type="link" class="timeline-user-link" @click="locateEvidenceReference(item)">{{ item.author_name || item.author_id }}</a-button>
                  <span class="timeline-time">{{ formatTimestamp(item.timestamp) }}</span>
                </p>
                <p class="timeline-content">{{ item.content }}</p>
              </a-timeline-item>
            </a-timeline>
          </div>
          <a-empty v-else description="数据库中暂无可展示的传播时间线" :image-style="{ height: '40px' }" />
        </a-card>
      </a-tab-pane>

      <a-tab-pane key="model" tab="趋势预测">
        <a-card size="small" title="真实传播趋势" class="evidence-timeline-card" :loading="evidenceTimelineLoading">
          <template #extra>
            <a-space :size="4" wrap>
              <a-button
                v-for="item in timelineRangeOptions"
                :key="item.value"
                size="small"
                :type="timelineRange === item.value ? 'primary' : 'default'"
                @click="selectTimelineRange(item.value)"
              >
                {{ item.label }}
              </a-button>
            </a-space>
          </template>
          <div v-if="evidenceTimelineReady" class="evidence-timeline-meta">
            <span>{{ evidenceTimelineResolutionLabel }}</span>
            <span>{{ formatTimelineWindow(evidenceTimeline?.window) }}</span>
          </div>
          <div v-if="evidenceTimelineReady" ref="evidenceTimelineChartRef" class="evidence-timeline-chart" />
          <a-empty v-else description="暂无可展示的时间证据" :image-style="{ height: '40px' }" />
        </a-card>
        <a-spin :spinning="predicting">
        <template v-if="modelPredictionReady">
          <a-row :gutter="12" style="margin-bottom: 16px">
            <a-col v-for="item in modelForecastCards" :key="item.key" :xs="24" :sm="8">
              <a-card size="small" class="forecast-card">
                <div class="forecast-label">{{ item.label }}</div>
                <div class="forecast-value">{{ item.value }}</div>
                <div class="forecast-interval">{{ item.extra }}</div>
              </a-card>
            </a-col>
          </a-row>
            <a-card size="small" title="传播趋势预测" style="margin-bottom: 16px">
            <a-descriptions size="small" :column="2" bordered>
              <a-descriptions-item label="趋势方向">{{ modelDirectionLabel }}</a-descriptions-item>
              <a-descriptions-item label="观测截止">{{ formatTimestamp(modelPrediction?.data_scope?.observed_until as string || observedUntil) }}</a-descriptions-item>
              <a-descriptions-item label="实际观测比例">{{ formatRatio(modelPrediction?.data_scope?.actual_observation_ratio ?? modelPrediction?.data_scope?.observation_ratio) }}</a-descriptions-item>
              <a-descriptions-item label="模型条件比例">{{ formatRatio(modelPrediction?.data_scope?.checkpoint_conditioning_ratio ?? observationRatio) }}</a-descriptions-item>
              <a-descriptions-item label="模型名称">{{ modelPrediction?.model?.name || 'Ours' }}</a-descriptions-item>
              <a-descriptions-item label="参考数据">{{ modelPrediction?.model?.dataset || 'twitter' }}</a-descriptions-item>
              <a-descriptions-item label="模型范围">{{ modelScopeLabel(modelPrediction?.model?.scope) }}</a-descriptions-item>
              <a-descriptions-item label="预测更新时间">{{ formatTimestamp(modelPrediction?.cache?.generated_at) }}</a-descriptions-item>
            </a-descriptions>
              <div ref="modelTrendChartRef" class="model-trend-chart" />
            </a-card>
          <a-card size="small" title="下一跳预测 Top-K" style="margin-bottom: 16px">
            <a-table
              :columns="nextHopColumns"
              :data-source="modelPrediction?.micro?.top_users || []"
              :pagination="false"
              size="small"
              rowKey="author_id"
              :customRow="nextHopRowProps"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'author'">
                  <a-button type="link" class="table-link-button" @click.stop="openNextHopTrace(record as NextHopUser)">
                    {{ (record as NextHopUser).author_name || (record as NextHopUser).author_id || '--' }}
                  </a-button>
                </template>
                <template v-else-if="column.key === 'source'">
                  <a-tag color="blue">{{ candidateSourceLabel((record as NextHopUser).candidate_source) }}</a-tag>
                </template>
                <template v-else-if="column.key === 'assessment'">
                  <a-tag :color="nextHopAssessmentColor(record as NextHopUser)">{{ nextHopAssessmentLabel(record as NextHopUser) }}</a-tag>
                </template>
                <template v-else-if="column.key === 'evidence'">
                  <a-button size="small" type="link" @click.stop="openNextHopTrace(record as NextHopUser)">
                    {{ (record as NextHopUser).evidence_refs?.length || 0 }} 条
                  </a-button>
                </template>
                <template v-else-if="column.key === 'last_seen'">
                  {{ formatTimestamp((record as NextHopUser).last_seen_at) }}
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-space>
                    <a-button size="small" type="link" @click.stop="openNextHopTrace(record as NextHopUser)">查看依据</a-button>
                    <a-button size="small" type="link" @click.stop="locateNextHopOnPath(record as NextHopUser)">回到路径</a-button>
                  </a-space>
                </template>
              </template>
            </a-table>
          </a-card>
        </template>
        <a-empty v-else :description="predictionEmptyDescription" :image-style="{ height: '48px' }" />
        </a-spin>
      </a-tab-pane>
    </a-tabs>

    <a-drawer v-model:open="claimDetailOpen" width="640" title="共享对象关联数据" placement="right">
      <template v-if="selectedClaim">
        <a-descriptions size="small" :column="1" bordered style="margin-bottom: 16px">
          <a-descriptions-item label="共享对象">{{ selectedClaim.object_id }}</a-descriptions-item>
          <a-descriptions-item label="对象类型">{{ claimTypeLabel(selectedClaim.type) }}</a-descriptions-item>
          <a-descriptions-item label="分享次数">{{ selectedClaim.share_count }}</a-descriptions-item>
          <a-descriptions-item label="涉及账户">{{ selectedClaim.account_count }}</a-descriptions-item>
        </a-descriptions>
        <a-button size="small" type="link" @click="focusObjectOnPath(selectedClaim.object_id)">在传播路径中查看关联关系</a-button>
        <div class="section-title">匹配时间线</div>
        <a-list v-if="claimTimelineMatches.length" :dataSource="claimTimelineMatches" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <div>
                <a-button type="link" class="timeline-user-link" @click="locateEvidenceReference(item)">{{ item.author_name || item.author_id }}</a-button>
                <span class="timeline-time">{{ formatTimestamp(item.timestamp) }}</span>
                <p class="timeline-content">{{ item.content }}</p>
              </div>
            </a-list-item>
          </template>
        </a-list>
        <a-empty v-else description="当前时间线样本中暂无匹配记录" :image-style="{ height: '36px' }" />
        <div class="section-title drawer-section">传播路径</div>
        <a-list v-if="claimEvidenceMatches.length" :dataSource="claimEvidenceMatches" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <div>
                <a-tag color="purple">{{ item.claim_id }}</a-tag>
                <span>源头：{{ item.originator.author_name || item.originator.account_id }}</span>
                <div class="claim-path-list">
                  <button
                    v-for="(path, index) in item.key_paths"
                    :key="`${item.claim_id}-${index}`"
                    class="claim-path-link"
                    type="button"
                    @click="openClaimPathDetail(item, path, index)"
                  >
                    {{ path.explanation || `传播路径 ${index + 1}` }}
                  </button>
                </div>
              </div>
            </a-list-item>
          </template>
        </a-list>
        <a-empty v-else description="暂无传播路径" :image-style="{ height: '36px' }" />
      </template>
    </a-drawer>

    <a-drawer v-model:open="claimPathDetailOpen" width="620" title="传播路径详情" placement="right">
      <template v-if="selectedClaimPathDetail">
        <a-descriptions size="small" :column="1" bordered style="margin-bottom: 16px">
          <a-descriptions-item label="共享对象">{{ selectedClaimPathDetail.chain.claim_id }}</a-descriptions-item>
          <a-descriptions-item label="源头账户">
            {{ selectedClaimPathDetail.chain.originator.author_name || selectedClaimPathDetail.chain.originator.account_id }}
          </a-descriptions-item>
          <a-descriptions-item label="路径说明">
            {{ selectedClaimPathDetail.path.explanation || '暂无路径说明' }}
          </a-descriptions-item>
          <a-descriptions-item v-if="selectedClaimPathDetail.path.nodes?.length" label="节点序列">
            {{ formatNodePath(selectedClaimPathDetail.path.nodes) }}
          </a-descriptions-item>
        </a-descriptions>

        <div class="section-title">支撑帖子</div>
        <a-list v-if="selectedClaimPathDetail.chain.supporting_posts?.length" :dataSource="selectedClaimPathDetail.chain.supporting_posts" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <div>
                <strong>{{ item.author_id }}</strong>
                <span class="timeline-time">{{ formatTimestamp(item.timestamp) }}</span>
                <p class="timeline-content">{{ item.content }}</p>
              </div>
            </a-list-item>
          </template>
        </a-list>
        <a-empty v-else description="暂无支撑帖子" :image-style="{ height: '36px' }" />

        <div class="section-title drawer-section">语义叠加</div>
        <a-descriptions v-if="semanticPathOverlay" size="small" :column="1" bordered>
          <a-descriptions-item label="情绪">{{ formatSemanticDistribution(semanticPathOverlay.sentiment) }}</a-descriptions-item>
          <a-descriptions-item label="关键词">{{ formatSemanticTerms(semanticPathOverlay.keywords, 'term') }}</a-descriptions-item>
          <a-descriptions-item label="主题">{{ formatSemanticTerms(semanticPathOverlay.topics, 'label') }}</a-descriptions-item>
          <a-descriptions-item label="实体">{{ formatSemanticTerms(semanticPathOverlay.entities, 'text') }}</a-descriptions-item>
          <a-descriptions-item label="立场">{{ formatSemanticDistribution(semanticPathOverlay.stance) }}</a-descriptions-item>
          <a-descriptions-item label="平台范围">{{ semanticPathOverlay.platforms.join('、') }}</a-descriptions-item>
          <a-descriptions-item label="时间范围">{{ formatSemanticTimeRange(semanticPathOverlay.time_range) }}</a-descriptions-item>
          <a-descriptions-item label="证据引用">{{ semanticPathOverlay.evidence_refs.join('、') }}</a-descriptions-item>
        </a-descriptions>
        <a-empty v-else description="暂无语义叠加" :image-style="{ height: '36px' }" />
      </template>
    </a-drawer>

    <a-drawer v-model:open="nodeDetailOpen" width="680" title="传播节点详情" placement="right">
      <template v-if="selectedNodeDetail">
        <a-descriptions size="small" :column="1" bordered style="margin-bottom: 16px">
          <a-descriptions-item label="真实用户名">{{ selectedNodeDetail.author_name || selectedNodeDetail.id }}</a-descriptions-item>
          <a-descriptions-item label="用户 ID">{{ selectedNodeDetail.id }}</a-descriptions-item>
          <a-descriptions-item label="发帖数量">{{ selectedNodeDetail.post_count ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="上下游关系">
            入度 {{ selectedNodeDetail.in_degree ?? 0 }} / 出度 {{ selectedNodeDetail.out_degree ?? 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="首次出现">{{ formatTimestamp(selectedNodeDetail.first_ts) }}</a-descriptions-item>
        </a-descriptions>

        <div class="section-title">下游扩散节点</div>
        <a-space v-if="selectedNodeDetail.downstream?.length" wrap style="margin-bottom: 16px">
          <a-tag v-for="item in selectedNodeDetail.downstream" :key="item.id" color="blue">
            {{ item.author_name || item.id }}
          </a-tag>
        </a-space>
        <a-empty v-else description="暂无下游节点" :image-style="{ height: '32px' }" />

        <div class="section-title drawer-section">关联帖子</div>
        <a-list v-if="selectedNodeDetail.posts?.length" :dataSource="selectedNodeDetail.posts" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <div>
                <strong>{{ item.author_name || item.author_id }}</strong>
                <span class="timeline-time">{{ formatTimestamp(item.timestamp) }}</span>
                <p class="timeline-content">{{ item.content }}</p>
                <a v-if="item.url" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.url }}</a>
              </div>
            </a-list-item>
          </template>
        </a-list>
        <a-empty v-else description="暂无关联帖子" :image-style="{ height: '32px' }" />

        <div class="section-title drawer-section">关键路径证据</div>
        <a-list v-if="selectedNodeDetail.key_paths?.length" :dataSource="selectedNodeDetail.key_paths" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <div>
                <a-tag color="purple">{{ item.claim_id }}</a-tag>
                <span>score {{ item.score }}</span>
                <p class="timeline-content">{{ item.explanation || formatNodePath(item.nodes) }}</p>
              </div>
            </a-list-item>
          </template>
        </a-list>
        <a-empty v-else description="暂无关键路径证据" :image-style="{ height: '32px' }" />
      </template>
    </a-drawer>

    <a-drawer v-model:open="nextHopDetailOpen" width="680" title="下一跳研判详情" placement="right">
      <template v-if="selectedNextHopUser">
        <a-descriptions size="small" :column="1" bordered style="margin-bottom: 16px">
          <a-descriptions-item label="用户名">{{ selectedNextHopUser.author_name || selectedNextHopUser.author_id }}</a-descriptions-item>
          <a-descriptions-item label="用户 ID">{{ selectedNextHopUser.author_id }}</a-descriptions-item>
          <a-descriptions-item label="研判类型">{{ nextHopAssessmentLabel(selectedNextHopUser) }}</a-descriptions-item>
          <a-descriptions-item label="候选分数">{{ formatScore(selectedNextHopUser.score) }}</a-descriptions-item>
          <a-descriptions-item label="候选来源">{{ candidateSourceLabel(selectedNextHopUser.candidate_source) }}</a-descriptions-item>
          <a-descriptions-item label="当前事件出现次数">{{ selectedNextHopUser.event_count ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="最近出现">{{ formatTimestamp(selectedNextHopUser.last_seen_at) }}</a-descriptions-item>
        </a-descriptions>

        <a-space style="margin-bottom: 16px">
          <a-button type="primary" size="small" @click="locateNextHopOnPath(selectedNextHopUser)">回到传播路径</a-button>
          <a-button size="small" @click="openNodeDetail(selectedNextHopUser.author_id)">查看节点详情</a-button>
        </a-space>

        <div class="section-title">关联记录</div>
        <a-list v-if="selectedNextHopUser.evidence_refs?.length" :dataSource="selectedNextHopUser.evidence_refs" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <div>
                <a-space wrap>
                  <a-tag>{{ candidateSourceLabel(item.candidate_source) }}</a-tag>
                  <span class="timeline-time">{{ formatTimestamp(item.timestamp) }}</span>
                </a-space>
                <a-button type="link" class="evidence-reference-link" @click="locateEvidenceReference(item)">{{ item.post_id || '关联记录' }}</a-button>
                <p class="timeline-content">{{ item.content || '暂无文本摘要' }}</p>
                <a v-if="item.url" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.url }}</a>
              </div>
            </a-list-item>
          </template>
        </a-list>
        <a-empty v-else description="暂无关联记录" :image-style="{ height: '32px' }" />
      </template>
    </a-drawer>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import {
  analyzeObservedPropagation,
  getCachedPropagationPrediction,
  getPropagationEventTimeline,
  predictPropagationCurrentEvent,
  type PropagationEventTimelineProjection,
  type PropagationTimelineRange,
} from '@/api/propagation'
import { getAnalysisArtifact, getEventSemantic, type SemanticEvidenceProjection } from '@/api/analysis'
import PageHeader from '@/components/PageHeader.vue'

const DEFAULT_EVENT_ID = 'trump_visit_2026_05_21'
const PROPAGATION_ANALYSIS_ARTIFACT_KEY = 'stage:propagation_analysis:result'

type KeyRoleItem = {
  account_id: string
  author_name?: string
  out_degree?: number
  in_degree?: number
  betweenness?: number
}

type EvidencePath = {
  explanation?: string
  nodes?: string[]
  score?: number
  confidence?: number | string
  path_id?: string | number
  evidence_refs?: unknown[]
  metadata?: Record<string, unknown>
}

type SemanticPathOverlay = {
  path_id: string | number
  semantic_overlay: {
    sentiment: Record<string, number>
    keywords: Array<{ term: string; count?: number }>
    topics: Array<{ label: string; count?: number }>
    entities: Array<{ text: string; count?: number }>
    stance: Record<string, number>
    platforms: string[]
    time_range: { start: string; end: string }
    evidence_refs: unknown[]
  }
}

type SemanticOverlayPayload = Omit<SemanticPathOverlay['semantic_overlay'], 'evidence_refs'> & {
  evidence_refs: string[]
}

type SupportingPost = {
  post_id: string
  author_id: string
  timestamp: string
  content: string
}

type EvidenceChain = {
  claim_id: string
  share_count: number
  originator: {
    account_id: string
    author_name?: string
    first_ts?: string
  }
  key_paths: EvidencePath[]
  supporting_posts: SupportingPost[]
}

type ClaimItem = {
  object_id: string
  share_count: number
  account_count: number
  first_share: string
}

type ClaimGroupItem = ClaimItem & {
  type: string
  display: string
  href?: string
}

type TimelineItem = {
  post_id: string
  author_id: string
  author_name: string
  timestamp: string
  content: string
}

type LayerRow = {
  level: number
  label: string
  node_count: number
  ratio: number
}

type KeyPathRow = {
  claim_id?: string
  nodes: string[]
  score: number
  confidence?: string
  path_length: number
  explanation?: string
}

type PathAnalysis = {
  node_count: number
  edge_count: number
  max_depth: number
  first_layer_ratio?: number
  layer_distribution: LayerRow[]
  key_paths: KeyPathRow[]
}

type GraphNode = {
  id: string
  author_name?: string
  post_count?: number
}

type GraphEdge = {
  source: string
  target: string
  weight?: number
  type?: string
  edge_id?: string
  evidence_type?: string
  relation_type?: string
  object_id?: string
  post_id?: string
  source_post_id?: string
  target_post_id?: string
  is_synthetic?: boolean
}

type DiffusionNode = {
  id: string
  author_name?: string
  layer: number
  post_count?: number
  first_ts?: string
  out_degree?: number
  in_degree?: number
  is_root?: boolean
  is_key?: boolean
  layout_x?: number
  layout_y?: number
  layout_cluster?: string
  layout_radius?: number
  similarity_to_root?: number
  shared_object_ids?: string[]
}

type DiffusionEdge = {
  source: string
  target: string
  weight?: number
  type?: string
  edge_id?: string
  evidence_type?: string
  relation_type?: string
  object_id?: string
  post_id?: string
  source_post_id?: string
  target_post_id?: string
  is_key_path?: boolean
  is_parallel_root?: boolean
  is_synthetic?: boolean
}

type DiffusionDetailNeighbor = {
  id: string
  author_name?: string
}

type DiffusionDetailPost = {
  post_id?: string
  author_id?: string
  author_name?: string
  timestamp?: string
  content?: string
  url?: string
}

type DiffusionNodeDetail = {
  id: string
  author_name?: string
  post_count?: number
  first_ts?: string
  out_degree?: number
  in_degree?: number
  upstream?: DiffusionDetailNeighbor[]
  downstream?: DiffusionDetailNeighbor[]
  posts?: DiffusionDetailPost[]
  comments?: DiffusionDetailPost[]
  key_paths?: Array<{
    claim_id?: string
    nodes?: string[]
    score?: number
    explanation?: string
  }>
}

type DiffusionSummary = {
  root_node?: DiffusionNode | null
  parallel_roots?: DiffusionNode[]
  visible_nodes?: DiffusionNode[]
  tree_edges?: DiffusionEdge[]
  highlight_edges?: DiffusionEdge[]
  layout_relations?: DiffusionEdge[]
  layers?: LayerRow[]
  detail_index?: {
    nodes?: Record<string, DiffusionNodeDetail>
    objects?: Record<string, unknown>
  }
  meta?: Record<string, unknown>
}

type AnalysisResult = {
  graph?: {
    nodes?: GraphNode[]
    edges?: GraphEdge[]
    node_count?: number
    edge_count?: number
  }
  key_roles?: {
    originators?: KeyRoleItem[]
    bridges?: KeyRoleItem[]
    amplifiers?: KeyRoleItem[]
  }
  claims?: ClaimItem[]
  timeline?: TimelineItem[]
  evidence_chains?: EvidenceChain[]
  path_analysis?: PathAnalysis
  diffusion_summary?: DiffusionSummary
  error?: string
}

type PropagationAnalysisArtifact = AnalysisResult & {
  status?: string
  fallback?: boolean
  snapshot_id?: string
  data_fingerprint?: string
  artifact_manifest?: Record<string, unknown>
}

type ModelTrendPoint = {
  step: number | string
  predicted_size: number
  at?: string
  timestamp?: string
}

type CumulativeTimelinePoint = {
  at?: string
  cumulative_size: number
}

type ModelTrendInterval = {
  step?: number | string
  timestamp?: string
  lower?: number
  upper?: number
  lower_bound?: number
  upper_bound?: number
  min?: number
  max?: number
}

type NextHopEvidenceRef = {
  post_id?: string
  author_id?: string
  author_name?: string
  timestamp?: string
  content?: string
  url?: string
  candidate_source?: string
}

type NextHopUser = {
  rank: number
  author_id: string
  author_name?: string
  score?: number
  candidate_source?: string
  event_count?: number
  first_seen_at?: string
  last_seen_at?: string
  source_counts?: Record<string, number>
  evidence_refs?: NextHopEvidenceRef[]
  trace_available?: boolean
  assessment_type?: string
  activation_type?: string
  identity_resolution?: string
  score_semantics?: string
  bucket_collision_size?: number
}

type PredictionCoverage = {
  mapped_candidate_buckets?: number
  unmapped_candidate_buckets?: number
  legal_candidate_buckets?: number
  mapped_probability_mass?: number
  new_activation_status?: string
  identity_mapping_status?: string
  ambiguous_mapped_buckets?: number
  excluded_ambiguous_users?: number
  unique_identity_probability_mass?: number
}

type PredictionDataScope = {
  event_id?: string
  platform?: string
  observed_until?: string
  observation_ratio?: number
  actual_observation_ratio?: number
  checkpoint_conditioning_ratio?: number
  trajectory_time_basis?: string
  observed_post_count?: number
  observed_comment_count?: number
  loaded_event_count?: number
  model_input_event_count?: number
  model_observed_event_count?: number
  prefix_selection?: string
}

type EventModelPrediction = {
  status?: string
  model_status?: string
  note?: string
  macro?: {
    observed_size?: number
    predicted_size?: number
    trend_points?: ModelTrendPoint[]
    intervals?: ModelTrendInterval[]
    observed_points?: CumulativeTimelinePoint[]
    realized_points?: CumulativeTimelinePoint[]
    direction?: string
    score_concentration?: number
    calibration_status?: 'available' | 'unavailable'
  }
  micro?: {
    top_users?: NextHopUser[]
    rollout_steps?: number
    candidate_count?: number
    candidate_bucket_count?: number
    coverage?: PredictionCoverage
  }
  model?: {
    name?: string
    dataset?: string
    checkpoint?: string
    methodology?: string
    scope?: string
  }
  event_id?: string
  platform?: string
  data_scope?: PredictionDataScope
  cache?: {
    hit?: boolean
    stale?: boolean
    snapshot_fingerprint?: string
    generated_at?: string
  }
}

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function optionalText(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

function firstFiniteNumber(...values: unknown[]) {
  for (const value of values) {
    const number = Number(value)
    if (value !== null && value !== undefined && value !== '' && Number.isFinite(number)) {
      return number
    }
  }
  return undefined
}

function asObjectArray(value: unknown): UnknownRecord[] {
  if (Array.isArray(value)) {
    return value.filter(isRecord)
  }
  if (isRecord(value)) {
    return Object.values(value).filter(isRecord)
  }
  return []
}

function unwrapPredictionPayload(value: unknown): UnknownRecord | null {
  let current: unknown = value
  for (let depth = 0; depth < 3; depth += 1) {
    if (!isRecord(current)) return null
    if (isRecord(current.data) && !current.macro && !current.micro) {
      current = current.data
      continue
    }
    if (isRecord(current.result) && !current.macro && !current.micro) {
      current = current.result
      continue
    }
    if (isRecord(current.prediction) && !current.macro && !current.micro) {
      current = current.prediction
      continue
    }
    return current
  }
  return isRecord(current) ? current : null
}

function normalizeTrendPoints(value: unknown): ModelTrendPoint[] {
  if (isRecord(value) && Array.isArray(value.points)) {
    return normalizeTrendPoints(value.points)
  }
  return asObjectArray(value).flatMap((item, index) => {
    const predictedSize = firstFiniteNumber(
      item.predicted_size,
      item.predicted,
      item.prediction,
      item.size,
      item.value,
      item.y,
    )
    if (predictedSize === undefined) return []
    return [{
      step: (item.step ?? item.index ?? index + 1) as number | string,
      predicted_size: predictedSize,
      at: typeof item.at === 'string' ? item.at : typeof item.time === 'string' ? item.time : undefined,
      timestamp: typeof item.timestamp === 'string' ? item.timestamp : typeof item.date === 'string' ? item.date : undefined,
    }]
  })
}

function normalizeCumulativeTimelinePoints(value: unknown): CumulativeTimelinePoint[] {
  return asObjectArray(value).flatMap((item) => {
    const at = typeof item.at === 'string'
      ? item.at
      : typeof item.timestamp === 'string'
        ? item.timestamp
        : typeof item.time === 'string'
          ? item.time
          : undefined
    const cumulativeSize = firstFiniteNumber(item.cumulative_size, item.observed_size, item.realized_size, item.predicted_size)
    return at && cumulativeSize !== undefined ? [{ at, cumulative_size: cumulativeSize }] : []
  })
}

function normalizeIntervals(value: unknown): ModelTrendInterval[] {
  if (isRecord(value) && Array.isArray(value.points)) {
    return normalizeIntervals(value.points)
  }
  return asObjectArray(value).flatMap((item, index) => {
    const lower = firstFiniteNumber(item.lower, item.lower_bound, item.min)
    const upper = firstFiniteNumber(item.upper, item.upper_bound, item.max)
    if (lower === undefined && upper === undefined) return []
    return [{
      step: (item.step ?? item.index ?? index + 1) as number | string,
      timestamp: typeof item.timestamp === 'string' ? item.timestamp : typeof item.at === 'string' ? item.at : undefined,
      lower,
      upper,
      lower_bound: lower,
      upper_bound: upper,
    }]
  })
}

function normalizePredictionResponse(value: unknown): EventModelPrediction | null {
  const raw = unwrapPredictionPayload(value)
  if (!raw) return null

  const rawMacro = isRecord(raw.macro)
    ? raw.macro
    : isRecord(raw.forecast) ? raw.forecast : raw
  const rawTrend = rawMacro.trend_points ?? rawMacro.trend ?? rawMacro.points
  const rawObserved = rawMacro.observed_points ?? rawMacro.observed_trend ?? raw.observed_points
  const rawRealized = rawMacro.realized_points ?? rawMacro.realized_trend ?? raw.realized_points
  const trendPoints = normalizeTrendPoints(rawTrend)
  const observedPoints = normalizeCumulativeTimelinePoints(rawObserved)
  const realizedPoints = normalizeCumulativeTimelinePoints(rawRealized)
  const rawMicro = isRecord(raw.micro)
    ? raw.micro
    : isRecord(raw.next_hop) ? raw.next_hop : {}
  const rawUsers = rawMicro.top_users ?? rawMicro.topUsers ?? rawMicro.users ?? rawMicro.top_k
  const topUsers = asObjectArray(rawUsers).flatMap((item, index) => {
    const authorId = String(item.author_id ?? item.user_id ?? item.id ?? '').trim()
    if (!authorId) return []
    return [{
      rank: Number(item.rank ?? index + 1),
      author_id: authorId,
      author_name: String(item.author_name ?? item.username ?? item.name ?? authorId),
      score: firstFiniteNumber(item.score, item.probability, item.value),
      candidate_source: typeof item.candidate_source === 'string' ? item.candidate_source : undefined,
      event_count: firstFiniteNumber(item.event_count, item.count),
      first_seen_at: typeof item.first_seen_at === 'string' ? item.first_seen_at : undefined,
      last_seen_at: typeof item.last_seen_at === 'string' ? item.last_seen_at : undefined,
      source_counts: isRecord(item.source_counts) ? item.source_counts as Record<string, number> : undefined,
      evidence_refs: Array.isArray(item.evidence_refs) ? item.evidence_refs as NextHopEvidenceRef[] : [],
      trace_available: item.trace_available !== false,
      assessment_type: typeof item.assessment_type === 'string' ? item.assessment_type : undefined,
      activation_type: typeof item.activation_type === 'string' ? item.activation_type : undefined,
      identity_resolution: typeof item.identity_resolution === 'string' ? item.identity_resolution : undefined,
      score_semantics: typeof item.score_semantics === 'string' ? item.score_semantics : undefined,
      bucket_collision_size: firstFiniteNumber(item.bucket_collision_size),
    }]
  })

  const rawModel = isRecord(raw.model) ? raw.model : {}
  const rawScope = isRecord(raw.data_scope) ? raw.data_scope : {}
  const rawCache = isRecord(raw.cache) ? raw.cache : {}
  const rawCoverage = isRecord(rawMicro.coverage) ? rawMicro.coverage : {}
  const lastTrendPoint = trendPoints.length ? trendPoints[trendPoints.length - 1] : undefined
  const macro: EventModelPrediction['macro'] = {
    observed_size: firstFiniteNumber(rawMacro.observed_size, rawMacro.observed, rawScope.observed_size),
    predicted_size: firstFiniteNumber(rawMacro.predicted_size, rawMacro.final_size, rawMacro.predicted, lastTrendPoint?.predicted_size),
    trend_points: trendPoints,
    intervals: normalizeIntervals(rawMacro.intervals ?? rawMacro.interval ?? rawMacro.prediction_interval),
    observed_points: observedPoints,
    realized_points: realizedPoints,
    direction: typeof rawMacro.direction === 'string' ? rawMacro.direction : undefined,
    score_concentration: firstFiniteNumber(rawMacro.score_concentration, rawMacro.confidence_like_score),
    calibration_status: rawMacro.calibration_status === 'available' ? 'available' : 'unavailable',
  }

  return {
    status: typeof raw.status === 'string' ? raw.status : undefined,
    model_status: typeof raw.model_status === 'string' ? raw.model_status : undefined,
    macro,
    micro: {
      top_users: topUsers,
      rollout_steps: firstFiniteNumber(rawMicro.rollout_steps, rawMicro.steps),
      candidate_count: firstFiniteNumber(rawMicro.candidate_count, rawMicro.candidates),
      candidate_bucket_count: firstFiniteNumber(rawMicro.candidate_bucket_count),
      coverage: {
        mapped_candidate_buckets: firstFiniteNumber(rawCoverage.mapped_candidate_buckets),
        unmapped_candidate_buckets: firstFiniteNumber(rawCoverage.unmapped_candidate_buckets),
        legal_candidate_buckets: firstFiniteNumber(rawCoverage.legal_candidate_buckets),
        mapped_probability_mass: firstFiniteNumber(rawCoverage.mapped_probability_mass),
        new_activation_status: typeof rawCoverage.new_activation_status === 'string' ? rawCoverage.new_activation_status : undefined,
        identity_mapping_status: typeof rawCoverage.identity_mapping_status === 'string' ? rawCoverage.identity_mapping_status : undefined,
        ambiguous_mapped_buckets: firstFiniteNumber(rawCoverage.ambiguous_mapped_buckets),
        excluded_ambiguous_users: firstFiniteNumber(rawCoverage.excluded_ambiguous_users),
        unique_identity_probability_mass: firstFiniteNumber(rawCoverage.unique_identity_probability_mass),
      },
    },
    model: {
      name: typeof rawModel.name === 'string' ? rawModel.name : typeof raw.model_name === 'string' ? raw.model_name : undefined,
      dataset: typeof rawModel.dataset === 'string' ? rawModel.dataset : typeof raw.dataset === 'string' ? raw.dataset : undefined,
      checkpoint: typeof rawModel.checkpoint === 'string' ? rawModel.checkpoint : undefined,
      methodology: typeof rawModel.methodology === 'string' ? rawModel.methodology : undefined,
      scope: typeof rawModel.scope === 'string' ? rawModel.scope : undefined,
    },
    event_id: typeof raw.event_id === 'string' ? raw.event_id : undefined,
    platform: typeof raw.platform === 'string' ? raw.platform : undefined,
    data_scope: rawScope as PredictionDataScope,
    cache: {
      hit: rawCache.hit === true,
      stale: rawCache.stale === true,
      snapshot_fingerprint: typeof rawCache.snapshot_fingerprint === 'string' ? rawCache.snapshot_fingerprint : undefined,
      generated_at: typeof rawCache.generated_at === 'string' ? rawCache.generated_at : undefined,
    },
    note: typeof raw.note === 'string' ? raw.note : undefined,
  }
}

function hasPredictionOutput(result: EventModelPrediction | null) {
  if (!result) return false
  if (result.model?.scope && result.model.scope !== 'current_event') return false
  const status = `${String(result.status || '')} ${String(result.model_status || '')}`.toLowerCase()
  if (/(error|failed|unavailable|missing|insufficient|abstain)/.test(status)) return false
  const macro = result.macro
  const micro = result.micro
  return Boolean(
    macro?.trend_points?.length ||
    macro?.predicted_size != null ||
    micro?.top_users?.length,
  )
}

function matchesCurrentPredictionScope(
  result: EventModelPrediction | null,
  requestedEventId: string,
  requestedPlatform: string,
) {
  if (!result) return false
  const resultEventId = String(result.data_scope?.event_id ?? result.event_id ?? '').trim()
  if (resultEventId && resultEventId !== requestedEventId) return false
  const expectedPlatform = requestedPlatform.trim().toLowerCase()
  const resultPlatform = String(result.data_scope?.platform ?? result.platform ?? '').trim().toLowerCase()
  if (expectedPlatform && resultPlatform && resultPlatform !== expectedPlatform) return false
  return result.model?.scope ? result.model.scope === 'current_event' : true
}

function shouldRetryPredictionWithoutPlatform(result: EventModelPrediction | null, requestedPlatform: string) {
  if (!requestedPlatform.trim() || !result) return false
  if (hasPredictionOutput(result)) return false
  const status = `${String(result.status || '')} ${String(result.model_status || '')}`.toLowerCase()
  if (!/(data_insufficient|data_unavailable|abstain|insufficient)/.test(status)) return false
  const scopedEventCount = firstFiniteNumber(
    result.data_scope?.loaded_event_count,
    result.data_scope?.model_input_event_count,
    result.data_scope?.observed_post_count,
    result.data_scope?.observed_comment_count,
    result.macro?.observed_size,
  )
  return scopedEventCount === undefined || scopedEventCount <= 0
}

function hasCalibratedPredictionIntervals(macro: EventModelPrediction['macro']) {
  if (macro?.calibration_status !== 'available') return false
  return (macro.intervals ?? []).some((interval) => {
    const lower = firstFiniteNumber(interval.lower, interval.lower_bound, interval.min)
    const upper = firstFiniteNumber(interval.upper, interval.upper_bound, interval.max)
    return lower !== undefined && upper !== undefined && upper >= lower
  })
}

type ClaimPathDetail = {
  chain: EvidenceChain
  path: EvidencePath
  index: number
}

const directionMap: Record<string, string> = {
  rising: '上升',
  stable: '稳定',
  declining: '下降',
}

function alignSliderMax(rawMax: number, min: number, step: number) {
  const safeStep = Math.max(1, Math.floor(Number(step) || 1))
  const span = Math.max(0, Math.floor(rawMax) - Math.floor(min))
  return Math.floor(min) + Math.ceil(span / safeStep) * safeStep
}

const analyzing = ref(false)
const predicting = ref(false)
const analysisResult = ref<AnalysisResult | null>(null)
const modelPrediction = ref<EventModelPrediction | null>(null)
const evidenceTimeline = ref<PropagationEventTimelineProjection | null>(null)
const evidenceTimelineLoading = ref(false)
const timelineRange = ref<PropagationTimelineRange>('active')
const semanticProjection = ref<SemanticEvidenceProjection | null>(null)
const linkedPropagationArtifact = ref<PropagationAnalysisArtifact | null>(null)
const semanticLoading = ref(false)
const selectedClaim = ref<ClaimGroupItem | null>(null)
const claimDetailOpen = ref(false)
const selectedClaimPathDetail = ref<ClaimPathDetail | null>(null)
const claimPathDetailOpen = ref(false)
const selectedNodeDetail = ref<DiffusionNodeDetail | null>(null)
const nodeDetailOpen = ref(false)
const selectedNextHopUser = ref<NextHopUser | null>(null)
const nextHopDetailOpen = ref(false)
const lastSyncedAt = ref('')
const eventId = ref(DEFAULT_EVENT_ID)
const platform = ref('')
const observedUntil = ref<string | undefined>()
const observationRatio = ref(0.5)
const activeTab = ref('path')
const selectedObjectId = ref('')
const timelineFocusPostId = ref('')
const expandedClaimGroupTypes = ref<Set<string>>(new Set())
const activeClaimGroupType = ref('hashtag')
const claimGroupMenuOpen = ref(false)
const DEFAULT_DIFFUSION_NODE_LIMIT = 160
const CLAIM_GROUP_COLLAPSED_LIMIT = 6
const diffusionNodeLimit = ref(DEFAULT_DIFFUSION_NODE_LIMIT)
const diffusionPendingNodeLimit = ref(DEFAULT_DIFFUSION_NODE_LIMIT)
const diffusionFullViewRequested = ref(false)
const route = useRoute()
const layerChartRef = ref<HTMLDivElement | null>(null)
const pathGraphRef = ref<HTMLDivElement | null>(null)
const modelTrendChartRef = ref<HTMLDivElement | null>(null)
const modelBacktestChartRef = ref<HTMLDivElement | null>(null)
const evidenceTimelineChartRef = ref<HTMLDivElement | null>(null)
let layerChart: echarts.ECharts | null = null
let pathGraphChart: echarts.ECharts | null = null
let modelTrendChart: echarts.ECharts | null = null
let modelBacktestChart: echarts.ECharts | null = null
let evidenceTimelineChart: echarts.ECharts | null = null
let modelTrendResizeObserver: ResizeObserver | null = null
let predictionRequestGeneration = 0
let evidenceTimelineRequestGeneration = 0
let semanticRequestGeneration = 0

const semanticPathOverlay = computed(() => {
  const selectedPath = selectedClaimPathDetail.value?.path
  if (!selectedPath || semanticProjection.value?.status !== 'ready') return null
  if (!linkedPropagationArtifact.value) return null
  if (!hasPropagationPathOverlays(semanticProjection.value.evidence)) return null
  return findPathSemanticOverlay(selectedPath, semanticProjection.value.evidence.cross_analysis.propagation_path_overlays)
})

const analysisReady = computed(() => !!analysisResult.value && !analysisResult.value.error)
const keyRoles = computed(() => analysisResult.value?.key_roles ?? null)
const claims = computed(() => analysisResult.value?.claims ?? [])
const timeline = computed(() => analysisResult.value?.timeline ?? [])
const evidenceChains = computed(() => analysisResult.value?.evidence_chains ?? [])
const linkedPropagationEvidenceChains = computed(() => linkedPropagationArtifact.value?.evidence_chains ?? [])
const semanticDrilldownEvidenceChains = computed(() => (
  linkedPropagationEvidenceChains.value.length ? linkedPropagationEvidenceChains.value : evidenceChains.value
))
const pathAnalysis = computed(() => analysisResult.value?.path_analysis ?? null)
const diffusionSummary = computed(() => {
  const serverSummary = analysisResult.value?.diffusion_summary
  return serverSummary?.visible_nodes?.length ? serverSummary : null
})
const diffusionReady = computed(() => (diffusionSummary.value?.visible_nodes?.length ?? 0) > 0)
const diffusionMeta = computed(() => diffusionSummary.value?.meta ?? {})
const diffusionTotalNodes = computed(() => {
  const total = Number(diffusionMeta.value.total_nodes ?? analysisResult.value?.graph?.node_count ?? 0)
  return Number.isFinite(total) && total > 0 ? Math.floor(total) : DEFAULT_DIFFUSION_NODE_LIMIT
})
const diffusionVisibleCount = computed(() => {
  const count = Number(diffusionMeta.value.visible_node_count ?? diffusionSummary.value?.visible_nodes?.length ?? 0)
  return Number.isFinite(count) && count > 0 ? Math.floor(count) : 0
})
const diffusionSliderStep = computed(() => {
  const rawMax = Math.max(diffusionTotalNodes.value, DEFAULT_DIFFUSION_NODE_LIMIT)
  return rawMax > 1000 ? 50 : 10
})
const diffusionSliderMax = computed(() => {
  const rawMax = Math.max(diffusionTotalNodes.value, DEFAULT_DIFFUSION_NODE_LIMIT)
  const min = Math.min(DEFAULT_DIFFUSION_NODE_LIMIT, rawMax)
  return alignSliderMax(rawMax, min, diffusionSliderStep.value)
})
const diffusionSliderMin = computed(() => Math.min(DEFAULT_DIFFUSION_NODE_LIMIT, diffusionSliderMax.value))
const layerRows = computed(() => diffusionSummary.value?.layers?.length ? diffusionSummary.value.layers : (pathAnalysis.value?.layer_distribution ?? []))
const displayLayerRows = computed(() => normalizeLayerRows(layerRows.value))
const userNameById = computed(() => {
  const map = new Map<string, string>()
  for (const node of analysisResult.value?.graph?.nodes ?? []) {
    const id = String(node.id || '').trim()
    const name = String(node.author_name || '').trim()
    if (id) {
      map.set(id, name || id)
    }
  }
  return map
})
const claimGroups = computed(() => {
  const groups = new Map<string, { type: string; label: string; items: ClaimGroupItem[] }>()
  for (const claim of claims.value) {
    const type = inferClaimType(claim.object_id)
    const label = claimTypeLabel(type)
    if (!groups.has(type)) {
      groups.set(type, { type, label, items: [] })
    }
    groups.get(type)?.items.push({
      ...claim,
      type,
      display: formatClaimObject(claim.object_id),
      href: claimHref(claim.object_id),
    })
  }
  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      items: group.items.sort((left, right) => Number(right.share_count ?? 0) - Number(left.share_count ?? 0)),
    }))
    .sort((left, right) => {
      const order = ['hashtag', 'keyword', 'url', 'tweet', 'other']
      const leftOrder = order.indexOf(left.type)
      const rightOrder = order.indexOf(right.type)
      return (leftOrder === -1 ? order.length : leftOrder) - (rightOrder === -1 ? order.length : rightOrder)
    })
})
const activeClaimGroup = computed(() => {
  if (!claimGroups.value.length) return null
  return claimGroups.value.find((group) => group.type === activeClaimGroupType.value)
    || claimGroups.value.find((group) => group.type === 'hashtag')
    || claimGroups.value[0]
})
const claimTimelineMatches = computed(() => {
  if (!selectedClaim.value) return []
  const objectTimeline = (diffusionSummary.value?.detail_index?.objects?.[selectedClaim.value.object_id] as any)?.timeline
  if (Array.isArray(objectTimeline) && objectTimeline.length) {
    return objectTimeline.slice(0, 30).map((item) => ({
      post_id: item.post_id || '',
      author_id: item.author_id || '',
      author_name: item.author_name || item.author_id || '',
      timestamp: item.timestamp || '',
      content: item.content || '',
    }))
  }
  const needle = selectedClaim.value.object_id.toLowerCase()
  return timeline.value
    .filter((item) => {
      const content = `${item.content || ''} ${item.post_id || ''}`.toLowerCase()
      return content.includes(needle) || needle.includes(content.trim())
    })
    .slice(0, 20)
})
const claimEvidenceMatches = computed(() => {
  if (!selectedClaim.value) return []
  if (!linkedPropagationEvidenceChains.value.length) {
    const objectEvidence = (diffusionSummary.value?.detail_index?.objects?.[selectedClaim.value.object_id] as any)?.evidence
    if (objectEvidence?.claim_id) {
      return [objectEvidence as EvidenceChain]
    }
  }
  return semanticDrilldownEvidenceChains.value
    .filter((item) => item.claim_id === selectedClaim.value?.object_id)
    .slice(0, 10)
})
const requestParams = computed(() => {
  const params: {
    event_id?: string
    platform?: string
    node_limit?: number
    first_layer_limit?: number
    second_layer_limit?: number
  } = {}
  const event = eventId.value.trim()
  const currentPlatform = platform.value.trim()
  if (event) {
    params.event_id = event
  }
  if (currentPlatform) {
    params.platform = currentPlatform
  }
  params.node_limit = diffusionFullViewRequested.value ? 0 : diffusionNodeLimit.value
  if (!diffusionFullViewRequested.value) {
    params.first_layer_limit = 40
    params.second_layer_limit = 80
  }
  return params
})

const predictionRequestParams = computed(() => {
  const params: {
    event_id?: string
    platform?: string
    top_k: number
    observed_until?: string
    observation_ratio: number
  } = {
    top_k: 10,
    observation_ratio: observationRatio.value,
  }
  const event = eventId.value.trim()
  const currentPlatform = platform.value.trim()
  if (event) params.event_id = event
  if (currentPlatform) params.platform = currentPlatform
  if (observedUntil.value) {
    const parsed = new Date(observedUntil.value)
    if (!Number.isNaN(parsed.getTime())) params.observed_until = parsed.toISOString()
  }
  return params
})

const modelPredictionReady = computed(() => {
  return hasPredictionOutput(modelPrediction.value)
})

const timelineRangeOptions: Array<{ value: PropagationTimelineRange; label: string }> = [
  { value: 'active', label: '活跃期' },
  { value: '24h', label: '24小时' },
  { value: '7d', label: '7天' },
  { value: 'all', label: '全部' },
]

const evidenceTimelineReady = computed(() => {
  const timeline = evidenceTimeline.value
  return Boolean((timeline?.observed_points?.length ?? 0) || (timeline?.realized_points?.length ?? 0))
})

const evidenceTimelineResolutionLabel = computed(() => {
  const labels: Record<string, string> = {
    minute: '分钟聚合',
    hour: '小时聚合',
    day: '日聚合',
    week: '周聚合',
  }
  return labels[evidenceTimeline.value?.resolution || ''] || '时间聚合'
})

const historicalBacktestAvailable = computed(() => {
  return (modelPrediction.value?.macro?.realized_points?.length ?? 0) > 1
})

const predictionEmptyDescription = computed(() => {
  const status = `${String(modelPrediction.value?.status || '')} ${String(modelPrediction.value?.model_status || '')}`.toLowerCase()
  if (status.includes('data_unavailable')) return '当前事件数据源不可用，暂无法生成趋势预测'
  if (/(abstain|insufficient)/.test(status)) return '当前事件数据不足，暂无法生成趋势预测'
  if (status.includes('unsupported_platform')) return '当前平台暂无可用趋势预测'
  if (/(unavailable|missing)/.test(status)) return '预测模型暂不可用'
  if (/(error|failed)/.test(status)) return '模型推理失败，请稍后重试'
  if (modelPrediction.value?.note) return modelPrediction.value.note
  return predicting.value ? '正在生成趋势预测' : '暂无趋势预测结果'
})

const modelForecastCards = computed(() => {
  if (!modelPredictionReady.value) {
    return []
  }
  const macro = modelPrediction.value?.macro ?? {}
  const micro = modelPrediction.value?.micro ?? {}
  return [
    {
      key: 'observed',
      label: '已观测规模',
      value: formatNumber(macro.observed_size),
      extra: '当前事件传播前缀',
    },
    {
      key: 'predicted',
      label: '预测最终规模',
      value: formatNumber(macro.predicted_size),
      extra: `参考数据：${modelPrediction.value?.model?.dataset || 'twitter'}`,
    },
    {
      key: 'candidate',
      label: '下一跳候选',
      value: formatNumber(micro.candidate_count),
      extra: `Top-K：${micro.top_users?.length ?? 0} 个用户`,
    },
  ]
})

const modelDirectionLabel = computed(() => directionMap[modelPrediction.value?.macro?.direction ?? ''] ?? '--')

const nextHopColumns = computed(() => [
  {
    title: '排名',
    dataIndex: 'rank',
    width: 72,
  },
  {
    title: '用户名',
    dataIndex: 'author_name',
    key: 'author',
  },
  {
    title: '用户 ID',
    dataIndex: 'author_id',
  },
  {
    title: '候选分数',
    dataIndex: 'score',
    customRender: ({ record }: { record: NextHopUser }) => formatScore(record.score),
  },
  {
    title: '研判类型',
    key: 'assessment',
    width: 94,
  },
  {
    title: '事件出现',
    dataIndex: 'event_count',
    customRender: ({ record }: { record: NextHopUser }) => formatNumber(record.event_count),
  },
  {
    title: '候选来源',
    dataIndex: 'candidate_source',
    key: 'source',
  },
  {
    title: '证据',
    key: 'evidence',
    width: 72,
  },
  {
    title: '最近出现',
    dataIndex: 'last_seen_at',
    key: 'last_seen',
  },
  {
    title: '操作',
    key: 'action',
    width: 150,
  },
])

function formatRatio(value?: number | null) {
  if (value == null || Number.isNaN(value)) {
    return '--'
  }
  return `${Math.round(Number(value) * 100)}%`
}

function ratioPercent(value?: number | null) {
  if (value == null || Number.isNaN(value)) {
    return 0
  }
  return Math.round(Number(value) * 1000) / 10
}

function formatTimestamp(value?: string) {
  if (!value) {
    return '--'
  }
  return value.replace('T', ' ').replace('Z', '')
}

function formatTimelineWindow(window?: { start?: string; end?: string } | null) {
  if (!window?.start || !window.end) return '暂无时间范围'
  return `${formatTimestamp(window.start)} 至 ${formatTimestamp(window.end)}`
}

function hasNonEmptyDistribution(value: unknown) {
  return isRecord(value) && Object.entries(value).length > 0 && Object.entries(value).every(
    ([label, count]) => Boolean(label.trim()) && typeof count === 'number' && Number.isFinite(count),
  )
}

function hasSemanticFeatureRecords(value: unknown, field: 'term' | 'label' | 'text') {
  return Array.isArray(value) && value.length > 0 && value.every((item) => (
    isRecord(item)
    && typeof item[field] === 'string'
    && Boolean(item[field].trim())
    && (item.count === undefined || (typeof item.count === 'number' && Number.isFinite(item.count)))
  ))
}

function hasNonEmptyTextList(value: unknown) {
  return Array.isArray(value) && value.length > 0 && value.every((item) => typeof item === 'string' && Boolean(item.trim()))
}

function normalizePathId(value: unknown) {
  if (typeof value !== 'string' && (typeof value !== 'number' || !Number.isFinite(value))) return ''
  return String(value).trim()
}

function normalizeEvidenceReference(value: unknown) {
  if (typeof value === 'string') {
    const parts = value.trim().split(':')
    if (parts.length < 3) return ''
    const platform = parts[0].trim()
    const kind = parts[1].trim()
    const id = parts.slice(2).join(':').trim()
    if (!platform || !id || (kind !== 'post' && kind !== 'comment')) return ''
    return `${platform}:${kind}:${id}`
  }
  if (!isRecord(value)) return ''
  const platform = optionalText(value.platform)
  if (!platform) return ''
  const postId = optionalText(value.post_id)
  if (postId) return `${platform}:post:${postId}`
  const commentId = optionalText(value.comment_id)
  if (commentId) return `${platform}:comment:${commentId}`
  return ''
}

function normalizeEvidenceRefs(value: unknown) {
  const refs = Array.isArray(value) ? value : []
  return refs
    .map((item) => normalizeEvidenceReference(item))
    .filter((item) => item.length > 0)
}

function hasCanonicalEvidenceRefs(value: unknown) {
  return Array.isArray(value) && value.length > 0 && normalizeEvidenceRefs(value).length === value.length
}

function hasPropagationPathOverlays(value: unknown): value is { cross_analysis: { propagation_path_overlays: SemanticPathOverlay[] } } {
  if (!isRecord(value) || !isRecord(value.cross_analysis)) return false
  const overlays = value.cross_analysis.propagation_path_overlays
  return Array.isArray(overlays) && overlays.every((candidate) => {
    if (!isRecord(candidate) || !normalizePathId(candidate.path_id)) return false
    const overlay = candidate.semantic_overlay
    const timeRange = isRecord(overlay) ? overlay.time_range : undefined
    return isRecord(overlay)
      && hasNonEmptyDistribution(overlay.sentiment)
      && hasSemanticFeatureRecords(overlay.keywords, 'term')
      && hasSemanticFeatureRecords(overlay.topics, 'label')
      && hasSemanticFeatureRecords(overlay.entities, 'text')
      && hasNonEmptyDistribution(overlay.stance)
      && hasNonEmptyTextList(overlay.platforms)
      && isRecord(timeRange)
      && typeof timeRange.start === 'string'
      && Boolean(timeRange.start.trim())
      && typeof timeRange.end === 'string'
      && Boolean(timeRange.end.trim())
      && hasCanonicalEvidenceRefs(overlay.evidence_refs)
  })
}

function sameEvidenceRefs(left: unknown, right: unknown) {
  const leftRefs = normalizeEvidenceRefs(left).sort()
  const rightRefs = normalizeEvidenceRefs(right).sort()
  if (leftRefs.length !== rightRefs.length || leftRefs.length === 0) return false
  return leftRefs.every((item, index) => item === rightRefs[index])
}

function pathEvidenceRefs(path: EvidencePath) {
  const metadataEvidenceRefs = Array.isArray(path.metadata?.evidence_refs)
    ? path.metadata.evidence_refs
    : []
  const rawRefs = Array.isArray(path.evidence_refs) ? path.evidence_refs : metadataEvidenceRefs
  return normalizeEvidenceRefs(rawRefs)
}

function normalizeSemanticOverlay(overlay: SemanticPathOverlay['semantic_overlay']): SemanticOverlayPayload {
  return {
    ...overlay,
    evidence_refs: normalizeEvidenceRefs(overlay.evidence_refs),
  }
}

function artifactSnapshotId(artifact: PropagationAnalysisArtifact) {
  return optionalText(artifact.snapshot_id)
}

function artifactDataFingerprint(artifact: PropagationAnalysisArtifact) {
  const manifest = isRecord(artifact.artifact_manifest) ? artifact.artifact_manifest : null
  return optionalText(artifact.data_fingerprint) || optionalText(manifest?.data_fingerprint)
}

function semanticEmbeddingFingerprint(evidence: unknown) {
  if (!isRecord(evidence) || !isRecord(evidence.embedding_manifest)) return ''
  const manifest = evidence.embedding_manifest
  return optionalText(manifest.snapshot_fingerprint)
    || optionalText(manifest.data_fingerprint)
    || optionalText(manifest.fingerprint)
}

function hasLinkedEvidenceChains(artifact: PropagationAnalysisArtifact) {
  return Array.isArray(artifact.evidence_chains) && artifact.evidence_chains.length > 0
}

function isVerifiedLinkedPropagationArtifact(semantic: SemanticEvidenceProjection, artifact: PropagationAnalysisArtifact) {
  if (semantic.status !== 'ready' || !semantic.run_id || !semantic.snapshot_id || !artifact) return false
  if (artifactSnapshotId(artifact) !== semantic.snapshot_id) return false
  const artifactStatus = optionalText(artifact.status).toLowerCase()
  if (artifactStatus !== 'ok' && artifactStatus !== 'completed') return false
  if (artifact.fallback === true) return false
  const semanticFingerprint = semanticEmbeddingFingerprint(semantic.evidence)
  const artifactFingerprint = artifactDataFingerprint(artifact)
  if (semanticFingerprint && artifactFingerprint && semanticFingerprint !== artifactFingerprint) return false
  return hasLinkedEvidenceChains(artifact)
}

function findPathSemanticOverlay(path: EvidencePath, overlays: SemanticPathOverlay[]) {
  const pathId = normalizePathId(path.path_id)
  const evidenceRefs = pathEvidenceRefs(path)
  if (!pathId || !evidenceRefs.length) return null
  const matchedOverlay = overlays.find((overlay) => (
    normalizePathId(overlay.path_id) === pathId
    && sameEvidenceRefs(overlay.semantic_overlay.evidence_refs, evidenceRefs)
  ))
  return matchedOverlay ? normalizeSemanticOverlay(matchedOverlay.semantic_overlay) : null
}

function formatSemanticDistribution(values: Record<string, number>) {
  return Object.entries(values).map(([label, count]) => `${label} ${count}`).join('、') || '--'
}

function formatSemanticTerms(
  values: Array<{ term?: string; label?: string; text?: string; count?: number }>,
  field: 'term' | 'label' | 'text',
) {
  return values.map((item) => `${item[field]}${item.count === undefined ? '' : ` ${item.count}`}`).join('、') || '--'
}

function formatSemanticTimeRange(value: { start: string; end: string } | null) {
  return value ? `${formatTimestamp(value.start)} 至 ${formatTimestamp(value.end)}` : '--'
}

function updateSyncTime() {
  lastSyncedAt.value = new Date().toLocaleString('zh-CN', { hour12: false })
}

function formatNumber(value?: number | null) {
  if (value == null || Number.isNaN(Number(value))) {
    return '--'
  }
  return Number(value).toLocaleString('zh-CN')
}

function formatScore(value?: number | null) {
  if (value == null || Number.isNaN(Number(value))) {
    return '--'
  }
  return Number(value).toFixed(4)
}

function candidateSourceLabel(value?: string) {
  const labels: Record<string, string> = {
    observed_user_hash_bucket_proxy: '当前事件候选',
    observed_event: '当前事件用户',
    observed_post: '当前事件帖子用户',
    observed_comment: '当前事件评论用户',
    comment_interaction: '评论互动邻居',
    shared_object: '同共享对象参与者',
  }
  return labels[value || ''] || value || '--'
}

function modelScopeLabel(value?: string) {
  if (value === 'current_event') return '当前事件'
  if (value === 'research_benchmark') return '研究基准'
  return value || '--'
}

function nextHopAssessmentLabel(record: NextHopUser) {
  const value = String(record.assessment_type || record.activation_type || '').toLowerCase()
  if (value.includes('new') || value.includes('first')) return '新激活'
  if (value.includes('reactiv') || value.includes('observed') || value.includes('repeat')) return '再激活'
  return record.event_count && record.event_count > 0 ? '再激活' : '新激活'
}

function nextHopAssessmentColor(record: NextHopUser) {
  return nextHopAssessmentLabel(record) === '新激活' ? 'green' : 'cyan'
}

function nextHopRowProps(record: NextHopUser) {
  return {
    class: 'clickable-table-row',
    onClick: () => openNextHopTrace(record),
  }
}

function openNextHopTrace(record: NextHopUser) {
  selectedNextHopUser.value = record
  nextHopDetailOpen.value = true
}

async function locateNextHopOnPath(record: NextHopUser) {
  const nodeId = String(record?.author_id || '').trim()
  if (!nodeId) return
  const nodes = diffusionSummary.value?.visible_nodes ?? []
  const dataIndex = nodes.findIndex((node) => String(node.id) === nodeId)
  if (dataIndex < 0) {
    if (!diffusionFullViewRequested.value && diffusionTotalNodes.value > nodes.length) {
      diffusionPendingNodeLimit.value = diffusionSliderMax.value
      diffusionNodeLimit.value = diffusionSliderMax.value
      diffusionFullViewRequested.value = true
      await loadAnalysis(false, true)
      await locateNextHopOnPath(record)
      return
    }
    nextHopDetailOpen.value = false
    activeTab.value = 'path'
    await nextTick()
    await renderPathTabCharts()
    message.info('该用户尚未出现在当前观测传播路径中，无法定位。')
    return
  }
  nextHopDetailOpen.value = false
  activeTab.value = 'path'
  await nextTick()
  await renderPathTabCharts()
  openNodeDetail(nodeId)
  if (pathGraphChart) {
    pathGraphChart.dispatchAction({ type: 'downplay', seriesIndex: 0 })
    pathGraphChart.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex })
    pathGraphChart.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex })
  }
}

async function locateUserOnPath(userId: string) {
  const record: NextHopUser = { rank: 0, author_id: String(userId || '') }
  await locateNextHopOnPath(record)
}

async function locateEvidenceReference(reference: { post_id?: string; author_id?: string }) {
  timelineFocusPostId.value = String(reference.post_id || '')
  const nodeId = String(reference.author_id || '').trim()
  const nodeExists = (diffusionSummary.value?.visible_nodes ?? []).some((node) => String(node.id) === nodeId)
  if (nodeExists) {
    await locateUserOnPath(String(reference.author_id))
    return
  }
  activeTab.value = 'timeline'
  await nextTick()
}

async function focusObjectOnPath(objectId: string) {
  selectedObjectId.value = String(objectId || '')
  activeTab.value = 'path'
  await nextTick()
  await renderPathTabCharts()
}

function normalizeLayerRows(rows: LayerRow[]) {
  const counts = new Map<number, number>()
  for (const row of rows) {
    const level = Number(row.level)
    if (!Number.isFinite(level) || level < 0) continue
    counts.set(level, (counts.get(level) || 0) + Number(row.node_count || 0))
  }

  const fixedRows: LayerRow[] = [0, 1, 2, 3, 4].map((level) => ({
    level,
    label: level === 0 ? '源头层' : `第${level}层`,
    node_count: counts.get(level) || 0,
    ratio: 0,
  }))
  const otherCount = Array.from(counts.entries())
    .filter(([level]) => level >= 5)
    .reduce((sum, [, count]) => sum + count, 0)
  const mergedRows = [
    ...fixedRows,
    {
      level: 999,
      label: '其它',
      node_count: otherCount,
      ratio: 0,
    },
  ]
  const total = mergedRows.reduce((sum, row) => sum + row.node_count, 0)
  if (total <= 0) {
    return mergedRows
  }
  return mergedRows.map((row) => ({
    ...row,
    ratio: row.node_count / total,
  }))
}

function buildLayerOption(rows: LayerRow[]): EChartsOption {
  return {
    backgroundColor: 'transparent',
    grid: {
      left: 42,
      right: 14,
      top: 20,
      bottom: 28,
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const item = params?.[0]
        const row = rows[item?.dataIndex]
        return row ? `${row.label}<br/>节点数：${row.node_count}<br/>占比：${formatRatio(row.ratio)}` : ''
      },
    },
    xAxis: {
      type: 'category',
      data: rows.map((item) => item.label),
      axisLabel: { color: '#64748b' },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.28)' } },
    },
    series: [
      {
        type: 'bar',
        data: rows.map((item) => item.node_count),
        barWidth: 28,
        itemStyle: {
          color: '#d7e51f',
          borderRadius: [6, 6, 0, 0],
        },
      },
    ],
  }
}

function buildModelTrendOption(): EChartsOption {
  const macro = modelPrediction.value?.macro ?? {}
  const observedSize = Number(macro.observed_size ?? 0)
  const trendPoints = (Array.isArray(macro.trend_points) ? macro.trend_points : []).map((item, index) => ({
    label: (item.at || item.timestamp) ? formatTimestamp(item.at || item.timestamp) : `模型相对步 ${item.step || index + 1}`,
    value: Number(item.predicted_size ?? 0),
  }))
  if (!trendPoints.length && macro.predicted_size != null) {
    trendPoints.push({ label: '模型相对步 最终', value: Number(macro.predicted_size) })
  }
  const labels = ['观测终点', ...trendPoints.map((item) => item.label)]
  const observedData = [observedSize, ...trendPoints.map(() => null)]
  const predictedData = [observedSize, ...trendPoints.map((item) => item.value)]
  const intervals = Array.isArray(macro.intervals) ? macro.intervals : []
  const showPredictionInterval = hasCalibratedPredictionIntervals(macro)
  const intervalByStep = new Map(intervals.map((item, index) => [String(item.step ?? item.timestamp ?? index + 1), item]))
  const intervalLower = showPredictionInterval ? [...observedData.map(() => null), ...trendPoints.map((_, index) => {
    const interval = intervalByStep.get(String((macro.trend_points ?? [])[index]?.step ?? index + 1))
    return interval?.lower ?? interval?.lower_bound ?? interval?.min ?? null
  })] : []
  const intervalUpper = showPredictionInterval ? [...observedData.map(() => null), ...trendPoints.map((_, index) => {
    const interval = intervalByStep.get(String((macro.trend_points ?? [])[index]?.step ?? index + 1))
    return interval?.upper ?? interval?.upper_bound ?? interval?.max ?? null
  })] : []
  const series: EChartsOption['series'] = [
    {
      name: '真实观测累计',
      type: 'line',
      data: observedData,
      symbolSize: 9,
      smooth: false,
      lineStyle: { width: 3 },
      itemStyle: { color: '#0891b2' },
    },
    {
      name: '模型相对预测',
      type: 'line',
      data: predictedData,
      symbolSize: 7,
      smooth: false,
      lineStyle: { width: 3, type: 'dashed', color: '#2563eb' },
      itemStyle: { color: '#2563eb' },
    },
  ]
  if (showPredictionInterval) {
    series.push(
      {
        name: '预测区间下界',
        type: 'line',
        data: intervalLower,
        symbol: 'none',
        lineStyle: { width: 0, opacity: 0 },
        stack: 'prediction_interval',
        tooltip: { show: false },
      },
      {
        name: '预测区间',
        type: 'line',
        data: intervalUpper.map((upper, index) => upper == null || intervalLower[index] == null ? null : Number(upper) - Number(intervalLower[index])),
        symbol: 'none',
        lineStyle: { width: 0, opacity: 0 },
        areaStyle: { color: 'rgba(59, 130, 246, 0.16)' },
        stack: 'prediction_interval',
      },
    )
  }

  return {
    backgroundColor: 'transparent',
    grid: {
      left: 48,
      right: 24,
      top: 34,
      bottom: 34,
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const rows = Array.isArray(params) ? params : []
        return rows
          .filter((item) => item.value != null)
          .map((item) => `${item.marker}${item.seriesName}：${formatNumber(Number(item.value))}`)
          .join('<br/>')
      },
    },
    legend: {
      top: 4,
      right: 12,
      data: showPredictionInterval ? ['真实观测累计', '模型相对预测', '预测区间'] : ['真实观测累计', '模型相对预测'],
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels,
      axisLabel: { color: '#64748b' },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
    },
    yAxis: {
      type: 'value',
      min: 0,
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.25)' } },
    },
    series,
  }
}

function buildHistoricalBacktestOption(): EChartsOption {
  const macro = modelPrediction.value?.macro ?? {}
  const observedPoints = Array.isArray(macro.observed_points) ? macro.observed_points : []
  const realizedPoints = Array.isArray(macro.realized_points) ? macro.realized_points : []
  const observedByTime = new Map(observedPoints.filter((point) => point.at).map((point) => [String(point.at), point.cumulative_size]))
  const realizedByTime = new Map(realizedPoints.filter((point) => point.at).map((point) => [String(point.at), point.cumulative_size]))
  const timestamps = Array.from(new Set([...observedByTime.keys(), ...realizedByTime.keys()])).sort((left, right) => left.localeCompare(right))
  const labels = timestamps.map((timestamp) => formatTimestamp(timestamp))
  const observedData = timestamps.map((timestamp) => observedByTime.get(timestamp) ?? null)
  const realizedData = timestamps.map((timestamp) => realizedByTime.get(timestamp) ?? null)

  return {
    backgroundColor: 'transparent',
    grid: { left: 48, right: 24, top: 34, bottom: 34 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => (Array.isArray(params) ? params : [])
        .filter((item) => item.value != null)
        .map((item) => `${item.marker}${item.seriesName}：${formatNumber(Number(item.value))}`)
        .join('<br/>'),
    },
    legend: { top: 4, right: 12, data: ['真实观测累计', '历史实际累计'] },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels,
      axisLabel: { color: '#64748b' },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
    },
    yAxis: {
      type: 'value',
      min: 0,
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.25)' } },
    },
    series: [
      {
        name: '真实观测累计',
        type: 'line',
        data: observedData,
        symbolSize: 7,
        smooth: false,
        lineStyle: { width: 3, color: '#0891b2' },
        itemStyle: { color: '#0891b2' },
      },
      {
        name: '历史实际累计',
        type: 'line',
        data: realizedData,
        symbolSize: 7,
        smooth: false,
        lineStyle: { width: 3, type: 'dashed', color: '#f97316' },
        itemStyle: { color: '#f97316' },
      },
    ],
  }
}

function buildEvidenceTimelineOption(): EChartsOption {
  const timeline = evidenceTimeline.value
  const observedByTime = new Map((timeline?.observed_points ?? []).map((point) => [point.at, point.cumulative_size]))
  const realizedByTime = new Map((timeline?.realized_points ?? []).map((point) => [point.at, point.cumulative_size]))
  const timestamps = Array.from(new Set([...observedByTime.keys(), ...realizedByTime.keys()])).sort((left, right) => left.localeCompare(right))

  return {
    backgroundColor: 'transparent',
    grid: { left: 48, right: 24, top: 34, bottom: 58 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => (Array.isArray(params) ? params : [])
        .filter((item) => item.value != null)
        .map((item) => `${item.marker}${item.seriesName}：${formatNumber(Number(item.value))}`)
        .join('<br/>'),
    },
    legend: { top: 4, right: 12, data: ['真实观测累计', '历史实际累计'] },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: timestamps.map((timestamp) => formatTimestamp(timestamp)),
      axisLabel: { color: '#64748b', hideOverlap: true },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
    },
    yAxis: {
      type: 'value',
      min: 0,
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.25)' } },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'filter' },
      { type: 'slider', xAxisIndex: 0, filterMode: 'filter', height: 18, bottom: 8 },
    ],
    series: [
      {
        name: '真实观测累计',
        type: 'line',
        data: timestamps.map((timestamp) => observedByTime.get(timestamp) ?? null),
        showSymbol: false,
        smooth: false,
        connectNulls: false,
        lineStyle: { width: 3, color: '#0891b2' },
        itemStyle: { color: '#0891b2' },
      },
      {
        name: '历史实际累计',
        type: 'line',
        data: timestamps.map((timestamp) => realizedByTime.get(timestamp) ?? null),
        showSymbol: false,
        smooth: false,
        connectNulls: false,
        lineStyle: { width: 3, type: 'dashed', color: '#f97316' },
        itemStyle: { color: '#f97316' },
      },
    ],
  }
}

function shortNodeLabel(value: string) {
  const text = String(value || '').trim()
  if (!text) return '--'
  return text.length > 10 ? `${text.slice(0, 10)}…` : text
}

function fitGraphPositions(
  positions: Map<string, { x: number; y: number; layer: number }>,
) {
  const values = Array.from(positions.values())
  if (!values.length) return positions

  const xs = values.map((position) => position.x)
  const ys = values.map((position) => position.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const width = Math.max(maxX - minX, 1)
  const height = Math.max(maxY - minY, 1)
  const scale = Math.min(520 / width, 430 / height, 0.92)
  const centerX = (minX + maxX) / 2
  const centerY = (minY + maxY) / 2
  const fitted = new Map<string, { x: number; y: number; layer: number }>()
  for (const [id, position] of positions.entries()) {
    fitted.set(id, {
      x: (position.x - centerX) * scale,
      y: (position.y - centerY) * scale,
      layer: position.layer,
    })
  }

  return fitted
}

function updatePathGraphLabelsByZoom(event?: unknown) {
  if (!pathGraphChart) return
  const option = pathGraphChart.getOption() as any
  const series = option?.series?.[0]
  const optionZoom = Array.isArray(series?.zoom) ? series.zoom[0] : series?.zoom
  const eventZoom = typeof event === 'object' && event !== null && 'zoom' in event
    ? Number((event as { zoom?: number }).zoom)
    : undefined
  const zoom = Number(eventZoom ?? optionZoom ?? 1)
  const rootId = String(diffusionSummary.value?.root_node?.id || diffusionSummary.value?.visible_nodes?.find((node) => node.is_root)?.id || '')
  const compact = Number.isFinite(zoom) && zoom < 0.65
  const data = (series?.data ?? []).map((node: any) => ({
    ...node,
    label: {
      ...(node.label ?? {}),
      show: compact ? String(node.userId || node.id) === rootId : true,
    },
  }))
  pathGraphChart.setOption({ series: [{ data }] }, false)
}

function displayUserName(userId: string) {
  const id = String(userId || '').trim()
  return userNameById.value.get(id) || id || '--'
}

function formatNodePath(nodes?: string[]) {
  if (!nodes?.length) return '--'
  return nodes.map((node) => displayUserName(node)).join(' → ')
}

function buildPathGraphOption(summary?: DiffusionSummary | null): EChartsOption {
  const nodes = summary?.visible_nodes ?? []
  const nodeById = new Map(nodes.map((node) => [String(node.id), node]))
  const rootId = String(summary?.root_node?.id || nodes.find((node) => node.is_root)?.id || nodes[0]?.id || '')

  const nodesByLayer = new Map<number, DiffusionNode[]>()
  for (const node of nodes) {
    const layer = Math.max(0, Number(node.layer ?? 0))
    if (!nodesByLayer.has(layer)) nodesByLayer.set(layer, [])
    nodesByLayer.get(layer)?.push(node)
  }

  const positions = new Map<string, { x: number; y: number; layer: number }>()
  const radialGap = 95
  positions.set(rootId, { x: 0, y: 0, layer: 0 })

  for (const [layer, layerNodes] of nodesByLayer.entries()) {
    if (layer === 0) continue
    const ringNodes = layerNodes
      .filter((node) => String(node.id) !== rootId)
      .sort((left, right) => {
        const leftScore = Number(left.out_degree ?? 0) + Number(left.post_count ?? 0) + (left.is_key ? 100 : 0)
        const rightScore = Number(right.out_degree ?? 0) + Number(right.post_count ?? 0) + (right.is_key ? 100 : 0)
        if (rightScore !== leftScore) return rightScore - leftScore
        return String(left.id).localeCompare(String(right.id))
      })
    if (!ringNodes.length) continue
    const radius = Math.max(1, layer) * radialGap
    const step = (Math.PI * 2) / Math.max(ringNodes.length, 1)
    const offset = layer % 2 === 0 ? -Math.PI / 2 : -Math.PI / 2 + step / 2
    ringNodes.forEach((node, index) => {
      const angle = offset + step * index
      positions.set(String(node.id), {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        layer,
      })
    })
  }
  const fittedPositions = fitGraphPositions(positions)

  const graphData = nodes.map((node) => {
    const id = String(node.id)
    const position = fittedPositions.get(id) || { x: 0, y: 0, layer: Number(node.layer ?? 0) }
    const isRoot = id === rootId || Boolean(node.is_root)
    const isKey = Boolean(node.is_key)
    const objectFocused = Boolean(selectedObjectId.value) && (node.shared_object_ids ?? []).includes(selectedObjectId.value)
    const value = Math.max(1, Number(node.post_count ?? 1))
    return {
      id,
      name: id,
      userId: id,
      x: position.x,
      y: position.y,
      value,
      category: isRoot ? 0 : isKey ? 1 : 2,
      symbolSize: isRoot ? 34 : isKey ? 8 : Math.max(2.8, Math.min(5.8, Math.sqrt(value) * 1.05 + 1.7)),
      label: {
        show: true,
        color: isRoot ? '#f8fafc' : '#dbeafe',
        fontSize: isRoot ? 12 : 9,
        fontWeight: isRoot ? 700 : 500,
        formatter: shortNodeLabel(node.author_name || displayUserName(id)),
      },
      itemStyle: {
        opacity: objectFocused || isRoot || isKey ? 1 : 0.42,
        borderColor: objectFocused ? '#facc15' : undefined,
        borderWidth: objectFocused ? 2 : 0,
      },
    }
  })

  return {
    backgroundColor: {
      type: 'linear',
      x: 0,
      y: 0,
      x2: 1,
      y2: 1,
      colorStops: [
        { offset: 0, color: '#071826' },
        { offset: 0.52, color: '#102235' },
        { offset: 1, color: '#06111d' },
      ],
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const node = nodeById.get(String(params.data.userId))
        const degreeText = `出度：${node?.out_degree ?? 0} / 入度：${node?.in_degree ?? 0}`
        return `${displayUserName(params.data.userId)}<br/>用户ID：${params.data.userId}<br/>${degreeText}`
      },
    },
    legend: {
      top: 10,
      left: 14,
      itemWidth: 18,
      itemHeight: 10,
      textStyle: { color: '#cbd5e1', fontSize: 11 },
      data: ['源头', '关键节点', '普通节点'],
    },
    series: [
      {
        type: 'graph',
        layout: 'none',
        roam: 'scale',
        zoom: 0.94,
        center: ['50%', '50%'],
        draggable: false,
        top: 54,
        bottom: 22,
        left: 24,
        right: 24,
        categories: [
          { name: '源头', itemStyle: { color: '#facc15' } },
          { name: '关键节点', itemStyle: { color: '#00d9ff' } },
          { name: '普通节点', itemStyle: { color: '#60a5fa' } },
        ],
        data: graphData,
        links: [],
        label: {
          color: '#eef6ff',
          fontSize: 10,
          position: 'right',
        },
        labelLayout: {
          hideOverlap: true,
        },
      },
    ],
  }
}

async function renderLayerChart() {
  await nextTick()
  if (!layerChartRef.value || layerChartRef.value.offsetWidth === 0 || layerChartRef.value.offsetHeight === 0) return
  if (!layerChart) {
    layerChart = echarts.init(layerChartRef.value)
  }
  layerChart.setOption(buildLayerOption(displayLayerRows.value), true)
  layerChart.resize()
}

async function renderPathGraph() {
  await nextTick()
  if (!pathGraphRef.value || pathGraphRef.value.offsetWidth === 0 || pathGraphRef.value.offsetHeight === 0) return
  if (!pathGraphChart) {
    pathGraphChart = echarts.init(pathGraphRef.value)
  }
  pathGraphChart.off('click')
  pathGraphChart.off('graphRoam')
  pathGraphChart.off('georoam')
  pathGraphChart.on('click', (params: any) => {
    if (params.dataType !== 'node') return
    openNodeDetail(String(params.data?.userId || params.data?.id || ''))
  })
  pathGraphChart.on('graphRoam', updatePathGraphLabelsByZoom)
  pathGraphChart.on('georoam', updatePathGraphLabelsByZoom)
  pathGraphChart.setOption(buildPathGraphOption(diffusionSummary.value), true)
  updatePathGraphLabelsByZoom()
  pathGraphChart.resize()
}

function observeModelTrendContainer(container: HTMLDivElement) {
  if (typeof ResizeObserver === 'undefined') return
  if (!modelTrendResizeObserver) {
    modelTrendResizeObserver = new ResizeObserver((entries) => {
      const visible = entries.some((entry) => entry.contentRect.width > 0 && entry.contentRect.height > 0)
      if (visible && activeTab.value === 'model' && modelPredictionReady.value) {
        void renderModelTrendChart()
        void renderHistoricalBacktestChart()
      }
    })
  }
  modelTrendResizeObserver.observe(container)
}

function disposeModelTrendChart() {
  modelTrendChart?.dispose()
  modelTrendChart = null
  modelBacktestChart?.dispose()
  modelBacktestChart = null
  modelTrendResizeObserver?.disconnect()
  modelTrendResizeObserver = null
}

function disposeEvidenceTimelineChart() {
  evidenceTimelineChart?.dispose()
  evidenceTimelineChart = null
}

async function renderModelTrendChart() {
  await nextTick()
  if (activeTab.value !== 'model' || !modelPredictionReady.value) return
  const container = modelTrendChartRef.value
  if (!container) return
  if (container.offsetWidth === 0 || container.offsetHeight === 0) {
    return
  }
  if (modelTrendChart && modelTrendChart.getDom() !== container) {
    disposeModelTrendChart()
  }
  observeModelTrendContainer(container)
  if (!modelTrendChart) {
    modelTrendChart = echarts.init(container)
  }
  modelTrendChart.setOption(buildModelTrendOption(), true)
  modelTrendChart.resize()
}

async function renderHistoricalBacktestChart() {
  await nextTick()
  if (activeTab.value !== 'model' || !historicalBacktestAvailable.value) {
    modelBacktestChart?.dispose()
    modelBacktestChart = null
    return
  }
  const container = modelBacktestChartRef.value
  if (!container || container.offsetWidth === 0 || container.offsetHeight === 0) return
  if (modelBacktestChart && modelBacktestChart.getDom() !== container) {
    modelBacktestChart.dispose()
    modelBacktestChart = null
  }
  if (!modelBacktestChart) {
    modelBacktestChart = echarts.init(container)
  }
  modelBacktestChart.setOption(buildHistoricalBacktestOption(), true)
  modelBacktestChart.resize()
}

async function renderEvidenceTimelineChart() {
  await nextTick()
  if (activeTab.value !== 'model' || !evidenceTimelineReady.value) return
  const container = evidenceTimelineChartRef.value
  if (!container || container.offsetWidth === 0 || container.offsetHeight === 0) return
  if (evidenceTimelineChart && evidenceTimelineChart.getDom() !== container) {
    disposeEvidenceTimelineChart()
  }
  if (!evidenceTimelineChart) {
    evidenceTimelineChart = echarts.init(container)
  }
  evidenceTimelineChart.setOption(buildEvidenceTimelineOption(), true)
  evidenceTimelineChart.resize()
}

function scheduleEvidenceTimelineRender() {
  void nextTick().then(() => {
    void renderEvidenceTimelineChart()
    const renderAgain = () => {
      void renderEvidenceTimelineChart()
    }
    if (typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(renderAgain)
    } else {
      window.setTimeout(renderAgain, 0)
    }
  })
}

function scheduleModelTrendChartRender() {
  void nextTick().then(() => {
    void renderModelTrendChart()
    void renderHistoricalBacktestChart()
    const renderAgain = () => {
      void renderModelTrendChart()
      void renderHistoricalBacktestChart()
    }
    if (typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(renderAgain)
    } else {
      window.setTimeout(renderAgain, 0)
    }
  })
}

function resizeCharts() {
  layerChart?.resize()
  pathGraphChart?.resize()
  modelTrendChart?.resize()
  modelBacktestChart?.resize()
  evidenceTimelineChart?.resize()
}

async function renderPathTabCharts() {
  if (activeTab.value !== 'path') return
  await Promise.all([renderLayerChart(), renderPathGraph()])
}

async function renderActiveTabCharts() {
  if (activeTab.value === 'path') {
    await renderPathTabCharts()
    return
  }
  if (activeTab.value === 'model') {
    await Promise.all([renderModelTrendChart(), renderHistoricalBacktestChart(), renderEvidenceTimelineChart()])
  }
}

function inferClaimType(value: string) {
  const text = String(value || '').trim()
  if (/^https?:\/\//i.test(text)) {
    if (/twitter\.com|x\.com|weibo\.com|m\.weibo\.cn|t\.cn/i.test(text)) return 'tweet'
    return 'url'
  }
  if (text.startsWith('#')) return 'hashtag'
  if (text.length <= 32) return 'keyword'
  return 'other'
}

function claimTypeLabel(type: string) {
  const labels: Record<string, string> = {
    tweet: '推文 / 帖子链接',
    url: 'URL',
    hashtag: '话题标签',
    keyword: '关键词',
    other: '其他对象',
  }
  return labels[type] || '其他对象'
}

function formatClaimObject(value: string) {
  const text = String(value || '').trim()
  if (!text) return '--'
  return text.length > 96 ? `${text.slice(0, 96)}...` : text
}

function claimHref(value: string) {
  const text = String(value || '').trim()
  return /^https?:\/\//i.test(text) ? text : undefined
}

function isClaimGroupExpanded(type: string) {
  return expandedClaimGroupTypes.value.has(type)
}

function visibleClaimGroupItems(group: { type: string; items: ClaimGroupItem[] }) {
  return isClaimGroupExpanded(group.type)
    ? group.items
    : group.items.slice(0, CLAIM_GROUP_COLLAPSED_LIMIT)
}

function showMoreClaimGroup(type: string) {
  const next = new Set(expandedClaimGroupTypes.value)
  if (next.has(type)) {
    next.delete(type)
  } else {
    next.add(type)
  }
  expandedClaimGroupTypes.value = next
}

function handleClaimGroupMenuClick({ key }: { key: string }) {
  activeClaimGroupType.value = String(key)
  claimGroupMenuOpen.value = false
}

function openClaimDetail(item: ClaimGroupItem) {
  selectedClaim.value = item
  selectedObjectId.value = item.object_id
  claimDetailOpen.value = true
  if (activeTab.value === 'path') {
    void renderPathTabCharts()
  }
}

function openClaimPathDetail(chain: EvidenceChain, path: EvidencePath, index: number) {
  selectedClaimPathDetail.value = { chain, path, index }
  claimPathDetailOpen.value = true
}

function openNodeDetail(nodeId: string) {
  const id = String(nodeId || '').trim()
  if (!id) return
  const detail = diffusionSummary.value?.detail_index?.nodes?.[id]
  selectedNodeDetail.value = detail || {
    id,
    author_name: displayUserName(id),
  }
  nodeDetailOpen.value = true
}

function firstQueryValue(value: unknown) {
  if (Array.isArray(value)) {
    return String(value[0] ?? '').trim()
  }
  return String(value ?? '').trim()
}

function syncScopeFromRoute() {
  predictionRequestGeneration += 1
  predicting.value = false
  eventId.value = firstQueryValue(route.query.event_id) || DEFAULT_EVENT_ID
  platform.value = firstQueryValue(route.query.platform)
  observedUntil.value = firstQueryValue(route.query.observed_until) || undefined
}

function resetSemanticProjection() {
  semanticRequestGeneration += 1
  semanticProjection.value = null
  linkedPropagationArtifact.value = null
  semanticLoading.value = false
}

async function loadSemanticProjection() {
  const requestedEventId = eventId.value.trim()
  const requestGeneration = ++semanticRequestGeneration
  semanticProjection.value = null
  linkedPropagationArtifact.value = null
  semanticLoading.value = Boolean(requestedEventId)
  if (!requestedEventId) return
  try {
    const response = await getEventSemantic(requestedEventId)
    if (requestGeneration !== semanticRequestGeneration || requestedEventId !== eventId.value.trim()) return
    semanticProjection.value = response.data
    if (response.data.status === 'ready' && response.data.run_id && response.data.snapshot_id) {
      const artifactResponse = await getAnalysisArtifact(response.data.run_id, PROPAGATION_ANALYSIS_ARTIFACT_KEY)
      if (requestGeneration !== semanticRequestGeneration || requestedEventId !== eventId.value.trim()) return
      if (isVerifiedLinkedPropagationArtifact(response.data, artifactResponse.data)) {
        linkedPropagationArtifact.value = artifactResponse.data
      }
    }
  } catch {
    if (requestGeneration !== semanticRequestGeneration || requestedEventId !== eventId.value.trim()) return
    semanticProjection.value = null
    linkedPropagationArtifact.value = null
  } finally {
    if (requestGeneration === semanticRequestGeneration && requestedEventId === eventId.value.trim()) {
      semanticLoading.value = false
    }
  }
}

async function loadAnalysis(showToast = false, preservePrediction = false) {
  if (!preservePrediction) {
    predictionRequestGeneration += 1
  }
  analyzing.value = true
  try {
    const res = (await analyzeObservedPropagation(requestParams.value)) as { data: AnalysisResult }
    analysisResult.value = res.data

    if (res.data.error) {
      if (showToast) {
        message.warning(res.data.error)
      }
      return
    }

    if (!preservePrediction) {
      modelPrediction.value = null
      disposeModelTrendChart()
    }
    selectedObjectId.value = ''
    timelineFocusPostId.value = ''
    updateSyncTime()
    await renderPathTabCharts()
  } catch {
    /* handled in interceptor */
  } finally {
    analyzing.value = false
  }
}

async function handleAnalyze() {
  diffusionFullViewRequested.value = false
  diffusionNodeLimit.value = Math.min(DEFAULT_DIFFUSION_NODE_LIMIT, diffusionSliderMax.value)
  diffusionPendingNodeLimit.value = diffusionNodeLimit.value
  await Promise.all([loadAnalysis(true), loadEvidenceTimeline()])
}

function handleDiffusionLimitChange(value: number) {
  diffusionPendingNodeLimit.value = Math.max(1, Math.floor(Number(value) || DEFAULT_DIFFUSION_NODE_LIMIT))
}

async function handleDiffusionLimitCommit(value: number) {
  const nextLimit = Math.max(1, Math.floor(Number(value) || DEFAULT_DIFFUSION_NODE_LIMIT))
  diffusionPendingNodeLimit.value = nextLimit
  const shouldRequestFull = diffusionTotalNodes.value > DEFAULT_DIFFUSION_NODE_LIMIT && nextLimit >= diffusionSliderMax.value
  if (nextLimit === diffusionNodeLimit.value && shouldRequestFull === diffusionFullViewRequested.value) return
  diffusionNodeLimit.value = nextLimit
  diffusionFullViewRequested.value = shouldRequestFull
  await loadAnalysis(false, true)
}

async function showFullDiffusionGraph() {
  const fullLimit = diffusionSliderMax.value
  diffusionPendingNodeLimit.value = fullLimit
  diffusionNodeLimit.value = fullLimit
  diffusionFullViewRequested.value = true
  await loadAnalysis(false, true)
}

async function handlePredict() {
  const requestedEventId = eventId.value.trim()
  if (!requestedEventId) return
  const requestGeneration = ++predictionRequestGeneration
  const requestedPlatform = platform.value.trim()
  predicting.value = true
  activeTab.value = 'model'
  void loadEvidenceTimeline()
  try {
    let response = await predictPropagationCurrentEvent(predictionRequestParams.value)
    if (
      requestGeneration !== predictionRequestGeneration
      || requestedEventId !== eventId.value.trim()
      || requestedPlatform !== platform.value.trim()
    ) {
      return
    }
    let result = normalizePredictionResponse(response)
    if (shouldRetryPredictionWithoutPlatform(result, requestedPlatform)) {
      const retryParams = { ...predictionRequestParams.value }
      delete retryParams.platform
      response = await predictPropagationCurrentEvent(retryParams)
      if (
        requestGeneration !== predictionRequestGeneration
        || requestedEventId !== eventId.value.trim()
        || requestedPlatform !== platform.value.trim()
      ) {
        return
      }
      result = normalizePredictionResponse(response)
    }
    if (!matchesCurrentPredictionScope(result, requestedEventId, requestedPlatform)) {
      modelPrediction.value = null
      disposeModelTrendChart()
      activeTab.value = 'model'
      return
    }
    if (hasPredictionOutput(result)) {
      modelPrediction.value = result
      activeTab.value = 'model'
      scheduleModelTrendChartRender()
    } else {
      modelPrediction.value = result
      disposeModelTrendChart()
      activeTab.value = 'model'
    }
  } catch {
    if (requestGeneration !== predictionRequestGeneration) return
    modelPrediction.value = {
      status: 'model_error',
      model_status: 'unavailable',
      note: '模型推理请求失败。',
    }
    disposeModelTrendChart()
    activeTab.value = 'model'
    /* handled in interceptor */
  } finally {
    if (requestGeneration === predictionRequestGeneration) {
      predicting.value = false
    }
  }
}

async function loadCachedPrediction() {
  const requestedEventId = eventId.value.trim()
  if (!requestedEventId) return
  const requestGeneration = ++predictionRequestGeneration
  const requestedPlatform = platform.value.trim()
  try {
    const response = await getCachedPropagationPrediction(predictionRequestParams.value)
    if (
      requestGeneration !== predictionRequestGeneration
      || requestedEventId !== eventId.value.trim()
      || requestedPlatform !== platform.value.trim()
    ) return
    const result = normalizePredictionResponse(response)
    if (matchesCurrentPredictionScope(result, requestedEventId, requestedPlatform)) {
      modelPrediction.value = result
      if (hasPredictionOutput(result)) scheduleModelTrendChartRender()
    }
  } catch {
    // Cache availability is optional. The observed propagation view remains usable.
  }
}

async function loadEvidenceTimeline() {
  const requestedEventId = eventId.value.trim()
  if (!requestedEventId) return
  const requestGeneration = ++evidenceTimelineRequestGeneration
  const requestedPlatform = platform.value.trim()
  evidenceTimelineLoading.value = true
  try {
    const response = await getPropagationEventTimeline({
      event_id: requestedEventId,
      platform: requestedPlatform || undefined,
      timeline_range: timelineRange.value,
    })
    if (
      requestGeneration !== evidenceTimelineRequestGeneration
      || requestedEventId !== eventId.value.trim()
      || requestedPlatform !== platform.value.trim()
    ) return
    evidenceTimeline.value = response.data
    scheduleEvidenceTimelineRender()
  } catch {
    if (requestGeneration === evidenceTimelineRequestGeneration) {
      evidenceTimeline.value = null
      disposeEvidenceTimelineChart()
    }
  } finally {
    if (requestGeneration === evidenceTimelineRequestGeneration) {
      evidenceTimelineLoading.value = false
    }
  }
}

async function selectTimelineRange(nextRange: PropagationTimelineRange) {
  if (timelineRange.value === nextRange && evidenceTimelineReady.value) return
  timelineRange.value = nextRange
  await loadEvidenceTimeline()
}

onMounted(() => {
  syncScopeFromRoute()
  void loadAnalysis(false, true)
  void loadCachedPrediction()
  void loadEvidenceTimeline()
  void loadSemanticProjection()
  window.addEventListener('resize', resizeCharts)
})

watch(
  () => [route.query.event_id, route.query.platform],
  () => {
    syncScopeFromRoute()
    diffusionFullViewRequested.value = false
    diffusionNodeLimit.value = DEFAULT_DIFFUSION_NODE_LIMIT
    diffusionPendingNodeLimit.value = DEFAULT_DIFFUSION_NODE_LIMIT
    void loadAnalysis(false, true)
    void loadCachedPrediction()
    void loadEvidenceTimeline()
  },
)

watch([eventId, platform], () => {
  resetSemanticProjection()
  void loadSemanticProjection()
})

watch(displayLayerRows, () => {
  void renderPathTabCharts()
})

watch(diffusionSummary, () => {
  const maxLimit = diffusionSliderMax.value
  if (diffusionNodeLimit.value > maxLimit) {
    diffusionNodeLimit.value = maxLimit
  }
  diffusionPendingNodeLimit.value = diffusionNodeLimit.value
  void renderPathTabCharts()
})

watch(activeTab, () => {
  void renderActiveTabCharts()
})

watch(modelPredictionReady, (ready) => {
  if (ready && activeTab.value === 'model') {
    scheduleModelTrendChartRender()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  layerChart?.dispose()
  pathGraphChart?.dispose()
  disposeModelTrendChart()
  disposeEvidenceTimelineChart()
})
</script>

<style scoped lang="less">
.propagation-page {
  display: flex;
  flex-direction: column;
}

.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.sync-hint {
  color: #8c8c8c;
  font-size: 12px;
}

.analysis-card {
  height: 100%;
}

.section-title {
  color: #1f1f1f;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
}

.path-card {
  min-height: 520px;
}

.path-visual-layout {
  min-height: 450px;
}

.path-node-control {
  display: grid;
  grid-template-columns: auto minmax(160px, 1fr) auto auto;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(14, 165, 233, 0.14);
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.04), rgba(14, 165, 233, 0.06));
}

.path-node-control-label,
.path-node-control-count {
  color: #475569;
  font-size: 12px;
  white-space: nowrap;
}

.path-node-slider {
  min-width: 0;
}

.path-graph-shell {
  min-height: 560px;
  overflow: hidden;
  border: 1px solid rgba(14, 165, 233, 0.22);
  border-radius: 4px;
  background:
    radial-gradient(circle at 72% 70%, rgba(0, 214, 255, 0.14), transparent 24%),
    radial-gradient(circle at 20% 18%, rgba(0, 180, 120, 0.1), transparent 28%),
    linear-gradient(135deg, #111827 0%, #1f2933 45%, #151515 100%);
  box-shadow: inset 0 0 60px rgba(0, 0, 0, 0.42);
}

.path-graph {
  width: 100%;
  height: 560px;
}

.layer-card {
  min-height: 560px;
}

.layer-visual {
  display: grid;
  gap: 10px;
  margin-bottom: 12px;
}

.layer-row {
  display: grid;
  grid-template-columns: 74px 52px 1fr;
  align-items: center;
  gap: 8px;
  color: #475569;
  font-size: 12px;
}

.layer-row strong {
  color: #0891b2;
}

.layer-track {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #e5e7eb;
}

.layer-bar {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #22d3ee, #d7e51f);
}

.layer-chart {
  width: 100%;
  height: 230px;
}

.timeline-wrap {
  max-height: 540px;
  overflow-y: auto;
  padding-top: 10px;
}

.timeline-wrap :deep(.ant-timeline) {
  padding-top: 4px;
}

.timeline-head {
  margin-bottom: 2px;
}

.timeline-entry-focused {
  border-radius: 6px;
  background: rgba(250, 204, 21, 0.16);
}

.timeline-user-link,
.role-link-button,
.evidence-reference-link {
  height: auto;
  padding: 0;
}

.timeline-time {
  color: #999;
  font-size: 12px;
  margin-left: 8px;
}

.timeline-content {
  color: #666;
  margin: 0;
}

.claim-path-list {
  display: grid;
  gap: 6px;
  margin-top: 8px;
}

.claim-path-link {
  color: #1677ff;
  cursor: pointer;
  padding: 0;
  border: 0;
  background: transparent;
  line-height: 1.5;
  text-align: left;
}

.claim-path-link:hover {
  color: #0958d9;
  text-decoration: underline;
}

.chain-header {
  margin-bottom: 8px;
}

.chain-body {
  color: #595959;
  display: grid;
  gap: 6px;
}

.forecast-card {
  min-height: 110px;
}

.forecast-label {
  color: #8c8c8c;
  font-size: 12px;
  margin-bottom: 8px;
}

.forecast-value {
  font-size: 28px;
  font-weight: 700;
  color: #1f1f1f;
  line-height: 1.1;
}

.forecast-interval {
  margin-top: 10px;
  color: #595959;
  font-size: 12px;
}

.model-trend-chart {
  width: 100%;
  height: 280px;
  margin-top: 14px;
}

.evidence-timeline-card {
  min-height: 360px;
}

.evidence-timeline-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 12px;
  flex-wrap: wrap;
}

.evidence-timeline-chart {
  width: 100%;
  height: 300px;
}

.table-link-button {
  padding: 0;
}

:deep(.clickable-table-row) {
  cursor: pointer;
}

:deep(.clickable-table-row:hover) {
  background: #f0f9ff;
}

</style>
