<template>
  <a-card class="review-pane" size="small" title="智能研判">
    <template v-if="report">
      <section class="review-control">
        <div class="runtime-strip">
          <a-space wrap>
            <span class="runtime-label">系统推荐：</span>
            <a-tag color="blue">{{ runtimeModeLabel(recommendedRuntimeMode) }}</a-tag>
            <a-tag v-for="item in runtimeReasons" :key="item" color="default">
              {{ runtimeReasonLabel(item) }}
            </a-tag>
          </a-space>
        </div>

        <a-row :gutter="[10, 10]">
          <a-col :xs="24" :lg="5">
            <a-segmented v-model:value="runtimeModeModel" block :options="runtimeModeOptions" />
          </a-col>
          <a-col :xs="24" :lg="8">
            <a-select
              v-model:value="selectedNamesModel"
              mode="multiple"
              placeholder="选择分析方式"
              style="width: 100%"
              @change="handleSelectionChange"
            >
              <a-select-option :value="allOption">全部选择</a-select-option>
              <a-select-option v-for="name in allAnalysisNames" :key="name" :value="name">
                {{ analysisDisplayName(name) }}
              </a-select-option>
            </a-select>
          </a-col>
          <a-col :xs="24" :lg="5">
            <a-input v-model:value="selectedPostIdsModel" placeholder="帖子编号" />
          </a-col>
          <a-col :xs="24" :lg="6">
            <a-space wrap>
              <a-button size="small" @click="$emit('fill-suggested')">使用建议</a-button>
              <a-button size="small" type="primary" :loading="loading" @click="$emit('start-review')">
                启动研判
              </a-button>
            </a-space>
          </a-col>
        </a-row>

        <a-row :gutter="[10, 10]" class="mt-10">
          <a-col :xs="24" :lg="12">
            <a-input v-model:value="selectedTreeIdsModel" placeholder="传播线索编号（可选）" />
          </a-col>
        </a-row>

        <div v-if="isComplexMode" class="review-options">
          <a-checkbox v-model:checked="enableActiveRetrievalModel">外部证据检索</a-checkbox>
          <a-checkbox v-model:checked="enableLightDebateModel">多模态争议追问</a-checkbox>
          <a-checkbox v-model:checked="enableFullDebateModel">完整多轮争议追问</a-checkbox>
          <a-checkbox v-model:checked="enableDeepJudgeModel">深度裁决</a-checkbox>
          <a-input-number v-model:value="retrievalTopKModel" :min="1" :max="10" size="small" addon-before="检索条数" />
          <a-input-number v-model:value="debateMaxRoundsModel" :min="1" :max="5" size="small" addon-before="争议轮数" />
        </div>
      </section>

      <a-alert
        v-if="currentJob"
        :type="currentJob.status === 'failed' ? 'error' : currentJob.status === 'completed' ? 'success' : 'info'"
        show-icon
        class="job-alert"
        :message="`研判任务 ${displayOrdinal(currentJob.job_id)} · ${jobStatusLabel(currentJob.status)} · 进度 ${currentJob.progress || 0}%`"
        :description="jobDescription"
      />

      <section v-if="governanceReport" class="governance-section">
        <div class="section-title">综合研判结论</div>
        <article class="governance-card">
          <div class="governance-meta">
            <a-tag color="blue">{{ governanceReport.governance_category || '综合研判' }}</a-tag>
            <a-tag color="green">证据{{ governanceReport.evidence_sufficiency || '待确认' }}</a-tag>
            <a-tag color="orange">{{ governanceReport.recommended_action || '人工复核' }}</a-tag>
          </div>
          <div class="markdown-body" v-html="renderMarkdown(governanceReport.governance_report_text)" />
          <div v-if="platformReferences.length" class="reference-list">
            <div class="reference-title">参考依据</div>
            <a
              v-for="ref in platformReferences"
              :key="ref.ref_id || ref.url"
              class="reference-link"
              :href="ref.url"
              target="_blank"
              rel="noreferrer"
            >
              {{ referenceLabel(ref) }}
            </a>
          </div>
          <div v-if="humanConfirmationItems.length" class="confirmation-list">
            <div class="reference-title">人工确认项</div>
            <a-tag v-for="item in humanConfirmationItems" :key="item" color="default">{{ item }}</a-tag>
          </div>
        </article>
      </section>

      <section class="result-section">
        <div class="section-title">研判结果</div>
        <a-list v-if="displayReviews.length > 0" :dataSource="displayReviews" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <article class="report-card">
                <header class="report-title">
                  <span>{{ analysisDisplayName(item.agent_name) }}</span>
                  <a-tag :color="item.status === 'failed' ? 'red' : item.status === 'completed' ? 'green' : 'blue'">
                    {{ jobStatusLabel(item.status) }}
                  </a-tag>
                </header>
                <div
                  :class="['markdown-body', { collapsed: isCollapsedReport(item) }]"
                  v-html="renderMarkdown(displayReportText(item))"
                />
                <a-button
                  v-if="canToggleReport(item)"
                  type="link"
                  size="small"
                  class="toggle-report-button"
                  @click="toggleReport(item)"
                >
                  {{ isReportExpanded(item) ? '收起' : '展开全文' }}
                </a-button>
              </article>
            </a-list-item>
          </template>
        </a-list>
        <a-empty v-else description="暂无研判结果" />
      </section>
    </template>
    <a-empty v-else description="暂无数据" />
  </a-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const allOption = '__all_analysis__'
const briefLimit = 520

const props = defineProps<{
  report: any
  allAnalysisNames: string[]
  recommendedRuntimeMode: string
  runtimeReasons: string[]
  selectedNames: string[]
  selectedPostIds: string
  selectedTreeIds: string
  runtimeMode: 'auto' | 'simple' | 'complex'
  enableActiveRetrieval: boolean
  enableLightDebate: boolean
  enableFullDebate: boolean
  enableDeepJudge: boolean
  retrievalTopK: number
  debateMaxRounds: number
  loading: boolean
  currentJob: any
  reviews: any[]
}>()

const emit = defineEmits<{
  (event: 'update:selectedNames', value: string[]): void
  (event: 'update:selectedPostIds', value: string): void
  (event: 'update:selectedTreeIds', value: string): void
  (event: 'update:runtimeMode', value: 'auto' | 'simple' | 'complex'): void
  (event: 'update:enableActiveRetrieval', value: boolean): void
  (event: 'update:enableLightDebate', value: boolean): void
  (event: 'update:enableFullDebate', value: boolean): void
  (event: 'update:enableDeepJudge', value: boolean): void
  (event: 'update:retrievalTopK', value: number): void
  (event: 'update:debateMaxRounds', value: number): void
  (event: 'start-review'): void
  (event: 'fill-suggested'): void
}>()

const expandedReportKeys = ref<Set<string>>(new Set())

const selectedNamesModel = computed({
  get: () => props.selectedNames,
  set: (value: string[]) => emit('update:selectedNames', value),
})

const selectedPostIdsModel = computed({
  get: () => props.selectedPostIds,
  set: (value: string) => emit('update:selectedPostIds', value),
})

const selectedTreeIdsModel = computed({
  get: () => props.selectedTreeIds,
  set: (value: string) => emit('update:selectedTreeIds', value),
})

const runtimeModeModel = computed({
  get: () => props.runtimeMode,
  set: (value: 'auto' | 'simple' | 'complex') => emit('update:runtimeMode', value),
})

const enableActiveRetrievalModel = computed({
  get: () => props.enableActiveRetrieval,
  set: (value: boolean) => emit('update:enableActiveRetrieval', value),
})

const enableLightDebateModel = computed({
  get: () => props.enableLightDebate,
  set: (value: boolean) => emit('update:enableLightDebate', value),
})

const enableFullDebateModel = computed({
  get: () => props.enableFullDebate,
  set: (value: boolean) => emit('update:enableFullDebate', value),
})

const enableDeepJudgeModel = computed({
  get: () => props.enableDeepJudge,
  set: (value: boolean) => emit('update:enableDeepJudge', value),
})

const retrievalTopKModel = computed({
  get: () => props.retrievalTopK,
  set: (value: number) => emit('update:retrievalTopK', value),
})

const debateMaxRoundsModel = computed({
  get: () => props.debateMaxRounds,
  set: (value: number) => emit('update:debateMaxRounds', value),
})

const runtimeModeOptions = [
  { label: '系统推荐', value: 'auto' },
  { label: '快速研判', value: 'simple' },
  { label: '深度研判', value: 'complex' },
]

const analysisDisplayNames: Record<string, string> = {
  PostHarmAgent: '帖子危害分析',
  MultimodalConsistencyAgent: '多模态一致性分析',
  ClaimEvidenceAgent: '主张证据核验',
  PropagationTreeAgent: '传播结构分析',
  QuestionReflectionAgent: '问题追问',
  HarmfulnessJudgeAgent: '危害性裁决',
  CountermeasureAgent: '治理建议',
  DecisionRuleOptimizerAgent: '规则优化',
}

const jobStatusLabels: Record<string, string> = {
  pending: '等待中',
  queued: '排队中',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
}

const isComplexMode = computed(() => {
  if (props.runtimeMode === 'complex') return true
  if (props.runtimeMode === 'simple') return false
  return props.recommendedRuntimeMode === 'complex'
})

const governanceReport = computed(() => {
  const judge = props.reviews.find((item: any) => item?.agent_name === 'HarmfulnessJudgeAgent')
  return judge?.structured_sidecar?.governance_report || judge?.system_audit_sidecar?.governance_report || null
})

const platformReferences = computed(() => governanceReport.value?.platform_reference_refs || [])
const humanConfirmationItems = computed(() => governanceReport.value?.human_confirmation_items || [])

const jobDescription = computed(() => {
  const summary = props.currentJob?.result?.summary
  if (typeof summary === 'string' && summary.trim()) return summary
  return props.currentJob?.error || ''
})

const displayReviews = computed(() => {
  const rows = props.reviews.filter((item: any) => item?.report_role !== 'reflection_response')
  const deduped = new Map<string, any>()
  for (const item of rows) {
    const key = normalizedReportKey(item)
    const existing = deduped.get(key)
    if (!existing || reportDisplayPriority(item) > reportDisplayPriority(existing)) {
      deduped.set(key, item)
    }
  }
  return Array.from(deduped.values()).sort((left, right) => agentOrderIndex(left) - agentOrderIndex(right))
})

function analysisDisplayName(value: string | undefined) {
  const key = String(value || '').trim()
  return key ? (analysisDisplayNames[key] || '研判分析') : '研判分析'
}

function runtimeModeLabel(value: string | undefined) {
  const key = String(value || '').trim()
  if (key === 'complex') return '深度研判'
  if (key === 'simple') return '快速研判'
  return '系统推荐'
}

function runtimeReasonLabel(value: string | undefined) {
  const key = String(value || '').trim()
  const mapping: Record<string, string> = {
    multiple_selected_posts: '多条帖子',
    multimodal_conflict_or_media_gap: '多模态冲突',
    claim_retrieval_tasks_present: '主张取证任务',
    propagation_context_present: '传播上下文',
    stance_or_post_view_uncertain: '存在不确定项',
    enabled_active_retrieval: '已开启检索',
    enabled_debate: '已开启争议追问',
    enabled_deep_judge: '已开启深度裁决',
    countermeasure_selected: '已选择治理建议',
    analyst_requested_complex_mode: '人工指定深度研判',
    single_post_low_conflict: '单贴低冲突',
  }
  return mapping[key] || '运行态因素'
}

function jobStatusLabel(value: string | undefined) {
  const key = String(value || '').trim()
  return key ? (jobStatusLabels[key] || '执行中') : '等待中'
}

function displayOrdinal(value: string | number | undefined) {
  const text = String(value ?? '').trim()
  if (!text) return ''
  const numeric = Number(text)
  return Number.isFinite(numeric) ? `第 ${numeric} 个` : '当前'
}

function referenceLabel(ref: any) {
  return [ref.platform, ref.title].filter(Boolean).join(' · ') || '公开治理参考'
}

function reportText(item: any) {
  return String(item?.analysis_report?.text || item?.report_text || item?.error || '暂无内容')
}

function reportKey(item: any) {
  return String(item?.review_id || item?.run_id || item?.agent_name || reportText(item).slice(0, 24))
}

function normalizedReportKey(item: any) {
  return String(item?.agent_name || analysisDisplayName(item?.agent_name) || 'unknown').replace(/ReflectionResponse$/, '')
}

function reportDisplayPriority(item: any) {
  const status = String(item?.status || '').trim()
  const hasText = reportText(item) && reportText(item) !== '暂无内容'
  if (status === 'completed' && hasText) return 40
  if (status === 'completed') return 30
  if (status === 'running' || status === 'queued' || status === 'pending') return 20
  return 10
}

function agentOrderIndex(item: any) {
  const key = normalizedReportKey(item)
  const keys = Object.keys(analysisDisplayNames)
  const index = keys.indexOf(key)
  return index >= 0 ? index : keys.length + 1
}

function canToggleReport(item: any) {
  return reportText(item).length > briefLimit
}

function isReportExpanded(item: any) {
  return expandedReportKeys.value.has(reportKey(item))
}

function isCollapsedReport(item: any) {
  return canToggleReport(item) && !isReportExpanded(item)
}

function displayReportText(item: any) {
  const text = reportText(item)
  if (!isCollapsedReport(item)) return text
  const lines = text.split(/\r?\n/)
  const compact = lines.slice(0, 10).join('\n').trim()
  const candidate = compact.length > briefLimit ? compact.slice(0, briefLimit) : text.slice(0, briefLimit)
  return `${candidate.trim()}……`
}

function toggleReport(item: any) {
  const key = reportKey(item)
  const next = new Set(expandedReportKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedReportKeys.value = next
}

function handleSelectionChange(values: string[]) {
  if (!values.includes(allOption)) return
  const hasAllOnly = values.length === 1
  selectedNamesModel.value = hasAllOnly ? [...props.allAnalysisNames] : values.filter((item) => item !== allOption)
}

function renderMarkdown(value: string | undefined) {
  const text = String(value || '').replace(/\r\n/g, '\n')
  const lines = text.split('\n')
  const html: string[] = []
  let paragraph: string[] = []
  let listOpen = false
  let codeOpen = false
  let codeLines: string[] = []

  const flushParagraph = () => {
    if (!paragraph.length) return
    html.push(`<p>${inlineMarkdown(escapeHtml(paragraph.join(' ')))}</p>`)
    paragraph = []
  }
  const closeList = () => {
    if (!listOpen) return
    html.push('</ul>')
    listOpen = false
  }
  const closeCode = () => {
    if (!codeOpen) return
    html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
    codeLines = []
    codeOpen = false
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd()
    if (line.trim().startsWith('```')) {
      flushParagraph()
      closeList()
      if (codeOpen) closeCode()
      else {
        codeOpen = true
        codeLines = []
      }
      continue
    }
    if (codeOpen) {
      codeLines.push(rawLine)
      continue
    }
    if (!line.trim()) {
      flushParagraph()
      closeList()
      continue
    }
    if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
      flushParagraph()
      if (!listOpen) {
        html.push('<ul>')
        listOpen = true
      }
      html.push(`<li>${inlineMarkdown(escapeHtml(line.trim().slice(2)))}</li>`)
      continue
    }
    if (/^#{1,6}\s/.test(line.trim())) {
      flushParagraph()
      closeList()
      const level = line.trim().match(/^#+/)?.[0].length || 1
      const content = line.trim().replace(/^#{1,6}\s*/, '')
      html.push(`<h${level}>${inlineMarkdown(escapeHtml(content))}</h${level}>`)
      continue
    }
    paragraph.push(line.trim())
  }

  flushParagraph()
  closeList()
  closeCode()
  return html.join('')
}

function inlineMarkdown(value: string) {
  return value
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
</script>

<style scoped>
.review-pane {
  border-radius: 14px;
}

.review-control {
  margin-bottom: 16px;
}

.runtime-strip {
  margin-bottom: 12px;
}

.runtime-label {
  color: #55657a;
  font-size: 13px;
}

.review-options {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
  padding: 12px;
  background: #f7f9fc;
  border-radius: 10px;
}

.mt-10 {
  margin-top: 10px;
}

.job-alert {
  margin-bottom: 16px;
}

.section-title {
  margin-bottom: 10px;
  font-weight: 600;
  color: #1f2d3d;
}

.governance-section,
.result-section {
  margin-top: 14px;
}

.governance-card,
.report-card {
  width: 100%;
  padding: 14px;
  background: #fff;
  border: 1px solid #edf1f7;
  border-radius: 12px;
}

.governance-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.reference-list,
.confirmation-list {
  margin-top: 12px;
}

.reference-title {
  margin-bottom: 8px;
  color: #55657a;
  font-size: 13px;
}

.reference-link {
  display: inline-flex;
  margin-right: 10px;
  margin-bottom: 6px;
}

.report-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  font-weight: 600;
}

.collapsed {
  max-height: 220px;
  overflow: hidden;
}

.toggle-report-button {
  margin-top: 8px;
  padding-left: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 12px 0 8px;
}

.markdown-body :deep(p) {
  margin-bottom: 8px;
  line-height: 1.7;
}

.markdown-body :deep(ul) {
  padding-left: 18px;
  margin-bottom: 8px;
}

.markdown-body :deep(code) {
  padding: 1px 4px;
  background: #f2f4f8;
  border-radius: 4px;
}

.markdown-body :deep(pre) {
  padding: 10px;
  overflow: auto;
  background: #111827;
  color: #f9fafb;
  border-radius: 8px;
}
</style>
