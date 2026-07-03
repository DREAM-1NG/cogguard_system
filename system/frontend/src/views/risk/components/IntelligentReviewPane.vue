<template>
  <a-card class="review-pane" size="small" title="智能研判">
    <template v-if="report">
      <section class="review-control">
        <a-row :gutter="[10, 10]">
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
          <a-col :xs="24" :lg="6">
            <a-input v-model:value="selectedPostIdsModel" placeholder="帖子编号" />
          </a-col>
          <a-col :xs="24" :lg="5">
            <a-input v-model:value="selectedTreeIdsModel" placeholder="传播线索编号（可选）" />
          </a-col>
          <a-col :xs="24" :lg="5">
            <a-space>
              <a-button size="small" @click="$emit('fill-suggested')">使用建议</a-button>
              <a-button size="small" type="primary" :loading="loading" @click="$emit('start-review')">
                启动研判
              </a-button>
            </a-space>
          </a-col>
        </a-row>

        <div class="review-options">
          <a-checkbox v-model:checked="enableActiveRetrievalModel">主动检索</a-checkbox>
          <a-checkbox v-model:checked="enableLightDebateModel">交叉质询</a-checkbox>
          <a-checkbox v-model:checked="enableFullDebateModel">完整质询</a-checkbox>
          <a-input-number v-model:value="retrievalTopKModel" :min="1" :max="10" size="small" addon-before="检索条数" />
          <a-input-number v-model:value="debateMaxRoundsModel" :min="1" :max="5" size="small" addon-before="质询轮数" />
        </div>
      </section>

      <a-alert
        v-if="currentJob"
        :type="currentJob.status === 'failed' ? 'error' : currentJob.status === 'completed' ? 'success' : 'info'"
        show-icon
        class="job-alert"
        :message="`研判任务 ${displayOrdinal(currentJob.job_id)} · ${jobStatusLabel(currentJob.status)} · 进度 ${currentJob.progress || 0}%`"
        :description="currentJob.error || currentJob.result?.summary"
      />

      <section v-if="governanceReport" class="governance-section">
        <div class="section-title">治理研判总报告</div>
        <article class="governance-card">
          <div class="governance-meta">
            <a-tag color="blue">{{ governanceReport.governance_category || '综合研判' }}</a-tag>
            <a-tag color="green">证据{{ governanceReport.evidence_sufficiency || '待确认' }}</a-tag>
            <a-tag color="orange">{{ governanceReport.recommended_action || '人审' }}</a-tag>
          </div>
          <pre class="report-text">{{ governanceReport.governance_report_text }}</pre>
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
        <div class="section-title">专家附录</div>
        <a-list v-if="reviews.length > 0" :dataSource="reviews" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <article class="report-card">
                <header class="report-title">
                  <span>{{ analysisDisplayName(item.agent_name) }}</span>
                  <a-tag :color="item.status === 'failed' ? 'red' : item.status === 'completed' ? 'green' : 'blue'">
                    {{ jobStatusLabel(item.status) }}
                  </a-tag>
                </header>
                <pre class="report-text">{{ item.analysis_report?.text || item.report_text || item.error || '暂无内容' }}</pre>
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
import { computed } from 'vue'

const allOption = '__all_analysis__'

const props = defineProps<{
  report: any
  allAnalysisNames: string[]
  selectedNames: string[]
  selectedPostIds: string
  selectedTreeIds: string
  enableActiveRetrieval: boolean
  enableLightDebate: boolean
  enableFullDebate: boolean
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
  (event: 'update:enableActiveRetrieval', value: boolean): void
  (event: 'update:enableLightDebate', value: boolean): void
  (event: 'update:enableFullDebate', value: boolean): void
  (event: 'update:retrievalTopK', value: number): void
  (event: 'update:debateMaxRounds', value: number): void
  (event: 'start-review'): void
  (event: 'fill-suggested'): void
}>()

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

const retrievalTopKModel = computed({
  get: () => props.retrievalTopK,
  set: (value: number) => emit('update:retrievalTopK', value),
})

const debateMaxRoundsModel = computed({
  get: () => props.debateMaxRounds,
  set: (value: number) => emit('update:debateMaxRounds', value),
})

const analysisDisplayNames: Record<string, string> = {
  PostHarmAgent: '帖子危害分析',
  MultimodalConsistencyAgent: '多模态一致性分析',
  ClaimEvidenceAgent: '主张证据核验',
  PropagationTreeAgent: '传播结构分析',
  QuestionReflectionAgent: '问题反思',
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

const governanceReport = computed(() => {
  const judge = props.reviews.find((item: any) => item?.agent_name === 'HarmfulnessJudgeAgent')
  return judge?.structured_sidecar?.governance_report || judge?.system_audit_sidecar?.governance_report || null
})

const platformReferences = computed(() => governanceReport.value?.platform_reference_refs || [])

const humanConfirmationItems = computed(() => governanceReport.value?.human_confirmation_items || [])

function analysisDisplayName(value: string | undefined) {
  const key = String(value || '').trim()
  return key ? (analysisDisplayNames[key] || '研判分析') : '研判分析'
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

function handleSelectionChange(value: string[]) {
  if (value.includes(allOption)) {
    emit('update:selectedNames', props.allAnalysisNames.slice())
    return
  }
  emit('update:selectedNames', Array.from(new Set(value.filter(Boolean))))
}
</script>

<style scoped>
.review-pane {
  border-radius: 18px;
}

.review-control {
  background: linear-gradient(135deg, #f7fbff, #fff);
  border: 1px solid #edf4ff;
  border-radius: 18px;
  padding: 16px;
}

.review-options {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
}

.job-alert {
  margin-top: 14px;
}

.governance-section,
.result-section {
  margin-top: 18px;
}

.section-title {
  color: #262626;
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 12px;
}

.governance-card,
.report-card {
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 16px;
  padding: 14px 16px;
  width: 100%;
}

.governance-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.report-title {
  align-items: center;
  color: #262626;
  display: flex;
  font-weight: 700;
  justify-content: space-between;
  margin-bottom: 10px;
}

.report-text {
  color: #262626;
  font-family: inherit;
  line-height: 1.75;
  margin: 0;
  white-space: pre-wrap;
}

.reference-list,
.confirmation-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.reference-title {
  color: #595959;
  flex-basis: 100%;
  font-size: 13px;
  font-weight: 700;
}

.reference-link {
  background: #f5f9ff;
  border: 1px solid #dcecff;
  border-radius: 999px;
  color: #1f5f99;
  font-size: 12px;
  padding: 3px 10px;
}
</style>
