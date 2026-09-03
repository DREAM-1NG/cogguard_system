<template>
  <div class="account-workbench">
    <a-card size="small" class="panel">
      <template #title>
        BotRHG 账号判别
      </template>
      <template #extra>
        <a-space>
          <a-button size="small" :loading="loading" @click="loadProfiles">刷新画像</a-button>
          <a-button type="primary" size="small" :loading="detectLoading" @click="runDetection">运行 / 刷新 BotRHG</a-button>
        </a-space>
      </template>

      <div class="botrhg-toolbar-note">
        结果直接回填到下方画像表：算法判别、最终概率、基线概率与路由修正状态。
      </div>
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
          <template v-else-if="column.key === 'botrhg_prediction'">
            <template v-if="getDetectionAccount(record)">
              <a-tag :color="predictionColor(getDetectionAccount(record)?.final_prediction)">
                {{ predictionLabel(getDetectionAccount(record)?.final_prediction) }}
              </a-tag>
            </template>
            <span v-else class="metric-note">未运行</span>
          </template>
          <template v-else-if="column.key === 'botrhg_probability'">
            <span v-if="getDetectionAccount(record)">{{ formatPercent(getDetectionAccount(record)?.final_bot_probability) }}</span>
            <span v-else class="metric-note">-</span>
          </template>
          <template v-else-if="column.key === 'botrhg_base_probability'">
            <span v-if="getDetectionAccount(record)">{{ formatPercent(getDetectionAccount(record)?.base_bot_probability) }}</span>
            <span v-else class="metric-note">-</span>
          </template>
          <template v-else-if="column.key === 'botrhg_routed'">
            <a-tag v-if="getDetectionAccount(record)" :color="getDetectionAccount(record)?.routed ? 'blue' : 'default'">
              {{ getDetectionAccount(record)?.routed ? '已修正' : '未路由' }}
            </a-tag>
            <span v-else class="metric-note">-</span>
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
            <a-descriptions-item label="算法判别">
              <a-tag :color="detectionTagColor">{{ detectionLabel }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="BotRHG 最终概率">
              {{ formatPercent(detectorAccount.final_bot_probability) }}
            </a-descriptions-item>
          </a-descriptions>

          <a-row :gutter="16" class="section">
            <a-col :span="12">
              <a-card size="small" title="BotRHG 判别结果" class="subpanel">
                <a-descriptions bordered size="small" :column="1">
                  <a-descriptions-item label="方法">{{ detectionMethod }}</a-descriptions-item>
                  <a-descriptions-item label="运行模式">{{ detectionMode }}</a-descriptions-item>
                  <a-descriptions-item label="最终概率">{{ formatPercent(detectorAccount.final_bot_probability) }}</a-descriptions-item>
                  <a-descriptions-item label="基线概率">{{ formatPercent(detectorAccount.base_bot_probability) }}</a-descriptions-item>
                  <a-descriptions-item label="局部可靠性">{{ formatPercent(detectorAccount.local_reliability) }}</a-descriptions-item>
                  <a-descriptions-item label="路由修正">{{ detectorAccount.routed ? '已进入支持邻域修正' : '未路由修正' }}</a-descriptions-item>
                </a-descriptions>
              </a-card>
            </a-col>
            <a-col :span="12">
              <a-card size="small" title="支持邻域用户" class="subpanel">
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
import { getAccountDetail, getAccountProfiles, getLatestSocialBotDetection, runSocialBotDetection } from '@/api/accounts'

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
  { title: '算法判别', dataIndex: 'botrhg_prediction', key: 'botrhg_prediction', width: 120 },
  { title: 'BotRHG 最终概率', dataIndex: 'botrhg_probability', key: 'botrhg_probability', width: 140 },
  { title: 'BotRHG 基线概率', dataIndex: 'botrhg_base_probability', key: 'botrhg_base_probability', width: 140 },
  { title: '路由修正', dataIndex: 'botrhg_routed', key: 'botrhg_routed', width: 100 },
  { title: '活跃时段', dataIndex: 'active_hours', key: 'active_hours', width: 100 },
  { title: '最短间隔', dataIndex: 'min_interval_seconds', key: 'min_interval_seconds', width: 100 },
]

const detectionMethodCard = computed(() => detectionResult.value?.method_card || {})
const detectionAccountMap = computed(() => {
  return new Map(
    (detectionResult.value?.accounts || []).map((row) => [String(row.account_id), row]),
  )
})
const detectorAccount = computed(() => {
  if (!detail.value) return {}
  return getDetectionAccount(detail.value) || detail.value?.detection_result?.account || {}
})
const similarUsers = computed(() => detail.value?.similar_users || detail.value?.detection_result?.similar_users || [])
const detectionMethod = computed(() => detectionMethodCard.value?.method || detail.value?.detection_result?.method || detail.value?.detection?.method || 'BotRHG')
const detectionMode = computed(() => detectionMethodCard.value?.runtime_mode || detail.value?.detection_result?.method_card?.runtime_mode || '-')
const detectionLabel = computed(() => predictionLabel(detectorAccount.value?.final_prediction))
const detectionTagColor = computed(() => predictionColor(detectorAccount.value?.final_prediction))
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

async function loadLatestDetection() {
  try {
    const response = await getLatestSocialBotDetection()
    detectionResult.value = response?.data || null
  } catch {
    detectionResult.value = null
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
  if (prediction === 'bot') return 'Bot'
  if (prediction === 'human') return 'Human'
  return '未运行'
}

function predictionColor(prediction: string | undefined) {
  if (prediction === 'bot') return 'volcano'
  if (prediction === 'human') return 'green'
  return 'default'
}

function formatPercent(value: unknown) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '-'
  return `${(number * 100).toFixed(1)}%`
}

function postTitle(post: Record<string, any>) {
  return `${post.timestamp || '-'} · ${post.content || '(empty)'}`
}

function postDesc(post: Record<string, any>) {
  return `点赞 ${post.likes ?? 0} · 转发 ${post.reposts ?? 0} · 评论 ${post.comments_count ?? 0}`
}

function similarUserDesc(user: Record<string, any>) {
  return `相似度 ${formatPercent(user.similarity)} · 判别 ${predictionLabel(user.final_prediction)} · 概率 ${formatPercent(user.final_bot_probability)}`
}

async function loadPage() {
  await Promise.allSettled([loadProfiles(), loadLatestDetection()])
}

onMounted(loadPage)
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

.metric-note {
  color: rgba(0, 0, 0, 0.45);
  line-height: 1.5;
  margin-top: 4px;
}

.botrhg-toolbar-note {
  color: rgba(0, 0, 0, 0.55);
  font-size: 13px;
  line-height: 1.6;
}
</style>
