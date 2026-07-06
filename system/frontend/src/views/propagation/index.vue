<!--
  传播监测页面
-->
<template>
  <div class="propagation-page">
    <PageHeader title="传播监测">
      <template #description>
        展示传播路径、共享对象、关键角色、证据链与时间线预测。
      </template>
    </PageHeader>

    <div class="action-bar">
      <a-space wrap>
        <a-input v-model:value="eventId" size="small" placeholder="事件 ID" style="width: 220px" allow-clear />
        <a-input v-model:value="platform" size="small" placeholder="平台，可选" style="width: 140px" allow-clear />
        <a-button type="primary" @click="handleAnalyze" :loading="analyzing">
          同步数据库传播结果
        </a-button>
        <a-button @click="handlePredict" :loading="predicting">
          运行模型预测
        </a-button>
      </a-space>
      <span v-if="lastSyncedAt" class="sync-hint">最近同步：{{ lastSyncedAt }}</span>
    </div>

    <a-tabs v-model:activeKey="activeTab" class="propagation-tabs">
      <a-tab-pane key="path" tab="传播路径">
        <a-row :gutter="16" style="margin-bottom: 16px">
          <a-col :xs="24" :xl="15">
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

          <a-col :xs="24" :xl="9">
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
          <div v-if="claimGroups.length" class="claim-groups">
            <div v-for="group in claimGroups" :key="group.type" class="claim-group">
              <div class="claim-group-title">
                <span>共享对象：{{ group.label }}</span>
                <a-tag>{{ group.items.length }} 条</a-tag>
              </div>
              <a-list :dataSource="group.items" size="small">
                <template #renderItem="{ item }">
                  <a-list-item>
                    <div class="claim-item">
                      <a-button type="link" class="claim-inline-button" @click="openClaimDetail(item)">
                        {{ item.display }}
                      </a-button>
                      <div class="claim-meta">
                        <a-tag color="blue">分享 {{ item.share_count }}</a-tag>
                        <a-tag color="purple">账户 {{ item.account_count }}</a-tag>
                        <span>首次分享 {{ formatTimestamp(item.first_share) }}</span>
                      </div>
                    </div>
                  </a-list-item>
                </template>
              </a-list>
            </div>
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
                    <span>{{ item.author_name || item.account_id }}</span>
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
                    <span>{{ item.author_name || item.account_id }}</span>
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
                <p class="timeline-head">
                  <strong>{{ item.author_name || item.author_id }}</strong>
                  <span class="timeline-time">{{ formatTimestamp(item.timestamp) }}</span>
                </p>
                <p class="timeline-content">{{ item.content }}</p>
              </a-timeline-item>
            </a-timeline>
          </div>
          <a-empty v-else description="数据库中暂无可展示的传播时间线" :image-style="{ height: '40px' }" />
        </a-card>
      </a-tab-pane>

      <a-tab-pane key="model" tab="模型预测">
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
              <a-descriptions-item label="预测置信度">{{ formatPercent(modelPrediction?.macro?.confidence_like_score) }}</a-descriptions-item>
              <a-descriptions-item label="模型名称">{{ modelPrediction?.model?.name || 'Ours' }}</a-descriptions-item>
              <a-descriptions-item label="训练来源">{{ modelPrediction?.model?.dataset || 'twitter' }}</a-descriptions-item>
            </a-descriptions>
            <div class="trend-point-list">
              <a-tag v-for="item in modelPrediction?.macro?.trend_points || []" :key="item.step" color="blue">
                第 {{ item.step }} 步：{{ item.predicted_size }}
              </a-tag>
            </div>
          </a-card>
          <a-card size="small" title="下一跳预测 Top-K" style="margin-bottom: 16px">
            <a-table
              :columns="nextHopColumns"
              :data-source="modelPrediction?.micro?.top_users || []"
              :pagination="false"
              size="small"
              rowKey="author_id"
            />
          </a-card>
        </template>
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
        <div class="section-title">匹配时间线</div>
        <a-list v-if="claimTimelineMatches.length" :dataSource="claimTimelineMatches" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <div>
                <strong>{{ item.author_name || item.author_id }}</strong>
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
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { analyzePropagation, predictPropagationEventModel } from '@/api/propagation'
import PageHeader from '@/components/PageHeader.vue'

const DEFAULT_EVENT_ID = 'trump_visit_2026_05_21'

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
  path_id?: string
  metadata?: Record<string, unknown>
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
  object_id?: string
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

type ModelTrendPoint = {
  step: number | string
  predicted_size: number
}

type NextHopUser = {
  rank: number
  author_id: string
  author_name?: string
  score?: number
  candidate_source?: string
}

type EventModelPrediction = {
  status?: string
  model_status?: string
  macro?: {
    observed_size?: number
    predicted_size?: number
    trend_points?: ModelTrendPoint[]
    direction?: string
    confidence_like_score?: number
  }
  micro?: {
    top_users?: NextHopUser[]
    rollout_steps?: number
    candidate_count?: number
  }
  model?: {
    name?: string
    dataset?: string
    checkpoint?: string
    methodology?: string
  }
  event_id?: string
  platform?: string
  data_scope?: Record<string, unknown>
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

const analyzing = ref(false)
const predicting = ref(false)
const analysisResult = ref<AnalysisResult | null>(null)
const modelPrediction = ref<EventModelPrediction | null>(null)
const selectedClaim = ref<ClaimGroupItem | null>(null)
const claimDetailOpen = ref(false)
const selectedClaimPathDetail = ref<ClaimPathDetail | null>(null)
const claimPathDetailOpen = ref(false)
const selectedNodeDetail = ref<DiffusionNodeDetail | null>(null)
const nodeDetailOpen = ref(false)
const lastSyncedAt = ref('')
const eventId = ref(DEFAULT_EVENT_ID)
const platform = ref('')
const activeTab = ref('path')
const DEFAULT_DIFFUSION_NODE_LIMIT = 300
const diffusionNodeLimit = ref(DEFAULT_DIFFUSION_NODE_LIMIT)
const diffusionPendingNodeLimit = ref(DEFAULT_DIFFUSION_NODE_LIMIT)
const diffusionFullViewRequested = ref(false)
const route = useRoute()
const layerChartRef = ref<HTMLDivElement | null>(null)
const pathGraphRef = ref<HTMLDivElement | null>(null)
let layerChart: echarts.ECharts | null = null
let pathGraphChart: echarts.ECharts | null = null

const analysisReady = computed(() => !!analysisResult.value && !analysisResult.value.error)
const keyRoles = computed(() => analysisResult.value?.key_roles ?? null)
const claims = computed(() => analysisResult.value?.claims ?? [])
const timeline = computed(() => analysisResult.value?.timeline ?? [])
const evidenceChains = computed(() => analysisResult.value?.evidence_chains ?? [])
const pathAnalysis = computed(() => analysisResult.value?.path_analysis ?? null)
const diffusionSummary = computed(() => {
  const serverSummary = analysisResult.value?.diffusion_summary
  if (serverSummary?.visible_nodes?.length) {
    return serverSummary
  }
  return buildClientDiffusionSummary(analysisResult.value)
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
const diffusionSliderMin = computed(() => Math.min(DEFAULT_DIFFUSION_NODE_LIMIT, diffusionSliderMax.value))
const diffusionSliderMax = computed(() => Math.max(diffusionTotalNodes.value, DEFAULT_DIFFUSION_NODE_LIMIT))
const diffusionSliderStep = computed(() => (diffusionSliderMax.value > 1000 ? 50 : 10))
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
  return Array.from(groups.values()).sort((left, right) => {
    const order = ['tweet', 'url', 'hashtag', 'keyword', 'other']
    return order.indexOf(left.type) - order.indexOf(right.type)
  })
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
  const objectEvidence = (diffusionSummary.value?.detail_index?.objects?.[selectedClaim.value.object_id] as any)?.evidence
  if (objectEvidence?.claim_id) {
    return [objectEvidence as EvidenceChain]
  }
  return evidenceChains.value
    .filter((item) => item.claim_id === selectedClaim.value?.object_id)
    .slice(0, 10)
})
const requestParams = computed(() => {
  const params: { event_id?: string; platform?: string; node_limit?: number } = {}
  const event = eventId.value.trim()
  const currentPlatform = platform.value.trim()
  if (event) {
    params.event_id = event
  }
  if (currentPlatform) {
    params.platform = currentPlatform
  }
  params.node_limit = diffusionFullViewRequested.value ? 0 : diffusionNodeLimit.value
  return params
})

const modelPredictionReady = computed(() => {
  const result = modelPrediction.value
  return result?.status === 'ok' && result?.model_status === 'available'
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
      extra: `训练来源：${modelPrediction.value?.model?.dataset || 'twitter'}`,
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
    customRender: ({ record }: { record: NextHopUser }) => record.author_name || record.author_id || '--',
  },
  {
    title: '用户 ID',
    dataIndex: 'author_id',
  },
  {
    title: '预测分数',
    dataIndex: 'score',
    customRender: ({ record }: { record: NextHopUser }) => formatScore(record.score),
  },
  {
    title: '候选来源',
    dataIndex: 'candidate_source',
    customRender: ({ record }: { record: NextHopUser }) => candidateSourceLabel(record.candidate_source),
  },
])

function formatPercent(value?: number) {
  if (value == null || Number.isNaN(value)) {
    return '--'
  }
  return `${Math.round(value * 100)}%`
}

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
    observed_event: '当前事件用户',
    observed_post: '当前事件帖子用户',
    observed_comment: '当前事件评论用户',
    comment_interaction: '评论互动邻居',
    shared_object: '同共享对象参与者',
  }
  return labels[value || ''] || value || '--'
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

function shortNodeLabel(value: string) {
  const text = String(value || '').trim()
  if (!text) return '--'
  return text.length > 10 ? `${text.slice(0, 10)}…` : text
}

function stableHash(value: string) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(index)) | 0
  }
  return Math.abs(hash)
}

function layeredEdgeCurveness(source: string, target: string, sourceLayer: number, targetLayer: number) {
  const layerGap = Math.max(1, Math.abs(targetLayer - sourceLayer))
  const direction = stableHash(`${source}->${target}`) % 2 === 0 ? 1 : -1
  return direction * Math.min(0.28, 0.1 + layerGap * 0.055)
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

function buildClientDiffusionSummary(result?: AnalysisResult | null): DiffusionSummary | null {
  const graphNodes = result?.graph?.nodes ?? []
  const graphEdges = result?.graph?.edges ?? []
  if (!graphNodes.length && !graphEdges.length) return null

  const nodeIds = new Set<string>()
  const nodeMeta = new Map<string, GraphNode>()
  for (const node of graphNodes) {
    const id = String(node.id || '').trim()
    if (!id) continue
    nodeIds.add(id)
    nodeMeta.set(id, node)
  }

  const outDegree = new Map<string, number>()
  const inDegree = new Map<string, number>()
  const children = new Map<string, string[]>()
  const edgeWeight = new Map<string, number>()
  for (const edge of graphEdges) {
    const source = String(edge.source || '').trim()
    const target = String(edge.target || '').trim()
    if (!source || !target || source === target) continue
    nodeIds.add(source)
    nodeIds.add(target)
    outDegree.set(source, (outDegree.get(source) || 0) + 1)
    inDegree.set(target, (inDegree.get(target) || 0) + 1)
    if (!children.has(source)) children.set(source, [])
    children.get(source)?.push(target)
    const key = `${source}->${target}`
    edgeWeight.set(key, (edgeWeight.get(key) || 0) + Number(edge.weight ?? 1))
  }

  if (!nodeIds.size) return null

  const keyNodeSet = new Set<string>()
  const keyEdgeSet = new Set<string>()
  for (const path of result?.path_analysis?.key_paths ?? []) {
    const nodes = path.nodes ?? []
    nodes.forEach((node) => keyNodeSet.add(String(node)))
    for (let index = 0; index < nodes.length - 1; index += 1) {
      keyEdgeSet.add(`${nodes[index]}->${nodes[index + 1]}`)
    }
  }

  const hasObservedPost = (id: string) => {
    const meta = nodeMeta.get(id)
    if (!meta) return false
    return Number(meta.post_count ?? 0) > 0 || timeline.value.some((item) => item.author_id === id)
  }

  const scoreNode = (id: string) => {
    const postCount = Number(nodeMeta.get(id)?.post_count ?? 0)
    return (outDegree.get(id) || 0) * 8 - (inDegree.get(id) || 0) * 2 + Math.log1p(postCount) * 4 + (keyNodeSet.has(id) ? 200 : 0)
  }

  const rootCandidates = Array.from(nodeIds).filter((id) => (inDegree.get(id) || 0) === 0 && (outDegree.get(id) || 0) > 0)
  const observedRootCandidates = rootCandidates.filter(hasObservedPost)
  const observedCandidates = Array.from(nodeIds).filter(hasObservedPost)
  const rootId = (observedRootCandidates.length ? observedRootCandidates : observedCandidates.length ? observedCandidates : rootCandidates.length ? rootCandidates : Array.from(nodeIds))
    .sort((left, right) => scoreNode(right) - scoreNode(left))[0]

  const visible = new Set<string>()
  const layers = new Map<string, number>()
  const treeEdges: DiffusionEdge[] = []
  const maxVisible = 300
  const budgets = [48, 28, 18, 10, 6, 4]
  const keepNode = (id: string, layer: number) => {
    if (!id || visible.has(id)) return true
    if (visible.size >= maxVisible && !keyNodeSet.has(id) && id !== rootId) return false
    visible.add(id)
    layers.set(id, Math.min(layer, layers.get(id) ?? layer))
    return true
  }

  keepNode(rootId, 0)
  const queue: Array<{ id: string; layer: number }> = [{ id: rootId, layer: 0 }]
  while (queue.length) {
    const current = queue.shift()
    if (!current || current.layer >= 6) continue
    const nextNodes = Array.from(new Set(children.get(current.id) ?? []))
      .filter((id) => !visible.has(id))
      .sort((left, right) => scoreNode(right) - scoreNode(left))
      .slice(0, budgets[current.layer] ?? 2)
    for (const child of nextNodes) {
      const nextLayer = current.layer + 1
      if (!keepNode(child, nextLayer)) continue
      treeEdges.push({
        source: current.id,
        target: child,
        weight: edgeWeight.get(`${current.id}->${child}`) || 1,
        type: 'summary',
      })
      queue.push({ id: child, layer: nextLayer })
    }
  }

  for (const path of result?.path_analysis?.key_paths?.slice(0, 4) ?? []) {
    const nodes = path.nodes ?? []
    nodes.forEach((node, index) => {
      const id = String(node)
      if (!visible.has(id) && visible.size < maxVisible) {
        keepNode(id, id === rootId ? 0 : Math.min(index + 1, 6))
      }
      const next = nodes[index + 1]
      if (next && visible.has(id) && visible.has(String(next))) {
        const key = `${id}->${next}`
        if (!treeEdges.some((edge) => `${edge.source}->${edge.target}` === key)) {
          treeEdges.push({
            source: id,
            target: String(next),
            weight: edgeWeight.get(key) || 1,
            type: 'key_path',
          })
        }
      }
    })
  }

  const visibleNodes: DiffusionNode[] = Array.from(visible)
    .sort((left, right) => (layers.get(left) ?? 99) - (layers.get(right) ?? 99) || scoreNode(right) - scoreNode(left))
    .map((id) => ({
      id,
      author_name: nodeMeta.get(id)?.author_name || displayUserName(id),
      layer: layers.get(id) ?? 0,
      post_count: Number(nodeMeta.get(id)?.post_count ?? 1),
      out_degree: outDegree.get(id) || 0,
      in_degree: inDegree.get(id) || 0,
      is_root: id === rootId,
      is_key: keyNodeSet.has(id),
    }))

  const layerCounts = new Map<number, number>()
  visibleNodes.forEach((node) => layerCounts.set(node.layer, (layerCounts.get(node.layer) || 0) + 1))
  const layerRows = Array.from(layerCounts.entries())
    .sort(([left], [right]) => left - right)
    .map(([level, count]) => ({
      level,
      label: level === 0 ? '源头层' : `第${level}层`,
      node_count: count,
      ratio: count / Math.max(nodeIds.size, 1),
    }))

  const highlightEdges: DiffusionEdge[] = Array.from(keyEdgeSet)
    .map((key) => {
      const [source, target] = key.split('->')
      return { source, target, weight: edgeWeight.get(key) || 1, type: 'key_path', is_key_path: true }
    })
    .filter((edge) => visible.has(edge.source) && visible.has(edge.target))

  const detailNodes: Record<string, DiffusionNodeDetail> = {}
  for (const node of visibleNodes) {
    detailNodes[node.id] = {
      id: node.id,
      author_name: node.author_name,
      post_count: node.post_count,
      out_degree: node.out_degree,
      in_degree: node.in_degree,
      upstream: graphEdges
        .filter((edge) => String(edge.target) === node.id)
        .slice(0, 12)
        .map((edge) => ({ id: String(edge.source), author_name: displayUserName(String(edge.source)) })),
      downstream: (children.get(node.id) ?? [])
        .slice(0, 12)
        .map((id) => ({ id, author_name: displayUserName(id) })),
      posts: timeline.value
        .filter((item) => item.author_id === node.id)
        .slice(0, 20)
        .map((item) => ({ ...item })),
      key_paths: (result?.path_analysis?.key_paths ?? [])
        .filter((path) => path.nodes?.includes(node.id))
        .map((path) => ({
          claim_id: path.claim_id,
          nodes: path.nodes,
          score: path.score,
          explanation: path.explanation,
        })),
    }
  }

  return {
    root_node: visibleNodes.find((node) => node.id === rootId) ?? null,
    parallel_roots: [],
    visible_nodes: visibleNodes,
    tree_edges: treeEdges.filter((edge) => visible.has(edge.source) && visible.has(edge.target)),
    highlight_edges: highlightEdges,
    layers: layerRows,
    detail_index: {
      nodes: detailNodes,
      objects: {},
    },
    meta: {
      mode: 'client_fallback_layered_summary',
      source: 'graph_edges',
      total_nodes: nodeIds.size,
      visible_node_count: visibleNodes.length,
    },
  }
}

function buildPathGraphOption(summary?: DiffusionSummary | null): EChartsOption {
  const nodes = summary?.visible_nodes ?? []
  const treeEdges = summary?.tree_edges ?? []
  const highlightEdges = summary?.highlight_edges ?? []
  const nodeById = new Map(nodes.map((node) => [String(node.id), node]))
  const rootId = String(summary?.root_node?.id || nodes.find((node) => node.is_root)?.id || nodes[0]?.id || '')
  const keyEdgeKeys = new Set(highlightEdges.map((edge) => `${edge.source}->${edge.target}`))

  const nodesByLayer = new Map<number, DiffusionNode[]>()
  for (const node of nodes) {
    const layer = Math.max(0, Number(node.layer ?? 0))
    if (!nodesByLayer.has(layer)) nodesByLayer.set(layer, [])
    nodesByLayer.get(layer)?.push(node)
  }

  const positions = new Map<string, { x: number; y: number; layer: number }>()
  const radialGap = 95
  positions.set(rootId, { x: 0, y: 0, layer: 0 })

  const hasBackendLayout = nodes.some((node) => Number.isFinite(Number(node.layout_x)) && Number.isFinite(Number(node.layout_y)))
  if (hasBackendLayout) {
    for (const node of nodes) {
      const id = String(node.id)
      if (Number.isFinite(Number(node.layout_x)) && Number.isFinite(Number(node.layout_y))) {
        positions.set(id, {
          x: Number(node.layout_x),
          y: Number(node.layout_y),
          layer: Number(node.layer ?? 0),
        })
      }
    }
  } else {
    for (const [layer, layerNodes] of nodesByLayer.entries()) {
      if (layer === 0) continue
      const ringNodes = layerNodes
        .filter((node) => String(node.id) !== rootId)
        .sort((left, right) => {
          const leftScore = Number(left.out_degree ?? 0) + Number(left.post_count ?? 0) + (left.is_key ? 100 : 0)
          const rightScore = Number(right.out_degree ?? 0) + Number(right.post_count ?? 0) + (right.is_key ? 100 : 0)
          return rightScore - leftScore
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
  }

  const graphData = nodes.map((node) => {
    const id = String(node.id)
    const position = positions.get(id) || { x: 0, y: 0, layer: Number(node.layer ?? 0) }
    const isRoot = id === rootId || Boolean(node.is_root)
    const isKey = Boolean(node.is_key)
    const value = Math.max(1, Number(node.post_count ?? 1))
    return {
      id,
      name: id,
      userId: id,
      x: position.x,
      y: position.y,
      value,
      category: isRoot ? 0 : isKey ? 1 : 2,
      symbolSize: isRoot ? 26 : isKey ? 8 : Math.max(2.6, Math.min(5.4, Math.sqrt(value) * 1.1 + 1.8)),
      label: {
        show: true,
        formatter: shortNodeLabel(node.author_name || displayUserName(id)),
      },
      itemStyle: {
        opacity: isRoot || isKey ? 1 : 0.72,
      },
    }
  })

  const mergedEdges = new Map<string, DiffusionEdge>()
  for (const edge of treeEdges) {
    mergedEdges.set(`${edge.source}->${edge.target}`, edge)
  }
  for (const edge of highlightEdges) {
    const key = `${edge.source}->${edge.target}`
    const existingEdge = mergedEdges.get(key)
    if (existingEdge) {
      mergedEdges.set(key, { ...existingEdge, is_key_path: true })
    }
  }

  const graphLinks = Array.from(mergedEdges.values())
    .filter((edge) => {
      const source = String(edge.source)
      const target = String(edge.target)
      if (!source || !target || source === target || !nodeById.has(source) || !nodeById.has(target)) return false
      const sourceLayer = Number(nodeById.get(source)?.layer ?? -1)
      const targetLayer = Number(nodeById.get(target)?.layer ?? -1)
      return sourceLayer !== targetLayer
    })
    .map((edge) => {
      const source = String(edge.source)
      const target = String(edge.target)
      const highlighted = Boolean(edge.is_key_path) || keyEdgeKeys.has(`${source}->${target}`)
      const sourceLayer = Number(nodeById.get(source)?.layer ?? 0)
      const targetLayer = Number(nodeById.get(target)?.layer ?? sourceLayer + 1)
      return {
        source,
        target,
        value: Number(edge.weight ?? 1) || 1,
        lineStyle: {
          color: highlighted ? 'rgba(56, 189, 248, 0.72)' : 'rgba(96, 165, 250, 0.3)',
          width: highlighted ? 1.35 : 0.72,
          curveness: layeredEdgeCurveness(source, target, sourceLayer, targetLayer),
          opacity: highlighted ? 0.62 : 0.28,
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
        if (params.dataType === 'edge') {
          return `${displayUserName(params.data.source)}<br/>→ ${displayUserName(params.data.target)}`
        }
        const node = nodeById.get(String(params.data.userId))
        const degreeText = `出度：${node?.out_degree ?? 0} / 入度：${node?.in_degree ?? 0}`
        return `${displayUserName(params.data.userId)}<br/>用户ID：${params.data.userId}<br/>${degreeText}`
      },
    },
    legend: {
      top: 8,
      right: 12,
      textStyle: { color: '#dbeafe' },
      data: ['源头', '关键节点', '普通节点'],
    },
    series: [
      {
        type: 'graph',
        layout: 'none',
        roam: true,
        zoom: 1.15,
        center: [0, 0],
        draggable: true,
        top: 42,
        bottom: 14,
        left: 12,
        right: 12,
        categories: [
          { name: '源头', itemStyle: { color: '#facc15' } },
          { name: '关键节点', itemStyle: { color: '#00d9ff' } },
          { name: '普通节点', itemStyle: { color: '#60a5fa' } },
        ],
        data: graphData,
        links: graphLinks,
        label: {
          color: '#eef6ff',
          fontSize: 10,
          position: 'right',
        },
        labelLayout: {
          hideOverlap: true,
        },
        edgeSymbol: ['none', 'none'],
        edgeSymbolSize: [0, 0],
        lineStyle: {
          color: 'source',
          opacity: 0.18,
          curveness: 0.16,
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: {
            width: 4,
          },
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

function resizeCharts() {
  layerChart?.resize()
  pathGraphChart?.resize()
}

async function renderPathTabCharts() {
  if (activeTab.value !== 'path') return
  await Promise.all([renderLayerChart(), renderPathGraph()])
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

function openClaimDetail(item: ClaimGroupItem) {
  selectedClaim.value = item
  claimDetailOpen.value = true
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
  eventId.value = firstQueryValue(route.query.event_id) || DEFAULT_EVENT_ID
  platform.value = firstQueryValue(route.query.platform)
}

async function loadAnalysis(showToast = false) {
  analyzing.value = true
  try {
    const res = (await analyzePropagation(requestParams.value)) as { data: AnalysisResult }
    analysisResult.value = res.data

    if (res.data.error) {
      if (showToast) {
        message.warning(res.data.error)
      }
      return
    }

    modelPrediction.value = null
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
  await loadAnalysis(true)
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
  await loadAnalysis(false)
}

async function showFullDiffusionGraph() {
  const fullLimit = diffusionSliderMax.value
  diffusionPendingNodeLimit.value = fullLimit
  diffusionNodeLimit.value = fullLimit
  diffusionFullViewRequested.value = true
  await loadAnalysis(false)
}

async function handlePredict() {
  predicting.value = true
  try {
    const res = (await predictPropagationEventModel({ ...requestParams.value, top_k: 10 })) as { data: EventModelPrediction }
    const result = res.data
    if (result?.status === 'ok' && result?.model_status === 'available') {
      modelPrediction.value = result
      activeTab.value = 'model'
    } else {
      modelPrediction.value = null
    }
  } catch {
    modelPrediction.value = null
    /* handled in interceptor */
  } finally {
    predicting.value = false
  }
}

onMounted(() => {
  syncScopeFromRoute()
  void loadAnalysis(false)
  window.addEventListener('resize', resizeCharts)
})

watch(
  () => [route.query.event_id, route.query.platform],
  () => {
    syncScopeFromRoute()
    diffusionFullViewRequested.value = false
    diffusionNodeLimit.value = DEFAULT_DIFFUSION_NODE_LIMIT
    diffusionPendingNodeLimit.value = DEFAULT_DIFFUSION_NODE_LIMIT
    void loadAnalysis(false)
  },
)

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
  void renderPathTabCharts()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  layerChart?.dispose()
  pathGraphChart?.dispose()
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
  min-height: 450px;
  overflow: hidden;
  border: 1px solid rgba(14, 165, 233, 0.18);
  border-radius: 10px;
  background:
    radial-gradient(circle at 48% 58%, rgba(245, 184, 0, 0.13), transparent 22%),
    radial-gradient(circle at 22% 18%, rgba(34, 211, 238, 0.11), transparent 30%),
    linear-gradient(135deg, #171717 0%, #0d1117 46%, #020617 100%);
}

.path-graph {
  width: 100%;
  height: 450px;
}

.layer-card {
  min-height: 430px;
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

</style>
