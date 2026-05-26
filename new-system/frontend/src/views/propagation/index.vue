<!--
  传播监控页面
-->
<template>
  <div class="propagation-page">
    <PageHeader title="传播监控">
      <template #description>
        页面优先同步数据库中的传播分析结果，当前先展示高频共享对象、传播时间线、关键角色和证据链摘要；
        趋势预测保留为按需触发的补充能力。
      </template>
    </PageHeader>

    <div class="action-bar">
      <a-space wrap>
        <a-button type="primary" @click="handleAnalyze" :loading="analyzing">
          同步数据库传播结果
        </a-button>
        <a-button @click="handlePredict" :loading="predicting">
          运行趋势预测
        </a-button>
      </a-space>
      <span v-if="lastSyncedAt" class="sync-hint">最近同步：{{ lastSyncedAt }}</span>
    </div>

    <a-alert
      v-if="analysisMessage"
      :message="analysisMessage"
      type="info"
      show-icon
      style="margin-bottom: 16px"
    />

    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :xs="24" :sm="12" :xl="6">
        <a-card size="small" :loading="analyzing && !analysisReady">
          <a-statistic title="帖子数量" :value="activeScope?.posts ?? 0" />
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :xl="6">
        <a-card size="small" :loading="analyzing && !analysisReady">
          <a-statistic title="评论数量" :value="activeScope?.comments ?? 0" />
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :xl="6">
        <a-card size="small" :loading="analyzing && !analysisReady">
          <a-statistic title="高频共享对象" :value="claims.length" suffix="个" />
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :xl="6">
        <a-card size="small" :loading="analyzing && !analysisReady">
          <a-statistic title="传播时间线记录" :value="timeline.length" suffix="条" />
        </a-card>
      </a-col>
    </a-row>

    <a-card size="small" style="margin-bottom: 16px" :loading="analyzing && !analysisReady">
      <template #title>高频共享对象</template>
      <template #extra v-if="claims.length > 0">
        <TableSettings v-model:size="tableSize" v-model:pageSize="pageSize" />
      </template>
      <a-table
        v-if="claims.length > 0"
        :columns="claimColumns"
        :dataSource="claims"
        rowKey="object_id"
        :size="tableSize"
        :pagination="{ pageSize }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'first_share'">
            {{ formatTimestamp(record.first_share) }}
          </template>
        </template>
      </a-table>
      <a-empty v-else description="数据库中暂无可展示的高频共享对象" :image-style="{ height: '40px' }" />
    </a-card>

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

    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :xs="24" :lg="8">
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
      <a-col :xs="24" :lg="8">
        <a-card size="small" title="桥接节点" :loading="analyzing && !analysisReady">
          <a-list v-if="keyRoles?.bridges?.length" :dataSource="keyRoles.bridges" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <span>{{ item.author_name || item.account_id }}</span>
                <template #actions><a-tag color="orange">介数 {{ item.betweenness }}</a-tag></template>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else description="暂无桥接节点结果" :image-style="{ height: '30px' }" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="8">
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

    <a-card size="small" title="趋势预测结果" :loading="predicting" v-if="trendResult">
      <a-alert
        type="info"
        show-icon
        :message="trendResult.explanation"
        style="margin-bottom: 16px"
      />
      <a-row :gutter="12" style="margin-bottom: 16px">
        <a-col v-for="item in forecastCards" :key="item.horizon" :xs="24" :sm="8">
          <a-card size="small" class="forecast-card">
            <div class="forecast-label">{{ item.label }}</div>
            <div class="forecast-value">{{ item.value }}</div>
            <div class="forecast-interval">区间 {{ item.interval }}</div>
          </a-card>
        </a-col>
      </a-row>
      <a-descriptions size="small" :column="2" bordered>
        <a-descriptions-item label="趋势方向">{{ directionLabel }}</a-descriptions-item>
        <a-descriptions-item label="主导阶段">{{ dominantRegimeLabel }}</a-descriptions-item>
        <a-descriptions-item label="预测置信度">{{ formatPercent(trendResult.confidence) }}</a-descriptions-item>
        <a-descriptions-item label="LLM 状态">{{ trendResult.llm_available ? '可用' : 'Mock / 降级' }}</a-descriptions-item>
      </a-descriptions>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { analyzePropagation, predictPropagationTrend } from '@/api/propagation'
import TableSettings from '@/components/TableSettings.vue'
import PageHeader from '@/components/PageHeader.vue'

type ScopeData = {
  posts?: number
  comments?: number
}

type KeyRoleItem = {
  account_id: string
  author_name?: string
  out_degree?: number
  in_degree?: number
  betweenness?: number
}

type EvidencePath = {
  explanation?: string
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

type TimelineItem = {
  post_id: string
  author_id: string
  author_name: string
  timestamp: string
  content: string
}

type AnalysisResult = {
  graph?: {
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
  data_scope?: ScopeData
  error?: string
}

type TrendResult = {
  volume_forecast: Record<string, number>
  confidence_interval: Record<string, [number, number]>
  direction: 'rising' | 'stable' | 'declining'
  regime_posterior: Record<string, number>
  confidence: number
  explanation: string
  llm_available: boolean
  error?: string
}

const regimeLabelMap: Record<string, string> = {
  seeding: '播种阶段',
  amplification: '扩散阶段',
  peak: '峰值阶段',
  decay: '衰退阶段',
}

const directionMap: Record<string, string> = {
  rising: '上升',
  stable: '稳定',
  declining: '下降',
}

const claimColumns = [
  { title: '共享对象', dataIndex: 'object_id', key: 'object_id', ellipsis: true },
  { title: '分享次数', dataIndex: 'share_count', key: 'share_count', sorter: (a: ClaimItem, b: ClaimItem) => a.share_count - b.share_count },
  { title: '涉及账户', dataIndex: 'account_count', key: 'account_count' },
  { title: '首次分享', dataIndex: 'first_share', key: 'first_share' },
]

const analyzing = ref(false)
const predicting = ref(false)
const tableSize = ref<'small' | 'middle' | 'default'>('middle')
const pageSize = ref(10)
const analysisResult = ref<AnalysisResult | null>(null)
const trendResult = ref<TrendResult | null>(null)
const analysisMessage = ref('')
const lastSyncedAt = ref('')

const analysisReady = computed(() => !!analysisResult.value && !analysisResult.value.error)
const activeScope = computed(() => analysisResult.value?.data_scope ?? null)
const keyRoles = computed(() => analysisResult.value?.key_roles ?? null)
const claims = computed(() => analysisResult.value?.claims ?? [])
const timeline = computed(() => analysisResult.value?.timeline ?? [])
const evidenceChains = computed(() => analysisResult.value?.evidence_chains ?? [])

const forecastCards = computed(() => {
  if (!trendResult.value) {
    return []
  }

  return ['1h', '6h', '24h'].map((horizon) => {
    const interval = trendResult.value?.confidence_interval[horizon]
    return {
      horizon,
      label: `${horizon} 预测`,
      value: trendResult.value?.volume_forecast[horizon] ?? 0,
      interval: interval ? `${interval[0]} - ${interval[1]}` : '--',
    }
  })
})

const dominantRegimeLabel = computed(() => {
  if (!trendResult.value) {
    return '--'
  }
  const [key] = Object.entries(trendResult.value.regime_posterior).sort(([, left], [, right]) => right - left)[0] ?? []
  return regimeLabelMap[key] ?? '--'
})

const directionLabel = computed(() => directionMap[trendResult.value?.direction ?? ''] ?? '--')

function formatPercent(value?: number) {
  if (value == null || Number.isNaN(value)) {
    return '--'
  }
  return `${Math.round(value * 100)}%`
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

async function loadAnalysis(showToast = false) {
  analyzing.value = true
  try {
    const res = (await analyzePropagation()) as { data: AnalysisResult }
    analysisResult.value = res.data

    if (res.data.error) {
      analysisMessage.value = res.data.error
      if (showToast) {
        message.warning(res.data.error)
      }
      return
    }

    analysisMessage.value = '已优先同步数据库中的高频共享对象、传播时间线、关键角色和证据链摘要。'
    updateSyncTime()
    if (showToast) {
      message.success('数据库传播结果同步完成。')
    }
  } catch {
    /* handled in interceptor */
  } finally {
    analyzing.value = false
  }
}

async function handleAnalyze() {
  await loadAnalysis(true)
}

async function handlePredict() {
  predicting.value = true
  try {
    const res = (await predictPropagationTrend()) as { data: TrendResult }
    if (res.data.error) {
      message.warning(res.data.error)
      return
    }
    trendResult.value = res.data
    message.success('趋势预测完成。')
  } catch {
    /* handled in interceptor */
  } finally {
    predicting.value = false
  }
}

onMounted(() => {
  void loadAnalysis(false)
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

.timeline-wrap {
  max-height: 540px;
  overflow-y: auto;
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
