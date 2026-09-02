<template>
  <div class="risk-page">
    <PageHeader title="风险研判" />

    <div class="risk-page-actions">
      <a-button type="primary" size="small" :loading="assessing" @click="handleAssess">重新评估</a-button>
    </div>

    <a-card v-if="!report && (historyLoading || assessing)" size="small" class="risk-empty-card">
      <a-spin tip="正在加载风险研判结果..." />
    </a-card>

    <template v-else-if="report">
      <a-tabs v-model:activeKey="activeTab" class="risk-tabs">
        <a-tab-pane key="evidence" tab="证据研判">
          <EvidenceReviewPane
            :all-posts="claimEvidencePosts"
            :support-posts="claimSupportPosts"
            :deny-posts="claimDenyPosts"
            @select-post="selectPostForReview"
          />
        </a-tab-pane>

        <a-tab-pane key="review" tab="智能研判">
          <IntelligentReviewPane
            :report="report"
            :all-analysis-names="allAnalysisNames"
            :recommended-runtime-mode="recommendedRuntimeMode"
            :runtime-reasons="runtimeReasons"
            v-model:selectedNames="selectedAnalysisNames"
            v-model:selectedPostIds="selectedPostIds"
            v-model:selectedTreeIds="selectedTreeIds"
            v-model:runtimeMode="runtimeMode"
            v-model:enableActiveRetrieval="enableActiveRetrieval"
            v-model:enableLightDebate="enableLightDebate"
            v-model:enableFullDebate="enableFullDebate"
            v-model:enableDeepJudge="enableDeepJudge"
            v-model:retrievalTopK="retrievalTopK"
            v-model:debateMaxRounds="debateMaxRounds"
            :loading="reviewLoading"
            :current-job="currentJob"
            :reviews="analysisReports"
            @fill-suggested="fillSuggestedAnalysis"
            @start-review="startReviewJob"
          />
        </a-tab-pane>

        <a-tab-pane key="history" tab="历史报告">
          <HistoryReportsPane
            :items="historyItems"
            :total="historyTotal"
            :page="historyPage"
            :loading="historyLoading"
            @page-change="handleHistoryPageChange"
            @open-report="openRiskReport"
          />
        </a-tab-pane>
      </a-tabs>
    </template>

    <a-card v-else size="small" class="risk-empty-card">
      <a-empty description="暂无数据" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import PageHeader from '@/components/PageHeader.vue'
import {
  assessRisk,
  getReviewJob,
  getRiskReportDetail,
  listRiskReports,
  runReviewAgentReview,
} from '@/api/risk'
import EvidenceReviewPane from './components/EvidenceReviewPane.vue'
import IntelligentReviewPane from './components/IntelligentReviewPane.vue'
import HistoryReportsPane from './components/HistoryReportsPane.vue'

const params = ref({
  platform: 'weibo',
  time_window: 24,
  min_participation: 3,
  edge_weight: 0.5,
})

const activeTab = ref<'evidence' | 'review' | 'history'>('evidence')
const assessing = ref(false)
const report = ref<any>(null)

const reviewLoading = ref(false)
const currentJob = ref<any>(null)
const selectedAnalysisNames = ref<string[]>([])
const selectedPostIds = ref('')
const selectedTreeIds = ref('')
const runtimeMode = ref<'auto' | 'simple' | 'complex'>('auto')
const enableActiveRetrieval = ref(true)
const enableLightDebate = ref(true)
const enableFullDebate = ref(false)
const enableDeepJudge = ref(false)
const retrievalTopK = ref(3)
const debateMaxRounds = ref(3)

const historyItems = ref<any[]>([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyLoading = ref(false)

const postSemantics = computed(() => report.value?.post_semantics || null)
const analysisSuggestions = computed(() => report.value?.review_harmfulness?.agent_review_suggestions || null)
const suggestedAnalysis = computed(() => analysisSuggestions.value?.suggested_agents || [])
const recommendedRuntimeMode = computed(() => analysisSuggestions.value?.recommended_runtime_mode || 'simple')
const runtimeReasons = computed(() => analysisSuggestions.value?.runtime_reasons || [])
const allAnalysisNames = computed(() => analysisSuggestions.value?.all_agents || [
  'PostHarmAgent',
  'MultimodalConsistencyAgent',
  'ClaimEvidenceAgent',
  'PropagationTreeAgent',
  'QuestionReflectionAgent',
  'HarmfulnessJudgeAgent',
  'CountermeasureAgent',
])
const analysisReports = computed(() => report.value?.agent_reviews || [])

watch(recommendedRuntimeMode, (value) => {
  if (runtimeMode.value === 'auto') {
    if (value !== 'complex') {
      enableActiveRetrieval.value = false
      enableLightDebate.value = false
      enableFullDebate.value = false
      enableDeepJudge.value = false
    }
  }
})

watch(runtimeMode, (value) => {
  if (value === 'simple') {
    enableActiveRetrieval.value = false
    enableLightDebate.value = false
    enableFullDebate.value = false
    enableDeepJudge.value = false
  }
})

const claimEvidencePosts = computed(() => {
  const rows = postSemantics.value?.aggregation_posts || postSemantics.value?.posts || []
  return rows.map(normalizeClaimPost).filter((item: any) => item.post_id || item.excerpt)
})

const claimSupportPosts = computed(() => {
  return claimEvidencePosts.value
    .filter((item: any) => item.stanceLabel === 'support' || item.harmLabel === 'harmful')
    .slice(0, 12)
})

const claimDenyPosts = computed(() => {
  return claimEvidencePosts.value
    .filter((item: any) => item.stanceLabel === 'deny' || item.stanceLabel === 'query')
    .slice(0, 12)
})

function normalizeClaimPost(post: any) {
  const primaryClaim = post?.primary_claim || {}
  const stance = post?.stance || {}
  const harmfulness = post?.harmfulness || {}
  const postView = post?.post_view_detection || {}
  return {
    ...post,
    post_id: String(post?.post_id || ''),
    authorName: post?.author_name || post?.author_id || '',
    platformName: post?.platform || post?.source_platform || report.value?.platform || '',
    excerpt: post?.excerpt || post?.text || '',
    primaryClaimId: primaryClaim?.claim_id || '',
    primaryClaimText: primaryClaim?.claim_text || '',
    claimScore: typeof primaryClaim?.score === 'number' ? primaryClaim.score : undefined,
    stanceLabel: stance?.label || postView?.stance?.label || 'unlinked',
    stanceConfidence: stance?.confidence || postView?.stance?.confidence || 0,
    stanceAbstain: Boolean(stance?.abstain || postView?.stance?.abstain),
    harmLabel: harmfulness?.label || postView?.final_harmfulness || 'uncertain',
    harmScore: harmfulness?.score || postView?.harm_score || 0,
    primaryType: harmfulness?.primary_type || postView?.harm_types?.[0] || '',
  }
}

function selectPostForReview(post: any) {
  if (!post?.post_id) return
  selectedPostIds.value = post.post_id
  if (selectedAnalysisNames.value.length === 0) {
    selectedAnalysisNames.value = ['ClaimEvidenceAgent', 'HarmfulnessJudgeAgent']
  }
  activeTab.value = 'review'
  message.success(`已选择帖子 ${post.post_id}`)
}

function fillSuggestedAnalysis() {
  const suggested = suggestedAnalysis.value.map((item: any) => item.agent_name).filter(Boolean)
  selectedAnalysisNames.value = suggested.length ? suggested : allAnalysisNames.value.slice(0, 2)
}

function normalizeSelectedAnalysis() {
  return Array.from(new Set(selectedAnalysisNames.value.filter(Boolean)))
}

function splitCsvLike(value: string) {
  return value
    .split(/[,，\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function buildReviewPayload() {
  const effectiveRuntimeMode = runtimeMode.value === 'auto'
    ? recommendedRuntimeMode.value
    : runtimeMode.value
  return {
    report_id: report.value.report_id,
    selected_post_ids: splitCsvLike(selectedPostIds.value),
    selected_tree_ids: splitCsvLike(selectedTreeIds.value),
    agent_names: normalizeSelectedAnalysis(),
    runtime_mode: runtimeMode.value,
    enable_active_retrieval: effectiveRuntimeMode === 'complex' ? enableActiveRetrieval.value : false,
    enable_light_debate: effectiveRuntimeMode === 'complex' ? enableLightDebate.value : false,
    enable_full_debate: effectiveRuntimeMode === 'complex' ? enableFullDebate.value : false,
    enable_deep_judge: effectiveRuntimeMode === 'complex' ? enableDeepJudge.value : false,
    debate_max_rounds: debateMaxRounds.value,
    retrieval_top_k: retrievalTopK.value,
  }
}

async function startReviewJob() {
  if (!report.value?.report_id) {
    message.warning('请先打开一份风险报告')
    return
  }
  if (normalizeSelectedAnalysis().length === 0) {
    message.warning('请至少选择一种分析方式')
    return
  }
  reviewLoading.value = true
  try {
    const res = await runReviewAgentReview(buildReviewPayload())
    currentJob.value = res.data
    message.success(`研判任务已启动：${displayOrdinal(res.data?.job_id)}`)
    await pollReviewJob(res.data?.job_id)
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.response?.data?.msg || e.message || '研判任务启动失败')
  } finally {
    reviewLoading.value = false
  }
}

async function pollReviewJob(jobId: number | string | undefined) {
  if (!jobId) return
  let transientNotFoundCount = 0
  for (let attempt = 0; attempt < 150; attempt += 1) {
    let res
    try {
      res = await getReviewJob(jobId)
    } catch (e: any) {
      const status = e?.response?.status
      if (status === 404 && transientNotFoundCount < 8) {
        transientNotFoundCount += 1
        await wait(800)
        continue
      }
      throw e
    }
    currentJob.value = res.data
    if (['completed', 'failed'].includes(String(res.data?.status))) {
      if (res.data?.status === 'completed') {
        message.success(`研判任务 ${displayOrdinal(jobId)} 已完成`)
        await refreshCurrentReport()
      } else {
        message.error(res.data?.error || `研判任务 ${displayOrdinal(jobId)} 执行失败`)
      }
      return
    }
    await wait(2000)
  }
  message.warning(`研判任务 ${displayOrdinal(jobId)} 仍在执行，请稍后查看。`)
}

async function refreshCurrentReport() {
  if (!report.value?.report_id) return
  const res = await getRiskReportDetail(report.value.report_id)
  if (res.data) {
    report.value = res.data
  }
}

async function handleAssess(notify: boolean | unknown = true) {
  const shouldNotify = notify !== false
  assessing.value = true
  try {
    const res = await assessRisk(params.value)
    report.value = res.data
    activeTab.value = 'evidence'
    if (shouldNotify) {
      message.success('评估完成')
    }
    await loadHistory(false)
  } catch (e: any) {
    if (shouldNotify) {
      message.error(e.response?.data?.msg || e.message || '评估失败')
    }
  } finally {
    assessing.value = false
  }
}

async function openRiskReport(reportId: string | undefined) {
  if (!reportId) return
  try {
    const res = await getRiskReportDetail(reportId)
    report.value = res.data
    activeTab.value = 'evidence'
    if (!postSemantics.value) {
      await handleAssess(false)
    }
  } catch (e: any) {
    message.error(e.response?.data?.msg || e.message || '加载风险报告失败')
  }
}

async function loadHistory(openLatest = false) {
  historyLoading.value = true
  try {
    const res = await listRiskReports({ page: historyPage.value, page_size: 10 })
    const d = res.data
    historyItems.value = d.items || []
    historyTotal.value = d.total || 0
    if (openLatest && !report.value && historyItems.value.length > 0) {
      await openRiskReport(historyItems.value[0]?.report_id)
    } else if (openLatest && !report.value && historyItems.value.length === 0) {
      await handleAssess(false)
    }
  } catch (e: any) {
    message.error(e.response?.data?.msg || e.message || '加载历史报告失败')
    if (openLatest && !report.value) {
      await handleAssess(false)
    }
  } finally {
    historyLoading.value = false
  }
}

function handleHistoryPageChange(page: number) {
  historyPage.value = page
  loadHistory(false)
}

function displayOrdinal(value: string | number | undefined) {
  const text = String(value ?? '').trim()
  if (!text) return ''
  const numeric = Number(text)
  return Number.isFinite(numeric) ? `第 ${numeric} 个` : '当前任务'
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

onMounted(() => {
  loadHistory(true)
})
</script>

<style scoped>
.risk-page {
  display: flex;
  flex-direction: column;
}

.risk-page-actions {
  align-items: center;
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.risk-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 14px;
}

.risk-tabs :deep(.ant-tabs-tab) {
  font-size: 15px;
  padding: 10px 4px;
}

.risk-empty-card {
  align-items: center;
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
  min-height: 320px;
}
</style>

