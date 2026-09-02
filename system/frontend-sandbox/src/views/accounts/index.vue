<template>
  <div class="account-workbench">
    <a-card size="small" class="panel">
      <template #title>
        社交机器人检测
      </template>
      <template #extra>
        <a-space>
          <a-button size="small" :loading="loading" @click="loadProfiles">刷新画像</a-button>
          <a-button type="primary" size="small" :loading="detectLoading" @click="runDetection">运行检测</a-button>
        </a-space>
      </template>

      <a-alert
        v-if="!detectionSummary"
        type="info"
        show-icon
        message="点击“运行检测”后，页面会显示账户级机器人判别摘要，并按 account_id 回填到列表。"
      />

      <template v-else>
        <a-descriptions bordered size="small" :column="3" class="section">
          <a-descriptions-item label="方法">{{ detectionMethodCard.method || 'BotRHG' }}</a-descriptions-item>
          <a-descriptions-item label="运行模式">{{ detectionMethodCard.runtime_mode || '-' }}</a-descriptions-item>
          <a-descriptions-item label="账号数">{{ detectionSummary.account_count ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="高风险账号">{{ detectionSummary.bot_count ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="路由修正">{{ detectionSummary.routed_count ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="支持邻域">{{ detectionSummary.support_k ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="路由预算">{{ formatPercent(detectionSummary.routing_budget) }}</a-descriptions-item>
          <a-descriptions-item label="数据范围">
            {{ detectionScopeLabel }}
          </a-descriptions-item>
          <a-descriptions-item label="帖子数">{{ detectionSummary.post_count ?? 0 }}</a-descriptions-item>
        </a-descriptions>

        <a-alert
          v-if="detectionMethodCard.note"
          class="section"
          type="info"
          show-icon
          :message="detectionMethodCard.note"
        />
        <a-alert
          v-if="detectionSummaryMessage"
          class="section"
          type="success"
          show-icon
          :message="detectionSummaryMessage"
        />
      </template>
    </a-card>

    <a-card size="small" class="panel">
      <template #title>
        账户画像
      </template>

      <a-table
        v-if="profiles.length"
        :columns="columns"
        :dataSource="profiles"
        :loading="loading"
        rowKey="account_id"
        :pagination="{ pageSize }"
        size="middle"
        >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'account_id'">
            <a @click.prevent="openDetail(record)" href="#">{{ record.account_id }}</a>
          </template>
          <template v-if="column.key === 'detection_result'">
            <template v-if="getDetectionAccount(record)">
              <a-tag :color="predictionColor(getDetectionAccount(record)?.final_prediction)">
                {{ predictionLabel(getDetectionAccount(record)?.final_prediction) }}
              </a-tag>
              <div class="metric-note">{{ detectionProbabilityText(getDetectionAccount(record)) }}</div>
            </template>
            <span v-else class="metric-note">未运行</span>
          </template>
          <template v-if="column.key === 'automation_score'">
            <a-tag :color="scoreColor(record.automation_score)">{{ scoreLabel(record.automation_score) }}</a-tag>
          </template>
        </template>
      </a-table>

      <a-empty v-else description="暂无账号画像数据" />
    </a-card>

    <a-drawer
      v-model:open="detailOpen"
      width="980"
      :destroyOnClose="true"
      :title="detailTitle"
    >
      <a-spin :spinning="detailLoading">
        <template v-if="detail">
          <a-descriptions bordered size="small" :column="2" class="section">
            <a-descriptions-item label="账号ID">{{ detail.account_id }}</a-descriptions-item>
            <a-descriptions-item label="昵称">{{ detail.author_name || detail.account_id }}</a-descriptions-item>
            <a-descriptions-item label="平台">{{ detail.platform || '-' }}</a-descriptions-item>
            <a-descriptions-item label="发言数">{{ detail.post_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item label="自动化评分">
              <a-tag :color="scoreColor(detail.automation_score)">{{ detail.automation_score ?? 0 }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="判别状态">
              <a-tag :color="detectionTagColor">{{ detectionLabel }}</a-tag>
            </a-descriptions-item>
          </a-descriptions>

          <a-row :gutter="16" class="section">
            <a-col :span="12">
              <a-card size="small" title="判别结果" class="subpanel">
                <a-descriptions bordered size="small" :column="1">
                  <a-descriptions-item label="方法">{{ detectionMethod }}</a-descriptions-item>
                  <a-descriptions-item label="运行模式">{{ detectionMode }}</a-descriptions-item>
                  <a-descriptions-item label="最终概率">{{ formatPercent(detectorAccount.final_bot_probability) }}</a-descriptions-item>
                  <a-descriptions-item label="基线概率">{{ formatPercent(detectorAccount.base_bot_probability) }}</a-descriptions-item>
                  <a-descriptions-item label="局部可靠性">{{ formatPercent(detectorAccount.local_reliability) }}</a-descriptions-item>
                </a-descriptions>
                <a-divider />
                <div class="method-note">{{ methodNote }}</div>
              </a-card>
            </a-col>
            <a-col :span="12">
              <a-card size="small" title="相近用户" class="subpanel">
                <a-list :dataSource="similarUsers" size="small">
                  <template #renderItem="{ item }">
                    <a-list-item>
                      <a-list-item-meta :title="item.author_name || item.account_id" :description="similarUserDesc(item)" />
                    </a-list-item>
                  </template>
                </a-list>
              </a-card>
            </a-col>
          </a-row>

          <a-card size="small" title="账号发言" class="section">
            <a-list :dataSource="detail.recent_posts || []" size="small">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta :title="postTitle(item)" :description="postDesc(item)" />
                </a-list-item>
              </template>
            </a-list>
          </a-card>
        </template>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getAccountDetail, getAccountProfiles, runSocialBotDetection } from '@/api/accounts'

type AccountProfile = Record<string, any>
type DetectionAccount = Record<string, any>
type DetectionResult = {
  summary?: Record<string, any>
  accounts?: DetectionAccount[]
  method_card?: Record<string, any>
}

const loading = ref(false)
const detectLoading = ref(false)
const detailLoading = ref(false)
const profiles = ref<AccountProfile[]>([])
const detail = ref<AccountProfile | null>(null)
const detailOpen = ref(false)
const detectionResult = ref<DetectionResult | null>(null)
const pageSize = ref(10)

const columns = [
  { title: '账号ID', dataIndex: 'account_id', key: 'account_id', width: 180, ellipsis: true },
  { title: '昵称', dataIndex: 'author_name', key: 'author_name', width: 160, ellipsis: true },
  { title: '发言数', dataIndex: 'post_count', key: 'post_count', width: 90 },
  { title: '自动化评分', dataIndex: 'automation_score', key: 'automation_score', width: 120 },
  { title: '判别结果', dataIndex: 'detection_result', key: 'detection_result', width: 160 },
  { title: '活跃时段', dataIndex: 'active_hours', key: 'active_hours', width: 100 },
  { title: '最短间隔', dataIndex: 'min_interval_seconds', key: 'min_interval_seconds', width: 100 },
]

const detectionSummary = computed(() => detectionResult.value?.summary || null)
const detectionMethodCard = computed(() => detectionResult.value?.method_card || {})
const detectionAccountMap = computed(() => {
  return new Map(
    (detectionResult.value?.accounts || []).map((row) => [String(row.account_id), row]),
  )
})
const detectionSummaryMessage = computed(() => {
  if (!detectionSummary.value) return ''
  const parts = [
    `账号 ${detectionSummary.value.account_count ?? 0} 个`,
    `高风险 ${detectionSummary.value.bot_count ?? 0} 个`,
    `路由修正 ${detectionSummary.value.routed_count ?? 0} 个`,
  ]
  if (detectionSummary.value.event_id) {
    parts.push(`事件 ${detectionSummary.value.event_id}`)
  }
  if (detectionSummary.value.platform) {
    parts.push(`平台 ${detectionSummary.value.platform}`)
  }
  return parts.join(' · ')
})
const detectionScopeLabel = computed(() => {
  const eventId = detectionSummary.value?.event_id
  const platform = detectionSummary.value?.platform
  if (eventId && platform) return `${eventId} / ${platform}`
  if (eventId) return String(eventId)
  if (platform) return String(platform)
  return '全量数据'
})
const detectorAccount = computed(() => detail.value?.detection_result?.account || {})
const similarUsers = computed(() => detail.value?.similar_users || detail.value?.detection_result?.similar_users || [])
const detectionMethod = computed(() => detail.value?.detection_result?.method || detail.value?.detection?.method || 'BotRHG proxy')
const detectionMode = computed(() => detail.value?.detection_result?.method_card?.runtime_mode || 'proxy')
const methodNote = computed(() => detail.value?.detection_result?.method_card?.note || '暂无方法说明')
const detectionLabel = computed(() => {
  const label = detectorAccount.value?.final_prediction || 'human'
  return label === 'bot' ? '高风险' : '正常'
})
const detectionTagColor = computed(() => (detectorAccount.value?.final_prediction === 'bot' ? 'red' : 'green'))
const detailTitle = computed(() => `账号详情 · ${detail.value?.author_name || detail.value?.account_id || '-'}`)

async function loadProfiles() {
  loading.value = true
  try {
    const response = await getAccountProfiles()
    profiles.value = response?.data || []
  } finally {
    loading.value = false
  }
}

async function runDetection() {
  detectLoading.value = true
  try {
    const response = await runSocialBotDetection()
    detectionResult.value = response?.data || null
  } finally {
    detectLoading.value = false
  }
}

async function openDetail(record: AccountProfile) {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = record
  try {
    const response = await getAccountDetail(String(record.account_id))
    detail.value = response?.data || record
  } finally {
    detailLoading.value = false
  }
}

function getDetectionAccount(record: AccountProfile) {
  return detectionAccountMap.value.get(String(record.account_id))
}

function predictionLabel(prediction: string | undefined) {
  if (prediction === 'bot') return '高风险'
  if (prediction === 'human') return '正常'
  return '未运行'
}

function predictionColor(prediction: string | undefined) {
  if (prediction === 'bot') return 'red'
  if (prediction === 'human') return 'green'
  return 'default'
}

function scoreLabel(score: number) {
  if (Number(score) >= 60) return '高风险'
  if (Number(score) >= 30) return '可疑'
  return '正常'
}

function scoreColor(score: number) {
  if (Number(score) >= 60) return 'red'
  if (Number(score) >= 30) return 'orange'
  return 'green'
}

function formatPercent(value: unknown) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '-'
  return `${(number * 100).toFixed(1)}%`
}

function detectionProbabilityText(account: DetectionAccount | undefined) {
  if (!account) return '未运行'
  const finalProbability = formatPercent(account.final_bot_probability)
  const baseProbability = formatPercent(account.base_bot_probability)
  return `最终 ${finalProbability} · 基线 ${baseProbability}`
}

function postTitle(post: Record<string, any>) {
  return `${post.timestamp || '-'} · ${post.content || '(empty)'}`
}

function postDesc(post: Record<string, any>) {
  return `点赞 ${post.likes ?? 0} · 转发 ${post.reposts ?? 0} · 评论 ${post.comments_count ?? 0}`
}

function similarUserDesc(user: Record<string, any>) {
  return `相似度 ${formatPercent(user.similarity)} · 判别 ${user.final_prediction || '-'} · 概率 ${formatPercent(user.final_bot_probability)}`
}

onMounted(loadProfiles)
</script>

<style scoped>
.account-workbench {
  display: grid;
  gap: 16px;
}

.section {
  margin-bottom: 16px;
}

.subpanel {
  min-height: 100%;
}

.method-note {
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.6;
}

.metric-note {
  color: rgba(0, 0, 0, 0.45);
  line-height: 1.5;
  margin-top: 4px;
}
</style>
