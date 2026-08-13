<template>
  <div class="account-workbench">
    <PageHeader title="账号画像">
      <template #description>
        汇总账号发言、BotRHG 研判结果和超图相近账号，辅助分析员定位需要复核的账号。
      </template>
    </PageHeader>

    <section class="filter-bar" aria-label="账号画像筛选">
      <a-space wrap :size="8">
        <a-input
          v-model:value="eventId"
          class="filter-input"
          size="small"
          placeholder="事件 ID，可选"
          allow-clear
        />
        <a-select
          v-model:value="platform"
          class="platform-select"
          size="small"
          placeholder="全部平台"
          allow-clear
          :options="platformOptions"
        />
        <a-button size="small" :loading="loading" @click="refreshProfiles">
          <ReloadOutlined />
          刷新画像
        </a-button>
        <a-button
          size="small"
          type="primary"
          :loading="detecting"
          @click="handleRunDetection"
        >
          <PlayCircleOutlined />
          运行检测
        </a-button>
      </a-space>
      <span v-if="lastSyncedAt" class="sync-hint">最近同步：{{ lastSyncedAt }}</span>
    </section>

    <section class="overview-grid" aria-label="账号检测摘要">
      <a-card size="small" class="overview-card">
        <template #title>检测结果</template>
        <template #extra>
          <a-tag :color="detectionStatusColor">
            {{ detectionStatusText }}
          </a-tag>
        </template>
        <div class="metric-strip">
          <div class="metric-item">
            <span>账号</span>
            <strong>{{ detectionSummary.account_count }}</strong>
          </div>
          <div class="metric-item attention">
            <span>需关注</span>
            <strong>{{ detectionSummary.bot_count }}</strong>
          </div>
          <div class="metric-item">
            <span>发言</span>
            <strong>{{ detectionSummary.post_count }}</strong>
          </div>
        </div>
        <p class="card-note">
          {{ detectionNarrative }}
        </p>
      </a-card>

      <a-card size="small" class="overview-card">
        <template #title>当前列表</template>
        <div class="metric-strip">
          <div class="metric-item">
            <span>总账号</span>
            <strong>{{ profileStats.total }}</strong>
          </div>
          <div class="metric-item attention">
            <span>需关注</span>
            <strong>{{ profileStats.attention }}</strong>
          </div>
          <div class="metric-item">
            <span>待研判</span>
            <strong>{{ profileStats.pending }}</strong>
          </div>
        </div>
        <p class="card-note">平台覆盖：{{ platformCoverage }}</p>
      </a-card>
    </section>

    <a-card size="small" class="profile-table-card">
      <template #title>账号列表</template>
      <template #extra>
        <a-space :size="8">
          <a-tag color="gold">需关注 {{ profileStats.attention }}</a-tag>
          <a-tag>待研判 {{ profileStats.pending }}</a-tag>
        </a-space>
      </template>

      <a-spin :spinning="loading">
        <a-table
          v-if="profiles.length"
          :columns="columns"
          :dataSource="profiles"
          :rowKey="profileRowKey"
          :pagination="{ pageSize, showSizeChanger: false }"
          size="middle"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'author_name'">
              <button type="button" class="link-button" @click="openDetail(record)">
                {{ displayName(record) }}
              </button>
              <div class="account-subtitle">{{ scopedAccountLabel(record) }}</div>
            </template>
            <template v-else-if="column.key === 'platform'">
              <a-tag>{{ platformLabel(record.platform) }}</a-tag>
            </template>
            <template v-else-if="column.key === 'assessment'">
              <a-tag :color="assessmentColor(record.assessment?.level)">
                {{ assessmentLabel(record.assessment?.level) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'prediction'">
              <span>{{ predictionLabel(record.assessment?.prediction) }}</span>
              <div class="account-subtitle">
                {{ record.assessment?.calibrated ? '已校准' : '未校准或暂无校准' }}
              </div>
            </template>
            <template v-else-if="column.key === 'bot_probability'">
              <div class="probability-cell">
                <span>{{ probabilityLabel(record.assessment?.bot_probability) }}</span>
                <div class="probability-track" aria-hidden="true">
                  <div
                    class="probability-fill"
                    :class="{ high: probabilityNumber(record.assessment?.bot_probability) >= 0.5 }"
                    :style="{ width: probabilityPercent(record.assessment?.bot_probability) }"
                  />
                </div>
              </div>
            </template>
            <template v-else-if="column.key === 'support_count'">
              {{ supportCount(record.assessment) }}
            </template>
            <template v-else-if="column.key === 'active_hours'">
              {{ activeHoursLabel(record.active_hours) }}
            </template>
            <template v-else-if="column.key === 'operation'">
              <a-button type="link" size="small" @click="openDetail(record)">查看</a-button>
            </template>
          </template>
        </a-table>

        <a-empty v-else-if="!loading" description="暂无账号画像数据" />
      </a-spin>
    </a-card>

    <a-drawer
      v-model:open="detailOpen"
      width="860"
      :destroyOnClose="true"
      :title="detailTitle"
    >
      <a-spin :spinning="detailLoading">
        <template v-if="detail">
          <a-descriptions bordered size="small" :column="2" class="detail-section">
            <a-descriptions-item label="昵称">{{ displayName(detail) }}</a-descriptions-item>
            <a-descriptions-item label="平台">{{ platformLabel(detail.platform) }}</a-descriptions-item>
            <a-descriptions-item label="账号 ID">{{ detail.account_id || '暂无' }}</a-descriptions-item>
            <a-descriptions-item label="发言数">{{ detail.post_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item label="活跃时段">{{ activeHoursLabel(detail.active_hours) }}</a-descriptions-item>
            <a-descriptions-item label="最短间隔">{{ intervalLabel(detail.min_interval_seconds) }}</a-descriptions-item>
            <a-descriptions-item label="研判结果">
              <a-tag :color="assessmentColor(detail.assessment?.level)">
                {{ assessmentLabel(detail.assessment?.level) }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="模型判别">
              {{ predictionLabel(detail.assessment?.prediction) }}
            </a-descriptions-item>
            <a-descriptions-item label="机器人概率">
              {{ probabilityLabel(detail.assessment?.bot_probability) }}
            </a-descriptions-item>
            <a-descriptions-item label="校准状态">
              {{ detail.assessment?.calibrated ? '已校准' : '未校准或暂无校准' }}
            </a-descriptions-item>
            <a-descriptions-item label="模型版本">
              {{ detail.assessment?.model_version || activeModel?.model_version || '暂无' }}
            </a-descriptions-item>
            <a-descriptions-item label="判别路径">
              {{ decisionPathLabel(detail.assessment) }}
            </a-descriptions-item>
          </a-descriptions>

          <a-alert
            v-if="detailAssessmentProblem"
            class="detail-section"
            type="info"
            show-icon
            :message="detailAssessmentProblem"
          />

          <section class="detail-section">
            <h3 class="section-title">超图相近账号</h3>
            <a-table
              v-if="detail.assessment?.similar_accounts?.length"
              :columns="similarColumns"
              :dataSource="detail.assessment.similar_accounts"
              rowKey="account_id"
              :pagination="false"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'similarity'">
                  {{ similarityLabel(record.similarity) }}
                </template>
                <template v-else-if="column.key === 'bot_probability'">
                  {{ probabilityLabel(record.bot_probability) }}
                </template>
                <template v-else-if="column.key === 'prediction'">
                  {{ predictionLabel(record.final_prediction) }}
                </template>
                <template v-else-if="column.key === 'routed'">
                  {{ record.routed ? '参与校正' : '未参与校正' }}
                </template>
              </template>
            </a-table>
            <a-empty
              v-else
              description="暂无相近账号"
              :image-style="{ height: '42px' }"
            />
          </section>

          <section class="detail-section">
            <h3 class="section-title">近期发言</h3>
            <a-list :dataSource="detail.recent_posts || []" size="small" class="post-list">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #title>
                      <span class="post-content">{{ postTitle(item) }}</span>
                    </template>
                    <template #description>
                      <span>{{ postDesc(item) }}</span>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
            <a-empty
              v-if="!(detail.recent_posts || []).length"
              description="暂无近期发言"
              :image-style="{ height: '42px' }"
            />
          </section>
        </template>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlayCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import {
  getAccountDetail,
  getAccountProfiles,
  getActiveAccountModel,
  runSocialBotDetection,
  type AccountModelPointerStatus,
  type AccountQueryParams,
  type BotDetectionResult,
} from '@/api/accounts'

type AccountAssessment = {
  level?: 'attention' | 'normal' | 'pending'
  label?: string
  prediction?: 'bot' | 'human' | ''
  final_prediction?: 'bot' | 'human' | ''
  bot_probability?: number | null
  calibrated?: boolean
  routed?: boolean
  model_version?: string
  pointer_revision?: number
  calibration_source?: string
  similar_accounts?: Array<{
    account_id: string
    similarity?: number | null
    bot_probability?: number | null
    final_prediction?: 'bot' | 'human' | ''
    routed?: boolean
  }>
}

type AccountProfile = Record<string, any> & {
  account_id?: string
  author_name?: string
  platform?: string
  post_count?: number
  active_hours?: number
  min_interval_seconds?: number
  recent_posts?: Array<Record<string, any>>
  assessment?: AccountAssessment
}

const loading = ref(false)
const detecting = ref(false)
const detailLoading = ref(false)
const profiles = ref<AccountProfile[]>([])
const detail = ref<AccountProfile | null>(null)
const detailOpen = ref(false)
const pageSize = ref(10)
const eventId = ref('')
const platform = ref<string | undefined>()
const activeModel = ref<AccountModelPointerStatus | null>(null)
const detectionResult = ref<BotDetectionResult | null>(null)
const lastSyncedAt = ref('')

const platformOptions = [
  { label: '微博', value: 'weibo' },
  { label: '抖音', value: 'douyin' },
  { label: '小红书', value: 'xhs' },
]

const columns = [
  { title: '账号', dataIndex: 'author_name', key: 'author_name', width: 220, ellipsis: true },
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 100 },
  { title: '发言数', dataIndex: 'post_count', key: 'post_count', width: 90 },
  { title: '研判结果', dataIndex: 'assessment', key: 'assessment', width: 120 },
  { title: '模型判别', dataIndex: ['assessment', 'prediction'], key: 'prediction', width: 150 },
  { title: '机器人概率', dataIndex: ['assessment', 'bot_probability'], key: 'bot_probability', width: 150 },
  { title: '相近账号', dataIndex: ['assessment', 'similar_accounts'], key: 'support_count', width: 90 },
  { title: '活跃时段', dataIndex: 'active_hours', key: 'active_hours', width: 110 },
  { title: '操作', dataIndex: 'operation', key: 'operation', width: 80 },
]

const similarColumns = [
  { title: '账号 ID', dataIndex: 'account_id', key: 'account_id', ellipsis: true },
  { title: '相似度', dataIndex: 'similarity', key: 'similarity', width: 110 },
  { title: '模型判别', dataIndex: 'final_prediction', key: 'prediction', width: 110 },
  { title: '机器人概率', dataIndex: 'bot_probability', key: 'bot_probability', width: 120 },
  { title: '超图路径', dataIndex: 'routed', key: 'routed', width: 120 },
]

const detailTitle = computed(() => `账号画像 · ${detail.value ? displayName(detail.value) : '-'}`)

const profileStats = computed(() => {
  const rows = profiles.value
  return {
    total: rows.length,
    attention: rows.filter((row) => row.assessment?.level === 'attention').length,
    normal: rows.filter((row) => row.assessment?.level === 'normal').length,
    pending: rows.filter((row) => !row.assessment || row.assessment.level === 'pending').length,
  }
})

const platformCoverage = computed(() => {
  const labels = Array.from(new Set(profiles.value.map((row) => platformLabel(row.platform))))
  return labels.length ? labels.join('、') : '暂无'
})

const detectionSummary = computed(() => {
  const summary = detectionResult.value?.summary || {}
  return {
    account_count: numberOrZero(summary.account_count ?? profileStats.value.total),
    bot_count: numberOrZero(summary.bot_count ?? profileStats.value.attention),
    post_count: numberOrZero(summary.post_count),
  }
})

const detectionStatusText = computed(() => {
  if (!detectionResult.value) return '未运行'
  const status = detectionResult.value.status || 'available'
  if (status === 'unavailable') return '不可用'
  return '已完成'
})

const detectionStatusColor = computed(() => {
  if (!detectionResult.value) return 'default'
  return detectionResult.value.status === 'unavailable' ? 'orange' : 'green'
})

const detectionNarrative = computed(() => {
  const result = detectionResult.value
  if (!result) return '尚未在当前筛选范围内运行账号检测。'
  if (result.status === 'unavailable') {
    return `检测不可用：${reasonLabel(result.pointer_failure_reason || result.reason || result.audit_status)}`
  }
  const latency = result.prediction_latency_ms ? `，耗时 ${Math.round(result.prediction_latency_ms)}ms` : ''
  return `已完成 BotRHG 账号检测${latency}。`
})

const modelProblemMessage = computed(() => {
  if (!activeModel.value) return '尚未读取当前模型指针。'
  if (activeModel.value.status === 'available') return ''
  const reason = reasonLabel(activeModel.value.reason || activeModel.value.detail)
  return `当前账号检测模型不可用：${reason}`
})

const detailAssessmentProblem = computed(() => {
  if (!detail.value) return ''
  if (detail.value.assessment?.prediction) return ''
  if (modelProblemMessage.value) return modelProblemMessage.value
  return '当前账号没有可展示的模型判别结果。'
})

function queryParams(): AccountQueryParams {
  return {
    event_id: eventId.value.trim() || undefined,
    platform: platform.value || undefined,
  }
}

async function loadProfiles() {
  loading.value = true
  try {
    const response = await getAccountProfiles(queryParams())
    profiles.value = response?.data || []
    lastSyncedAt.value = formatClock(new Date())
  } finally {
    loading.value = false
  }
}

async function loadActiveModel() {
  const response = await getActiveAccountModel()
  activeModel.value = response?.data || null
}

async function refreshProfiles() {
  await Promise.all([loadActiveModel(), loadProfiles()])
}

async function handleRunDetection() {
  detecting.value = true
  try {
    const response = await runSocialBotDetection(queryParams())
    detectionResult.value = response?.data || null
    if (detectionResult.value?.accounts?.length) {
      mergeDetectionResult(detectionResult.value)
    }
    if (detectionResult.value?.status === 'unavailable') {
      message.warning(detectionNarrative.value)
    } else {
      message.success('账号检测已完成')
    }
    await loadActiveModel()
  } finally {
    detecting.value = false
  }
}

async function openDetail(record: AccountProfile) {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = record
  try {
    const response = await getAccountDetail(String(record.account_id), {
      ...queryParams(),
      platform: String(record.platform || platform.value || '') || undefined,
    })
    const nextDetail = response?.data || record
    detail.value = mergeSingleAssessment(nextDetail)
  } finally {
    detailLoading.value = false
  }
}

function mergeDetectionResult(result: BotDetectionResult) {
  const byKey = new Map<string, AccountAssessment>()
  for (const row of result.accounts || []) {
    byKey.set(scopedKey(row.platform, row.account_id), detectionAccountToAssessment(row))
  }
  profiles.value = profiles.value.map((profile) => ({
    ...profile,
    assessment: byKey.get(scopedKey(profile.platform, profile.account_id)) || profile.assessment,
  }))
  if (detail.value) {
    detail.value = mergeSingleAssessment(detail.value)
  }
}

function mergeSingleAssessment(record: AccountProfile): AccountProfile {
  const row = (detectionResult.value?.accounts || []).find(
    (item) => scopedKey(item.platform, item.account_id) === scopedKey(record.platform, record.account_id),
  )
  if (!row) return record
  return { ...record, assessment: detectionAccountToAssessment(row) }
}

function detectionAccountToAssessment(row: Record<string, any>): AccountAssessment {
  const prediction = normalizedPrediction(row.final_prediction || row.prediction)
  const probability = probabilityValue(row.calibrated_bot_probability ?? row.final_bot_probability)
  return {
    level: prediction === 'bot' ? 'attention' : prediction === 'human' ? 'normal' : 'pending',
    label: prediction === 'bot' ? '需关注' : prediction === 'human' ? '未见异常' : '暂无研判',
    prediction,
    final_prediction: prediction,
    bot_probability: probability,
    calibrated: Boolean(
      row.calibrated
        || row.calibration_passed
        || (row.calibrated_bot_probability !== null && row.calibrated_bot_probability !== undefined),
    ),
    routed: Boolean(row.routed),
    model_version: activeModel.value?.model_version || '',
    pointer_revision: activeModel.value?.pointer_revision || 0,
    calibration_source: String(row.calibration_source || ''),
    similar_accounts: similarAccountProjection(row.support_evidence),
  }
}

function similarAccountProjection(rows: unknown): AccountAssessment['similar_accounts'] {
  if (!Array.isArray(rows)) return []
  return rows
    .filter((row): row is Record<string, any> => Boolean(row && typeof row === 'object' && row.account_id))
    .slice(0, 10)
    .map((row) => ({
      account_id: String(row.account_id),
      similarity: numberOrNull(row.similarity),
      bot_probability: probabilityValue(row.calibrated_bot_probability ?? row.final_bot_probability),
      final_prediction: normalizedPrediction(row.final_prediction),
      routed: Boolean(row.routed),
    }))
}

function profileRowKey(record: AccountProfile) {
  return scopedKey(record.platform, record.account_id)
}

function scopedKey(platformValue: unknown, accountId: unknown) {
  return `${String(platformValue || 'unknown').toLowerCase()}::${String(accountId || '')}`
}

function scopedAccountLabel(record: AccountProfile) {
  return `${platformLabel(record.platform)} · ${record.account_id || '暂无 ID'}`
}

function displayName(record: AccountProfile) {
  return String(record.author_name || record.account_id || '未命名账号')
}

function assessmentLabel(level: AccountAssessment['level']) {
  if (level === 'attention') return '需关注'
  if (level === 'normal') return '未见异常'
  return '暂无研判'
}

function assessmentColor(level: AccountAssessment['level']) {
  if (level === 'attention') return 'gold'
  if (level === 'normal') return 'green'
  return 'default'
}

function predictionLabel(value: unknown) {
  const prediction = normalizedPrediction(value)
  if (prediction === 'bot') return '社交机器人'
  if (prediction === 'human') return '正常账号'
  return '暂无'
}

function normalizedPrediction(value: unknown): 'bot' | 'human' | '' {
  const prediction = String(value || '').trim().toLowerCase()
  return prediction === 'bot' || prediction === 'human' ? prediction : ''
}

function probabilityLabel(value: unknown) {
  const probability = probabilityValue(value)
  return probability === null ? '暂无' : `${(probability * 100).toFixed(1)}%`
}

function probabilityValue(value: unknown): number | null {
  const probability = Number(value)
  return Number.isFinite(probability) && probability >= 0 && probability <= 1 ? probability : null
}

function probabilityNumber(value: unknown) {
  return probabilityValue(value) ?? 0
}

function probabilityPercent(value: unknown) {
  return `${Math.round(probabilityNumber(value) * 100)}%`
}

function similarityLabel(value: unknown) {
  const similarity = Number(value)
  return Number.isFinite(similarity) ? similarity.toFixed(3) : '暂无'
}

function platformLabel(value: unknown) {
  const current = String(value || '').toLowerCase()
  const labels: Record<string, string> = { weibo: '微博', douyin: '抖音', xhs: '小红书' }
  return labels[current] || '其他平台'
}

function activeHoursLabel(value: unknown) {
  const count = Number(value)
  return Number.isFinite(count) && count > 0 ? `${count} 个时段` : '暂无'
}

function intervalLabel(value: unknown) {
  const seconds = Number(value)
  if (!Number.isFinite(seconds) || seconds <= 0) return '暂无'
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`
  return `${Math.round(seconds / 3600)} 小时`
}

function supportCount(assessment?: AccountAssessment) {
  return assessment?.similar_accounts?.length ?? 0
}

function reasonLabel(value: unknown) {
  const reason = String(value || '').trim()
  const labels: Record<string, string> = {
    active_model_bundle_invalid: '模型制品校验失败',
    account_model_pointer_invalid: '模型指针失效',
    no_active_account_model_pointer: '尚未激活账号检测模型',
    account_model_runtime_unavailable: '模型运行时不可用',
    account_model_runtime_load_failure: '模型加载失败',
    invalid_pointer_without_model_identity: '指针缺少可审计模型身份',
    unavailable_without_active_pointer: '没有可用模型指针',
  }
  return labels[reason] || reason || '原因未返回'
}

function decisionPathLabel(assessment?: AccountAssessment) {
  if (!assessment?.prediction) return '暂无'
  return assessment.routed ? '超图校正' : '基础分类'
}

function postTitle(post: Record<string, any>) {
  return String(post.content || post.text || '暂无内容')
}

function postDesc(post: Record<string, any>) {
  const timestamp = post.timestamp || post.created_at || '时间未标明'
  const likes = post.likes ?? post.like_count ?? 0
  const reposts = post.reposts ?? post.repost_count ?? 0
  const comments = post.comments_count ?? post.comment_count ?? 0
  return `${timestamp} · 点赞 ${likes} · 转发 ${reposts} · 评论 ${comments}`
}

function numberOrZero(value: unknown) {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

function numberOrNull(value: unknown) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatClock(value: Date) {
  return value.toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => {
  void refreshProfiles()
})
</script>

<style scoped>
.account-workbench {
  display: grid;
  gap: 16px;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: #FFFFFF;
  border: 1px solid #E4E4E7;
  border-radius: 6px;
}

.filter-input {
  width: 220px;
}

.platform-select {
  width: 140px;
}

.sync-hint,
.card-note,
.account-subtitle {
  color: #71717A;
  font-size: 12px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.overview-card {
  min-height: 160px;
}

.metric-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.metric-item {
  padding: 10px;
  background: #FAF9F6;
  border: 1px solid #E4E4E7;
  border-radius: 6px;
}

.metric-item span {
  display: block;
  color: #71717A;
  font-size: 12px;
}

.metric-item strong {
  display: block;
  margin-top: 4px;
  color: #18181B;
  font-size: 22px;
  line-height: 1.1;
}

.metric-item.attention strong {
  color: #D97706;
}

.card-note {
  margin: 12px 0 0;
  line-height: 1.6;
}

.profile-table-card {
  min-width: 0;
}

.link-button {
  display: inline;
  padding: 0;
  color: #2563EB;
  font: inherit;
  font-weight: 600;
  text-align: left;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.link-button:focus-visible {
  outline: 2px solid #18181B;
  outline-offset: 2px;
}

.probability-cell {
  display: grid;
  gap: 6px;
}

.probability-track {
  width: 100%;
  height: 6px;
  overflow: hidden;
  background: #E4E4E7;
  border-radius: 999px;
}

.probability-fill {
  height: 100%;
  background: #2563EB;
  border-radius: inherit;
}

.probability-fill.high {
  background: #D97706;
}

.detail-section {
  margin-bottom: 16px;
}

.section-title {
  margin: 0 0 10px;
  color: #18181B;
  font-size: 14px;
  font-weight: 600;
}

.post-list {
  border: 1px solid #E4E4E7;
  border-radius: 6px;
}

.post-content {
  display: block;
  max-width: 720px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1100px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .filter-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .filter-input,
  .platform-select {
    width: 100%;
  }
}
</style>
