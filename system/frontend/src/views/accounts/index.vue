<template>
  <div class="account-workbench">
    <PageHeader title="账号画像">
      <template #description>
        查看账号研判、近期发言和相似账号，辅助分析员定位需要复核的行为模式。
      </template>
    </PageHeader>

    <section class="filter-bar" aria-label="账号画像筛选">
      <a-space wrap :size="8">
        <label class="sr-only" for="account-event-id">事件 ID</label>
        <a-input
          id="account-event-id"
          v-model:value="eventId"
          class="filter-input"
          size="small"
          name="account-event-id"
          autocomplete="off"
          placeholder="事件 ID，可选…"
          aria-label="事件 ID"
          allow-clear
          @press-enter="applyEventScope"
        />
        <label class="sr-only" for="account-platform">平台</label>
        <a-select
          id="account-platform"
          v-model:value="platform"
          class="platform-select"
          size="small"
          placeholder="全部平台"
          aria-label="平台"
          allow-clear
          :options="platformOptions"
          @change="handlePlatformChange"
        />
        <a-button size="small" :loading="loading" @click="applyEventScope">
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
        <template #title>研判结果</template>
        <template #extra>
          <a-tag :color="detectionStatusColor">{{ detectionStatusText }}</a-tag>
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
            <strong>{{ detectionSummary.activity_count }}</strong>
          </div>
        </div>
        <p class="card-note">{{ detectionNarrative }}</p>
      </a-card>

      <a-card size="small" class="overview-card">
        <template #title>当前范围</template>
        <div class="metric-strip">
          <div class="metric-item">
            <span>账号</span>
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
        <p class="card-note">平台覆盖：{{ platformCoverage }} · 已载入 {{ profiles.length }} 条优先账号</p>
      </a-card>
    </section>

    <section class="account-master-detail" aria-label="账号研判工作台">
      <section class="account-list-pane" aria-labelledby="account-list-title">
        <header class="pane-header">
          <div>
            <h2 id="account-list-title">账号列表</h2>
            <p>显示 {{ profiles.length }} / {{ profileStats.total }} 个账号，按当前研判优先级排列</p>
          </div>
          <span class="pane-meta">优先账号</span>
        </header>

        <a-alert
          v-if="profileError"
          class="pane-alert"
          type="warning"
          show-icon
          message="账号列表加载失败"
          :description="profileError"
        />

        <div class="account-list-scroll" tabindex="0" aria-label="滚动账号列表">
          <a-spin :spinning="loading" class="account-list-loading">
            <div v-if="profiles.length" class="account-list" role="list" aria-label="账号列表">
              <button
                v-for="record in profiles"
                :key="profileRowKey(record)"
                type="button"
                class="account-list-row"
                :class="{ 'is-selected': isSelectedAccount(record) }"
                :aria-pressed="isSelectedAccount(record)"
                :aria-label="`查看账号 ${displayName(record)}`"
                :ref="(element) => captureAccountListRow(record, element)"
                @click="selectAccount(record)"
              >
                <span class="account-list-heading">
                  <strong>{{ displayName(record) }}</strong>
                  <a-tag>{{ platformLabel(record.platform) }}</a-tag>
                </span>
                <span class="account-list-meta">
                  <span>{{ record.post_count ?? 0 }} 条发言</span>
                  <span>{{ assessmentLabel(record.assessment?.level) }}</span>
                </span>
                <span class="account-list-probability">
                  <span>机器人概率</span>
                  <strong>{{ probabilityLabel(record.assessment?.bot_probability) }}</strong>
                </span>
              </button>
            </div>
            <a-empty v-else-if="!loading" description="当前范围暂无账号画像数据" />
          </a-spin>
        </div>
      </section>

      <section class="account-detail-pane" aria-labelledby="account-detail-title" aria-live="polite">
        <a-skeleton v-if="detailLoading && !detail" active :paragraph="{ rows: 8 }" />
        <a-empty v-else-if="!detail" description="从左侧选择账号查看画像" />

        <template v-else>
          <header class="detail-header">
            <div class="detail-title-wrap">
              <span class="detail-eyebrow">当前账号</span>
              <h2 id="account-detail-title">{{ displayName(detail) }}</h2>
              <p>{{ scopedAccountLabel(detail) }}</p>
            </div>
            <a-tag :color="assessmentColor(detail.assessment?.level)">
              {{ assessmentLabel(detail.assessment?.level) }}
            </a-tag>
          </header>

          <a-alert
            v-if="detailError"
            class="detail-alert"
            type="warning"
            show-icon
            message="账号详情未完全加载"
            :description="detailError"
          >
            <template #action>
              <a-button size="small" @click="retryDetail">重试</a-button>
            </template>
          </a-alert>

          <section class="profile-facts" aria-label="账号概要">
            <div class="profile-fact">
              <span>发言数</span>
              <strong>{{ detail.post_count ?? 0 }}</strong>
            </div>
            <div class="profile-fact">
              <span>机器人概率</span>
              <strong>{{ probabilityLabel(detail.assessment?.bot_probability) }}</strong>
            </div>
            <div class="profile-fact">
              <span>活跃时段</span>
              <strong>{{ activeHoursLabel(detail.active_hours) }}</strong>
            </div>
            <div class="profile-fact">
              <span>判别路径</span>
              <strong>{{ decisionPathLabel(detail.assessment) }}</strong>
            </div>
          </section>

          <section class="detail-section similar-section" aria-labelledby="similar-account-title">
            <div class="section-heading">
              <div>
                <h3 id="similar-account-title">相似账号</h3>
                <p>按当前检测运行中的账号特征相近度排序。</p>
              </div>
              <span class="section-count">{{ similarAccounts.length }} 个</span>
            </div>
            <p class="method-note">相近度用于账号研判辅助，不代表关注、好友或转发关系。</p>

            <ol v-if="similarAccounts.length" class="similar-account-list" aria-label="相似账号列表">
              <li v-for="(neighbor, index) in similarAccounts" :key="`${neighbor.platform}-${neighbor.account_id}`">
                <button
                  type="button"
                  class="similar-account-row"
                  :aria-label="`查看相似账号 ${similarAccountName(neighbor)}`"
                  @click="selectSimilarAccount(neighbor)"
                >
                  <span class="similar-rank" aria-hidden="true">{{ index + 1 }}</span>
                  <span class="similar-account-main">
                    <strong>{{ similarAccountName(neighbor) }}</strong>
                    <span>{{ platformLabel(neighbor.platform) }} · {{ neighbor.account_id }}</span>
                  </span>
                  <span class="similarity-measure">
                    <span class="similarity-track" aria-hidden="true">
                      <span :style="{ width: similarityPercent(neighbor.similarity) }" />
                    </span>
                    <strong>{{ similarityLabel(neighbor.similarity) }}</strong>
                  </span>
                  <span class="similar-account-verdict">
                    <span>{{ predictionLabel(neighbor.final_prediction) }}</span>
                    <span>{{ probabilityLabel(neighbor.bot_probability) }}</span>
                    <small>{{ neighbor.routed ? '参与本次校正' : '未参与本次校正' }}</small>
                  </span>
                </button>
              </li>
            </ol>
            <a-empty
              v-else
              description="当前检测未产出相似账号"
              :image-style="{ height: '42px' }"
            />
          </section>

          <section class="detail-section" aria-labelledby="recent-post-title">
            <div class="section-heading">
              <div>
                <h3 id="recent-post-title">近期发言</h3>
                <p>保留原帖文本与互动信息，支持人工核查。</p>
              </div>
            </div>
            <a-list v-if="(detail.recent_posts || []).length" :data-source="detail.recent_posts || []" size="small" class="post-list">
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
              v-else
              description="暂无近期发言"
              :image-style="{ height: '42px' }"
            />
          </section>
        </template>
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, type ComponentPublicInstance } from 'vue'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import {
  getAccountDetail,
  getAccountProfilePage,
  getActiveAccountModel,
  runSocialBotDetection,
  type AccountModelPointerStatus,
  type AccountProfilePage,
  type AccountQueryParams,
  type BotDetectionResult,
} from '@/api/accounts'
import {
  acceptAccountDetailResponse,
  accountSelectionKey,
  accountTargetFromProfile,
  resolveAccountSelection,
  sameAccountTarget,
  type AccountTarget,
} from './accountWorkbench'

type SimilarAccount = {
  account_id: string
  platform: string
  author_name?: string
  similarity?: number | null
  bot_probability?: number | null
  final_prediction?: 'bot' | 'human' | ''
  routed?: boolean
}

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
  similar_accounts?: Array<Omit<SimilarAccount, 'platform' | 'author_name'>>
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

type RefreshProfilesOptions = {
  keepSelection?: boolean
  useRouteSelection?: boolean
}

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const detecting = ref(false)
const detailLoading = ref(false)
const profileError = ref('')
const detailError = ref('')
const profiles = ref<AccountProfile[]>([])
const profilePage = ref<AccountProfilePage | null>(null)
const detail = ref<AccountProfile | null>(null)
const selectedAccount = ref<AccountTarget | null>(null)
const accountListRowElements = new Map<string, HTMLButtonElement>()
const eventId = ref(queryValue(route.query.event_id))
const platform = ref<string | undefined>(queryValue(route.query.platform) || undefined)
const activeModel = ref<AccountModelPointerStatus | null>(null)
const detectionResult = ref<BotDetectionResult | null>(null)
const lastSyncedAt = ref('')
let profilesRequestGeneration = 0
let detailRequestGeneration = 0
const PROFILE_PAGE_SIZE = 200

const platformOptions = [
  { label: '微博', value: 'weibo' },
  { label: '抖音', value: 'douyin' },
  { label: '小红书', value: 'xhs' },
]

const profileStats = computed(() => {
  const rows = profiles.value
  return {
    total: Number(profilePage.value?.total ?? rows.length),
    attention: Number(profilePage.value?.attention ?? rows.filter((row) => row.assessment?.level === 'attention').length),
    pending: Number(profilePage.value?.pending ?? rows.filter((row) => !row.assessment || row.assessment.level === 'pending').length),
  }
})

const platformCoverage = computed(() => {
  const source = profilePage.value?.platforms || profiles.value.map((row) => String(row.platform || ''))
  const labels = Array.from(new Set(source.map((value) => platformLabel(value))))
  return labels.length ? labels.join('、') : '暂无'
})

const detectionSummary = computed(() => {
  const summary = detectionResult.value?.summary || {}
  return {
    account_count: numberOrZero(summary.account_count ?? profileStats.value.total),
    bot_count: numberOrZero(summary.bot_count ?? profileStats.value.attention),
    activity_count: numberOrZero(summary.activity_count ?? summary.post_count),
  }
})

const detectionStatusText = computed(() => {
  if (!detectionResult.value) return '未运行'
  return detectionResult.value.status === 'unavailable' ? '不可用' : '已完成'
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
  return `已完成账号检测${latency}。`
})

const similarAccounts = computed<SimilarAccount[]>(() => {
  const anchor = detail.value
  const anchorPlatform = String(anchor?.platform || '').trim().toLowerCase()
  if (!anchorPlatform) return []
  return (anchor?.assessment?.similar_accounts || []).map((neighbor) => {
    const profile = profileForTarget({ platform: anchorPlatform, accountId: neighbor.account_id })
    return {
      ...neighbor,
      platform: anchorPlatform,
      author_name: profile?.author_name,
      final_prediction: neighbor.final_prediction || profile?.assessment?.prediction,
      bot_probability: neighbor.bot_probability ?? profile?.assessment?.bot_probability,
    }
  })
})

function queryValue(value: unknown): string {
  return Array.isArray(value) ? String(value[0] || '').trim() : String(value || '').trim()
}

function queryParams(): AccountQueryParams {
  return {
    event_id: eventId.value.trim() || undefined,
    platform: platform.value || undefined,
  }
}

function routeSelection(): AccountTarget | null {
  const accountId = queryValue(route.query.account_id)
  const accountPlatform = queryValue(route.query.account_platform) || queryValue(route.query.platform)
  return accountId && accountPlatform ? { platform: accountPlatform, accountId } : null
}

function syncRoute() {
  const query = { ...route.query }
  const currentEventId = eventId.value.trim()
  if (currentEventId) query.event_id = currentEventId
  else delete query.event_id
  if (platform.value) query.platform = platform.value
  else delete query.platform
  if (selectedAccount.value) {
    query.account_id = selectedAccount.value.accountId
    query.account_platform = selectedAccount.value.platform
  } else {
    delete query.account_id
    delete query.account_platform
  }
  void router.replace({ query })
}

function profileRowKey(record: AccountProfile) {
  const target = accountTargetFromProfile(record)
  return target ? accountSelectionKey(target) : `unknown::${String(record.account_id || '')}`
}

function profileForTarget(target: AccountTarget | null): AccountProfile | undefined {
  return profiles.value.find((profile) => sameAccountTarget(accountTargetFromProfile(profile), target))
}

function isSelectedAccount(record: AccountProfile): boolean {
  return sameAccountTarget(accountTargetFromProfile(record), selectedAccount.value)
}

function captureAccountListRow(record: AccountProfile, element: Element | ComponentPublicInstance | null) {
  const target = accountTargetFromProfile(record)
  if (!target) return
  const key = accountSelectionKey(target)
  if (element instanceof HTMLButtonElement) accountListRowElements.set(key, element)
  else accountListRowElements.delete(key)
}

function scrollSelectedAccountIntoView(target: AccountTarget) {
  accountListRowElements
    .get(accountSelectionKey(target))
    ?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

async function loadProfiles(options: RefreshProfilesOptions = {}) {
  const requestGeneration = ++profilesRequestGeneration
  const requested = options.keepSelection
    ? selectedAccount.value
    : options.useRouteSelection
      ? routeSelection()
      : null
  loading.value = true
  profileError.value = ''
  try {
    const response = await getAccountProfilePage({
      ...queryParams(),
      page: 1,
      page_size: PROFILE_PAGE_SIZE,
    })
    if (requestGeneration !== profilesRequestGeneration) return
    profilePage.value = response?.data || null
    profiles.value = Array.isArray(response?.data?.items) ? response.data.items : []
    lastSyncedAt.value = formatClock(new Date())
    const nextSelection = resolveAccountSelection(profiles.value, requested)
    if (!nextSelection) {
      selectedAccount.value = null
      detail.value = null
      detailError.value = ''
      syncRoute()
      return
    }
    const nextProfile = profileForTarget(nextSelection)
    if (nextProfile) void selectAccount(nextProfile)
  } catch {
    if (requestGeneration !== profilesRequestGeneration) return
    profiles.value = []
    profilePage.value = null
    selectedAccount.value = null
    detail.value = null
    detailError.value = ''
    profileError.value = '请检查当前事件范围与服务连接后重试。'
    syncRoute()
  } finally {
    if (requestGeneration === profilesRequestGeneration) loading.value = false
  }
}

async function loadActiveModel() {
  try {
    const response = await getActiveAccountModel()
    activeModel.value = response?.data || null
  } catch {
    activeModel.value = null
  }
}

async function refreshProfiles(options: RefreshProfilesOptions = {}) {
  await Promise.all([loadActiveModel(), loadProfiles(options)])
}

function applyEventScope() {
  void refreshProfiles({ keepSelection: false })
}

function handlePlatformChange() {
  void refreshProfiles({ keepSelection: false })
}

async function handleRunDetection() {
  detecting.value = true
  try {
    const response = await runSocialBotDetection(queryParams())
    detectionResult.value = response?.data || null
    if (detectionResult.value?.accounts?.length) mergeDetectionResult(detectionResult.value)
    if (detectionResult.value?.status === 'unavailable') message.warning(detectionNarrative.value)
    else message.success('账号检测已完成')
    await loadActiveModel()
  } finally {
    detecting.value = false
  }
}

async function selectAccount(record: AccountProfile, scrollListRow = false) {
  const target = accountTargetFromProfile(record)
  if (!target) return
  selectedAccount.value = target
  detail.value = mergeSingleAssessment(record)
  detailError.value = ''
  syncRoute()
  if (scrollListRow) {
    await nextTick()
    scrollSelectedAccountIntoView(target)
  }
  await loadAccountDetail(record, target)
}

async function loadAccountDetail(record: AccountProfile, target: AccountTarget) {
  const requestGeneration = ++detailRequestGeneration
  detailLoading.value = true
  try {
    const response = await getAccountDetail(target.accountId, {
      ...queryParams(),
      platform: target.platform,
    })
    if (!acceptAccountDetailResponse({
      requestGeneration,
      currentGeneration: detailRequestGeneration,
      requested: target,
      current: selectedAccount.value,
    })) return
    detail.value = mergeSingleAssessment(response?.data || record)
  } catch {
    if (!acceptAccountDetailResponse({
      requestGeneration,
      currentGeneration: detailRequestGeneration,
      requested: target,
      current: selectedAccount.value,
    })) return
    detailError.value = '详情请求未完成，当前画像显示的是列表中的已加载信息。'
  } finally {
    if (requestGeneration === detailRequestGeneration) detailLoading.value = false
  }
}

function retryDetail() {
  const current = selectedAccount.value
  const profile = profileForTarget(current)
  if (current && profile) void loadAccountDetail(profile, current)
}

function selectSimilarAccount(neighbor: SimilarAccount) {
  const target = {
    platform: String(detail.value?.platform || ''),
    accountId: neighbor.account_id,
  }
  const profile = profileForTarget(target)
  if (profile) {
    void selectAccount(profile, true)
    return
  }
  void selectAccount({
    account_id: target.accountId,
    author_name: neighbor.author_name || target.accountId,
    platform: target.platform,
  }, true)
}

function mergeDetectionResult(result: BotDetectionResult) {
  const byKey = new Map<string, AccountAssessment>()
  for (const row of result.accounts || []) {
    const target = accountTargetFromProfile({ platform: row.platform, account_id: row.account_id })
    if (target) byKey.set(accountSelectionKey(target), detectionAccountToAssessment(row))
  }
  profiles.value = profiles.value.map((profile) => {
    const target = accountTargetFromProfile(profile)
    return { ...profile, assessment: target ? byKey.get(accountSelectionKey(target)) || profile.assessment : profile.assessment }
  })
  if (detail.value) detail.value = mergeSingleAssessment(detail.value)
}

function mergeSingleAssessment(record: AccountProfile): AccountProfile {
  const target = accountTargetFromProfile(record)
  const row = (detectionResult.value?.accounts || []).find((item) => {
    const candidate = accountTargetFromProfile({ platform: item.platform, account_id: item.account_id })
    return sameAccountTarget(candidate, target)
  })
  return row ? { ...record, assessment: detectionAccountToAssessment(row) } : record
}

function detectionAccountToAssessment(row: Record<string, any>): AccountAssessment {
  const prediction = normalizedPrediction(row.final_prediction || row.prediction)
  return {
    level: prediction === 'bot' ? 'attention' : prediction === 'human' ? 'normal' : 'pending',
    label: prediction === 'bot' ? '需关注' : prediction === 'human' ? '未见异常' : '暂无模型输出',
    prediction,
    final_prediction: prediction,
    bot_probability: probabilityValue(row.calibrated_bot_probability ?? row.final_bot_probability),
    calibrated: Boolean(row.calibrated || row.calibration_passed),
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
    .map((row) => ({
      account_id: String(row.account_id),
      similarity: numberOrNull(row.similarity),
      bot_probability: probabilityValue(row.calibrated_bot_probability ?? row.final_bot_probability),
      final_prediction: normalizedPrediction(row.final_prediction),
      routed: Boolean(row.routed),
    }))
}

function displayName(record: AccountProfile) {
  return String(record.author_name || record.account_id || '未命名账号')
}

function similarAccountName(neighbor: SimilarAccount) {
  return String(neighbor.author_name || neighbor.account_id || '未命名账号')
}

function scopedAccountLabel(record: AccountProfile) {
  return `${platformLabel(record.platform)} · ${record.account_id || '暂无 ID'}`
}

function assessmentLabel(level: AccountAssessment['level']) {
  if (level === 'attention') return '需关注'
  if (level === 'normal') return '未见异常'
  return '暂无模型输出'
}

function assessmentColor(level: AccountAssessment['level']) {
  if (level === 'attention') return 'gold'
  if (level === 'normal') return 'green'
  return 'default'
}

function predictionLabel(value: unknown) {
  const prediction = normalizedPrediction(value)
  if (prediction === 'bot') return '疑似自动化账号'
  if (prediction === 'human') return '正常账号'
  return '暂无模型输出'
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

function similarityLabel(value: unknown) {
  const similarity = Number(value)
  return Number.isFinite(similarity) ? similarity.toFixed(3) : '暂无'
}

function similarityPercent(value: unknown) {
  const similarity = Number(value)
  const normalized = Number.isFinite(similarity) ? Math.min(1, Math.max(0, similarity)) : 0
  return `${Math.round(normalized * 100)}%`
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

function decisionPathLabel(assessment?: AccountAssessment) {
  if (!assessment?.prediction) return '暂无'
  return assessment.routed ? '模型校正' : '基础模型输出'
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

function formatClock(value: Date) {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'short',
    timeStyle: 'medium',
    hour12: false,
  }).format(value)
}

onMounted(() => {
  void refreshProfiles({ useRouteSelection: true })
})
</script>

<style scoped>
.account-workbench {
  display: grid;
  gap: 16px;
}

.filter-bar,
.account-master-detail {
  border: 1px solid #e4eaf1;
  border-radius: 6px;
  background: #fff;
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
}

.filter-input {
  width: 220px;
}

.platform-select {
  width: 140px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.sync-hint,
.card-note,
.pane-header p,
.detail-title-wrap p,
.section-heading p,
.method-note {
  color: #667085;
  font-size: 12px;
}

.sync-hint {
  font-variant-numeric: tabular-nums;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.overview-card {
  min-height: 160px;
}

.metric-strip,
.profile-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.metric-item {
  padding: 10px;
  border: 1px solid #e8eef6;
  border-radius: 6px;
  background: #f7f9fc;
}

.metric-item span,
.profile-fact span {
  display: block;
  color: #667085;
  font-size: 12px;
}

.metric-item strong {
  display: block;
  margin-top: 4px;
  color: #101828;
  font-size: 22px;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.metric-item.attention strong {
  color: #b26a00;
}

.card-note {
  margin: 12px 0 0;
  line-height: 1.6;
}

.account-master-detail {
  display: grid;
  grid-template-columns: minmax(290px, 0.85fr) minmax(0, 1.65fr);
  height: clamp(620px, calc(100dvh - 250px), 780px);
  min-height: 0;
  overflow: hidden;
}

.account-list-pane,
.account-detail-pane {
  min-width: 0;
  min-height: 0;
  padding: 18px;
}

.account-list-pane {
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e4eaf1;
  background: #fbfcfe;
}

.pane-header,
.detail-header,
.section-heading,
.account-list-heading,
.account-list-meta,
.account-list-probability,
.similar-account-main,
.similarity-measure,
.similar-account-verdict {
  display: flex;
}

.pane-header,
.detail-header,
.section-heading {
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.pane-header {
  margin-bottom: 12px;
}

.pane-header h2,
.detail-header h2,
.section-heading h3 {
  margin: 0;
  color: #101828;
  letter-spacing: 0;
}

.pane-header h2,
.detail-header h2 {
  font-size: 18px;
  line-height: 1.35;
}

.pane-header p,
.detail-title-wrap p,
.section-heading p {
  margin: 4px 0 0;
  line-height: 1.5;
}

.pane-meta,
.section-count {
  flex: 0 0 auto;
  color: #667085;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.pane-alert,
.detail-alert {
  margin-bottom: 12px;
}

.account-list {
  display: grid;
  gap: 6px;
  min-height: 0;
}

.account-list-scroll {
  flex: 1;
  min-height: 0;
  padding-right: 6px;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-color: #aebdca transparent;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
}

.account-list-scroll:focus-visible {
  outline: 3px solid #91caff;
  outline-offset: 2px;
}

.account-list-scroll::-webkit-scrollbar {
  width: 8px;
}

.account-list-scroll::-webkit-scrollbar-thumb {
  border: 2px solid #fbfcfe;
  border-radius: 999px;
  background: #aebdca;
}

.account-list-scroll::-webkit-scrollbar-thumb:hover {
  background: #7f94a8;
}

.account-list-loading {
  display: block;
  min-height: 100%;
}

.account-list-loading :deep(.ant-spin-nested-loading),
.account-list-loading :deep(.ant-spin-container) {
  min-height: 100%;
}

.account-list-row,
.similar-account-row {
  width: 100%;
  color: inherit;
  text-align: left;
  cursor: pointer;
  touch-action: manipulation;
}

.account-list-row {
  display: grid;
  gap: 7px;
  padding: 12px;
  border: 1px solid transparent;
  border-radius: 5px;
  background: transparent;
  transition: background-color 150ms ease, border-color 150ms ease;
}

.account-list-row:hover {
  border-color: #cbd9e6;
  background: #f1f6fb;
}

.account-list-row.is-selected {
  border-color: #63809e;
  background: #eaf1f8;
  box-shadow: inset 3px 0 0 #315d7e;
}

.account-list-row:focus-visible,
.similar-account-row:focus-visible {
  outline: 3px solid #91caff;
  outline-offset: 2px;
}

.account-list-heading {
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.account-list-heading strong,
.similar-account-main strong,
.post-content {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-list-heading strong {
  font-size: 14px;
}

.account-list-meta,
.account-list-probability {
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #667085;
  font-size: 12px;
}

.account-list-probability strong {
  color: #344054;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.account-detail-pane {
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
  background: #fff;
}

.detail-header {
  padding-bottom: 16px;
  border-bottom: 1px solid #e4eaf1;
}

.detail-eyebrow {
  display: block;
  margin-bottom: 5px;
  color: #5d7185;
  font-size: 12px;
  font-weight: 600;
}

.profile-facts {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  padding: 16px 0;
  border-bottom: 1px solid #e4eaf1;
}

.profile-fact {
  min-width: 0;
}

.profile-fact strong {
  display: block;
  margin-top: 5px;
  overflow-wrap: anywhere;
  color: #1d2939;
  font-size: 14px;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
}

.detail-section {
  padding-top: 18px;
}

.section-heading h3 {
  font-size: 15px;
  line-height: 1.4;
}

.method-note {
  margin: 10px 0 8px;
  line-height: 1.5;
}

.similar-account-list {
  display: grid;
  gap: 4px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.similar-account-row {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) minmax(120px, 0.7fr) minmax(132px, 0.75fr);
  align-items: center;
  gap: 12px;
  padding: 10px 8px;
  border: 1px solid transparent;
  border-radius: 5px;
  background: #fff;
  transition: background-color 150ms ease, border-color 150ms ease;
}

.similar-account-row:hover {
  border-color: #d7e1eb;
  background: #f8fafc;
}

.similar-rank {
  color: #667085;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.similar-account-main,
.similar-account-verdict {
  flex-direction: column;
  min-width: 0;
}

.similar-account-main strong {
  color: #1d2939;
  font-size: 13px;
}

.similar-account-main span,
.similar-account-verdict span,
.similar-account-verdict small {
  overflow-wrap: anywhere;
  color: #667085;
  font-size: 12px;
  line-height: 1.45;
}

.similarity-measure {
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.similarity-track {
  display: block;
  flex: 1;
  min-width: 32px;
  height: 5px;
  overflow: hidden;
  border-radius: 3px;
  background: #e7edf3;
}

.similarity-track > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #63809e;
}

.similarity-measure strong {
  color: #344054;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.similar-account-verdict small {
  color: #5d7185;
}

.post-list {
  border: 1px solid #edf2f7;
  border-radius: 5px;
}

.post-content {
  display: block;
  max-width: 100%;
}

@media (max-width: 1100px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .account-master-detail {
    grid-template-columns: minmax(260px, 0.8fr) minmax(0, 1.2fr);
  }

  .similar-account-row {
    grid-template-columns: 22px minmax(0, 1fr) minmax(110px, 0.6fr);
  }

  .similar-account-verdict {
    grid-column: 2 / -1;
    flex-direction: row;
    gap: 8px;
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

  .account-master-detail {
    grid-template-columns: 1fr;
    height: auto;
    min-height: 0;
  }

  .account-list-pane {
    height: min(460px, 60dvh);
    border-right: 0;
    border-bottom: 1px solid #e4eaf1;
  }

  .account-detail-pane {
    overflow-y: visible;
  }

  .profile-facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    row-gap: 16px;
  }

  .similar-account-row {
    grid-template-columns: 22px minmax(0, 1fr);
    gap: 8px;
  }

  .similarity-measure,
  .similar-account-verdict {
    grid-column: 2;
  }

  .similar-account-verdict {
    flex-wrap: wrap;
  }
}

@media (prefers-reduced-motion: reduce) {
  .account-list-row,
  .similar-account-row {
    transition: none;
  }
}
</style>
