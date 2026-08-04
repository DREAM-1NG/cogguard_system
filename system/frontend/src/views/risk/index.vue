<template>
  <div class="review-page">
    <PageHeader title="事件研判" />

    <section class="selector-bar" aria-labelledby="case-selector-title">
      <div>
        <h3 id="case-selector-title" class="section-title">事件搜索与切换</h3>
        <p class="section-subtitle">按事件名称或复核条目搜索</p>
      </div>
      <a-space class="selector-actions" :size="8" wrap>
        <a-select
          v-model:value="selectedCaseId"
          show-search
          allow-clear
          :filter-option="false"
          :options="caseOptions"
          :loading="searching"
          class="case-select"
          placeholder="搜索事件"
          aria-label="搜索事件"
          @search="handleCaseSearch"
          @change="handleCaseChange"
        />
        <a-button :loading="loading" aria-label="刷新当前事件" @click="refreshCurrentCase">刷新</a-button>
      </a-space>
    </section>

    <a-spin :spinning="loading">
      <a-empty v-if="!currentCase" description="暂无可复核事件" class="empty-state" />

      <template v-else>
        <section class="summary-grid" aria-label="事件复核摘要">
          <a-card size="small" class="summary-card">
            <template #title>系统初判</template>
            <div class="case-title">{{ currentCase.title }}</div>
            <div class="case-meta">
              <span>更新：{{ formatTime(currentCase.updated_at) }}</span>
            </div>
            <div class="preliminary-status" :class="`is-${currentCase.preliminary_finding.conclusion}`">
              <div class="preliminary-title">{{ conclusionLabel(currentCase.preliminary_finding.conclusion) }}</div>
              <p>{{ preliminaryNarrative }}</p>
            </div>
            <div class="summary-meta">
              证据充分度：{{ sufficiencyLabel(currentCase.evidence_sufficiency) }}
              <span>·</span>
              {{ urgencyLabel(currentCase.urgency) }}
              <span>·</span>
              {{ dispositionLabel(currentCase.disposition) }}
            </div>
          </a-card>

          <a-card size="small" title="证据充分度" class="summary-card">
            <a-list size="small" :data-source="sufficiencyLines">
              <template #renderItem="{ item }">
                <a-list-item>{{ item }}</a-list-item>
              </template>
            </a-list>
            <a-empty
              v-if="sufficiencyLines.length === 0"
              description="暂无补充说明"
              :image-style="{ height: '36px' }"
            />
          </a-card>

          <a-card size="small" title="协调摘要" class="summary-card">
            <p class="rationale">{{ coordinationNarrative }}</p>
            <div class="mini-list">
              <span class="mini-label">重点群体</span>
              <span v-for="item in visibleKeyCommunities" :key="item" class="focus-label">{{ item }}</span>
              <span v-if="visibleKeyCommunities.length === 0" class="muted">暂无</span>
            </div>
            <div class="mini-list">
              <span class="mini-label">重点账号</span>
              <span v-for="item in visibleKeyAccounts" :key="item" class="focus-label">{{ item }}</span>
              <span v-if="hiddenKeyAccountCount" class="muted">等 {{ hiddenKeyAccountCount }} 个账号</span>
              <span v-if="visibleKeyAccounts.length === 0" class="muted">暂无</span>
            </div>
          </a-card>
        </section>

        <section class="workspace-grid">
          <a-card size="small" class="evidence-panel">
            <template #title>证据分组与标注</template>
            <template #extra>
              <a-button
                size="small"
                aria-label="申请复核"
                @click="openReviewRequest"
              >
                申请复核
              </a-button>
            </template>

            <a-tabs v-model:activeKey="activeEvidenceGroup" size="small">
              <a-tab-pane
                v-for="group in evidenceGroups"
                :key="group.key"
                :tab="`${group.label} (${group.items.length})`"
              >
                <div class="evidence-list" role="list" :aria-label="`${group.label}证据`">
                  <article
                    v-for="item in group.items"
                    :key="item.evidence_ref"
                    class="evidence-item"
                    role="listitem"
                  >
                    <div class="evidence-heading">
                      <a-checkbox
                        :checked="selectedEvidenceRefs.includes(item.evidence_ref)"
                        :aria-label="`选择证据 ${item.title}`"
                        @change="toggleEvidenceRef(item.evidence_ref)"
                      />
                      <div>
                        <h4>{{ item.title }}</h4>
                        <div class="case-meta">
                          <span>{{ evidenceTypeLabel(item.evidence_type) }}</span>
                          <span>{{ item.platform || '来源未标明' }}</span>
                          <span>{{ formatTime(item.observed_at) }}</span>
                        </div>
                      </div>
                    </div>
                    <p class="evidence-excerpt">{{ item.excerpt || '暂无摘要' }}</p>
                    <div class="evidence-footer">
                      <a-space :size="8" wrap>
                        <a-tag :color="assessmentColor(item.assessment)">
                          {{ assessmentLabel(item.assessment) }}
                        </a-tag>
                        <a-button size="small" aria-label="标注证据" @click="openAnnotation(item)">
                          标注
                        </a-button>
                        <a v-if="item.source_url" :href="item.source_url" target="_blank" rel="noopener noreferrer">
                          原始链接
                        </a>
                      </a-space>
                    </div>
                    <a-list
                      v-if="item.annotations.length"
                      class="annotation-list"
                      size="small"
                      :data-source="item.annotations"
                    >
                      <template #renderItem="{ item: annotation }">
                        <a-list-item>
                          <div>
                            <a-tag :color="assessmentColor(annotation.assessment)">
                              {{ assessmentLabel(annotation.assessment) }}
                            </a-tag>
                            <span class="annotation-note">{{ annotation.note }}</span>
                            <div class="case-meta">
                              {{ annotation.created_by_name }} · {{ formatTime(annotation.created_at) }}
                            </div>
                          </div>
                        </a-list-item>
                      </template>
                    </a-list>
                  </article>
                  <a-empty
                    v-if="group.items.length === 0"
                    description="该分组暂无证据"
                    :image-style="{ height: '42px' }"
                  />
                </div>
              </a-tab-pane>
            </a-tabs>
          </a-card>

          <div class="decision-column">
            <a-card size="small" title="复核建议" class="side-card">
              <template v-if="currentCase.review_advisory">
                <a-space class="tag-row" :size="8" wrap>
                  <a-tag :color="conclusionColor(currentCase.review_advisory.conclusion)">
                    {{ conclusionLabel(currentCase.review_advisory.conclusion) }}
                  </a-tag>
                  <a-tag :color="urgencyColor(currentCase.review_advisory.urgency)">
                    {{ urgencyLabel(currentCase.review_advisory.urgency) }}
                  </a-tag>
                  <a-tag>{{ dispositionLabel(currentCase.review_advisory.disposition) }}</a-tag>
                </a-space>
                <p class="rationale">{{ advisoryNarrative(currentCase.review_advisory.conclusion) }}</p>
                <a-divider orientation="left">差异摘要</a-divider>
                <a-list size="small" :data-source="differenceLines">
                  <template #renderItem="{ item }">
                    <a-list-item>{{ item }}</a-list-item>
                  </template>
                </a-list>
              </template>
              <a-empty v-else description="暂无复核建议" :image-style="{ height: '42px' }" />
            </a-card>

            <a-card size="small" title="确认结论" class="side-card">
              <a-form v-if="!decisionLocked" layout="vertical" :disabled="savingDraft || confirming">
                <a-form-item label="确认结论" required>
                  <a-segmented
                    v-model:value="draftForm.conclusion"
                    :options="conclusionOptions"
                    aria-label="确认结论"
                  />
                </a-form-item>
                <a-form-item label="紧急程度" required>
                  <a-segmented
                    v-model:value="draftForm.urgency"
                    :options="urgencyOptions"
                    aria-label="紧急程度"
                  />
                </a-form-item>
                <a-form-item label="处置方式" required>
                  <a-select
                    v-model:value="draftForm.disposition"
                    :options="dispositionOptions"
                    aria-label="处置方式"
                  />
                </a-form-item>
                <a-form-item label="结论依据" required>
                  <a-textarea
                    v-model:value="draftForm.rationale"
                    :rows="4"
                    show-count
                    :maxlength="8000"
                    aria-label="结论依据"
                  />
                </a-form-item>
                <a-form-item label="关键证据">
                  <a-textarea
                    v-model:value="keyEvidenceInput"
                    :rows="2"
                    placeholder="每行一条证据引用…"
                    aria-label="关键证据"
                  />
                </a-form-item>
                <a-form-item label="待补事项">
                  <a-textarea
                    v-model:value="unresolvedInput"
                    :rows="2"
                    placeholder="每行一条待补事项…"
                    aria-label="待补事项"
                  />
                </a-form-item>
              </a-form>
              <template v-if="!decisionLocked">
                <a-alert
                  v-if="draftConflict"
                  class="draft-conflict"
                  type="error"
                  show-icon
                  message="草稿已被其他分析员更新"
                  description="请刷新案件后再继续编辑，避免覆盖他人的修改。"
                />
                <div class="draft-status" aria-live="polite">{{ draftStatusText }}</div>
                <a-space :size="8" wrap>
                  <a-button :disabled="!draftDirty || Boolean(draftConflict)" :loading="savingDraft" @click="saveDraftNow">
                    保存草稿
                  </a-button>
                  <a-button
                    type="primary"
                    danger
                    :disabled="!canConfirmDecision"
                    :loading="confirming"
                    @click="openConfirmDecision"
                  >
                    明确确认
                  </a-button>
                </a-space>
              </template>
              <a-descriptions v-else :column="1" size="small" bordered>
                <a-descriptions-item label="结论">
                  {{ conclusionLabel(currentCase.confirmed_decision!.conclusion) }}
                </a-descriptions-item>
                <a-descriptions-item label="紧迫度">
                  {{ urgencyLabel(currentCase.confirmed_decision!.urgency) }}
                </a-descriptions-item>
                <a-descriptions-item label="处置">
                  {{ dispositionLabel(currentCase.confirmed_decision!.disposition) }}
                </a-descriptions-item>
                <a-descriptions-item label="理由">
                  {{ currentCase.confirmed_decision!.rationale }}
                </a-descriptions-item>
              </a-descriptions>
              <a-alert
                v-if="currentCase.confirmed_decision"
                class="confirmed-alert"
                type="success"
                show-icon
                :message="`已确认：${conclusionLabel(currentCase.confirmed_decision.conclusion)}`"
                :description="`${currentCase.confirmed_decision.confirmed_by_name} · ${formatTime(currentCase.confirmed_decision.confirmed_at)}`"
              />
            </a-card>

            <a-card size="small" title="业务活动记录" class="side-card">
              <a-list
                size="small"
                :data-source="activities"
                :loading="activityLoading"
                class="activity-list"
              >
                <template #renderItem="{ item }">
                  <a-list-item>
                    <div class="activity-item">
                      <div class="activity-summary">{{ activityLabel(item.activity_type) }}</div>
                      <div class="case-meta">
                        {{ item.actor_name }} · {{ formatTime(item.occurred_at) }}
                      </div>
                    </div>
                  </a-list-item>
                </template>
              </a-list>
              <a-empty
                v-if="!activityLoading && activities.length === 0"
                description="暂无活动记录"
                :image-style="{ height: '42px' }"
              />
            </a-card>
          </div>
        </section>
      </template>
    </a-spin>

    <a-modal
      v-model:open="annotationOpen"
      title="标注证据"
      ok-text="保存标注"
      cancel-text="取消"
      :confirm-loading="annotationSaving"
      @ok="submitAnnotation"
    >
      <a-form layout="vertical">
        <a-form-item label="证据条目">
          <a-input :value="annotationTarget?.title" disabled aria-label="证据条目" />
        </a-form-item>
        <a-form-item label="证据关系" required>
          <a-select
            v-model:value="annotationForm.assessment"
            :options="assessmentOptions"
            aria-label="证据关系"
          />
        </a-form-item>
        <a-form-item label="标注说明" required>
          <a-textarea
            v-model:value="annotationForm.note"
            :rows="4"
            :maxlength="4000"
            show-count
            aria-label="标注说明"
          />
        </a-form-item>
        <a-form-item label="补充链接">
          <a-input v-model:value="annotationForm.source_url" allow-clear aria-label="补充链接" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="reviewRequestOpen"
      title="申请复核"
      ok-text="提交申请"
      cancel-text="取消"
      :confirm-loading="reviewRequestSaving"
      @ok="submitReviewRequest"
    >
      <a-form layout="vertical">
        <a-form-item label="复核原因" required>
          <a-textarea
            v-model:value="reviewRequestReason"
            :rows="4"
            :maxlength="4000"
            show-count
            aria-label="复核原因"
          />
        </a-form-item>
        <a-form-item label="关联证据">
          <a-select
            v-model:value="selectedEvidenceRefs"
            mode="multiple"
            :options="evidenceRefOptions"
            aria-label="关联证据"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Modal, message } from 'ant-design-vue'
import PageHeader from '@/components/PageHeader.vue'
import {
  annotateReviewCaseEvidence,
  confirmDecision,
  getLatestReviewCase,
  getReviewCase,
  getReviewCaseEvidence,
  listCaseActivities,
  readCaseEventStream,
  requestReviewAdvisory,
  saveDecisionDraft,
  searchReviewCases,
} from '@/api/reviewCases'
import type {
  CaseActivity,
  CaseActivityType,
  DecisionDraft,
  Disposition,
  EvidenceAssessment,
  EvidenceItem,
  EvidenceSufficiency,
  ReviewCaseDetail,
  ReviewCaseEvidence,
  ReviewCaseSummary,
  ReviewConclusion,
  ReviewUrgency,
} from '@/types/reviewCase'

type SelectOption = { label: string; value: string }
type EvidenceGroup = { key: EvidenceAssessment; label: string; items: EvidenceItem[] }

const route = useRoute()
const router = useRouter()

const currentCase = ref<ReviewCaseDetail | null>(null)
const evidence = ref<ReviewCaseEvidence | null>(null)
const caseItems = ref<ReviewCaseSummary[]>([])
const selectedCaseId = ref<string | undefined>()
const loading = ref(false)
const searching = ref(false)
const activityLoading = ref(false)
const activeEvidenceGroup = ref<EvidenceAssessment>('supports')
const selectedEvidenceRefs = ref<string[]>([])
const activities = ref<CaseActivity[]>([])
const activityCursor = ref(0)

const annotationOpen = ref(false)
const annotationSaving = ref(false)
const annotationTarget = ref<EvidenceItem | null>(null)
const annotationForm = reactive<{
  assessment: EvidenceAssessment
  note: string
  source_url: string
}>({
  assessment: 'supports',
  note: '',
  source_url: '',
})

const reviewRequestOpen = ref(false)
const reviewRequestSaving = ref(false)
const reviewRequestReason = ref('')

const savingDraft = ref(false)
const confirming = ref(false)
const draftVersion = ref(0)
const draftSavedAt = ref('')
const draftHydrating = ref(false)
const draftDirty = ref(false)
const draftConflict = ref('')
const draftEditRevision = ref(0)
const draftSaveTimer = ref<number | undefined>()
let draftSavePromise: Promise<DecisionDraft | null> | null = null
let caseSearchTimer: number | undefined
let caseSearchSequence = 0
let activityRecoveryTimer: number | undefined
let activityRecoveryController: AbortController | null = null
const draftForm = reactive<{
  conclusion: ReviewConclusion
  urgency: ReviewUrgency
  disposition: Disposition
  rationale: string
}>({
  conclusion: 'insufficient_evidence',
  urgency: 'watch',
  disposition: 'gather_evidence',
  rationale: '',
})
const keyEvidenceInput = ref('')
const unresolvedInput = ref('')

const conclusionLabels: Record<ReviewConclusion, string> = {
  harmful: '存在风险',
  non_harmful: '风险不成立',
  insufficient_evidence: '证据不足',
}

const sufficiencyLabels: Record<EvidenceSufficiency, string> = {
  sufficient: '充分',
  limited: '有限',
  insufficient: '不足',
}

const urgencyLabels: Record<ReviewUrgency, string> = {
  routine: '常规关注',
  watch: '持续观察',
  urgent: '需尽快处理',
  critical: '需立即处理',
}

const dispositionLabels: Record<Disposition, string> = {
  monitor: '继续监测',
  gather_evidence: '补充证据',
  escalate: '升级处置',
  respond: '对外回应',
  archive: '归档',
}

const assessmentLabels: Record<EvidenceAssessment, string> = {
  supports: '支持',
  contradicts: '反驳',
  irrelevant: '无关',
  unresolved: '待判定',
}

const activityLabels: Record<CaseActivityType, string> = {
  case_created: '建立复核条目',
  snapshot_added: '更新事件材料',
  evidence_annotated: '证据标注',
  evidence_requested: '请求补充证据',
  review_requested: '申请复核',
  review_advisory_available: '收到复核建议',
  decision_draft_saved: '保存草稿',
  decision_confirmed: '确认结论',
  correction_recorded: '记录修正',
  reconfirmation_required: '需要重新确认',
}

const conclusionOptions = typedOptions(conclusionLabels)
const urgencyOptions = typedOptions(urgencyLabels)
const dispositionOptions = typedOptions(dispositionLabels)
const assessmentOptions = typedOptions(assessmentLabels)

const caseOptions = computed<SelectOption[]>(() => {
  return caseItems.value.map((item) => ({
    label: item.title,
    value: item.case_id,
  }))
})

const evidenceGroups = computed<EvidenceGroup[]>(() => {
  const data = evidence.value
  return [
    { key: 'supports', label: '支持', items: data?.supports || [] },
    { key: 'contradicts', label: '反驳', items: data?.contradicts || [] },
    { key: 'irrelevant', label: '无关', items: data?.irrelevant || [] },
    { key: 'unresolved', label: '待判定', items: data?.unresolved || [] },
  ]
})

const allEvidenceItems = computed(() => evidenceGroups.value.flatMap((group) => group.items))

const evidenceRefOptions = computed<SelectOption[]>(() => {
  return allEvidenceItems.value.map((item) => ({
    label: item.title,
    value: item.evidence_ref,
  }))
})

const sufficiencyLines = computed(() => {
  if (!currentCase.value) return []
  if (currentCase.value.evidence_sufficiency === 'sufficient') {
    return ['现有材料覆盖多个来源，可支持当前研判结论。']
  }
  if (currentCase.value.evidence_sufficiency === 'limited') {
    return ['现有材料可支持初步研判，仍建议结合后续材料持续核验。']
  }
  return ['现有材料尚不足以形成明确结论，建议补充相关证据。']
})

const differenceLines = computed(() => {
  const advisory = currentCase.value?.review_advisory
  if (!advisory) return []
  const preliminary = currentCase.value?.preliminary_finding.conclusion
  return preliminary && preliminary !== advisory.conclusion
    ? ['复核结论与系统初判存在差异，请结合证据材料作出最终确认。']
    : ['复核结论与系统初判一致。']
})

const preliminaryNarrative = computed(() => {
  const conclusion = currentCase.value?.preliminary_finding.conclusion
  return conclusionNarrative(conclusion)
})

const visibleKeyCommunities = computed(() => {
  const communities = currentCase.value?.coordination_summary.key_communities || []
  return communities.slice(0, 3).map((_, index) => `协同群体 ${index + 1}`)
})

const allKeyAccounts = computed(() => {
  return (currentCase.value?.coordination_summary.key_accounts || []).filter((item) => {
    const value = String(item).trim()
    return Boolean(value) && !/^\d+$/.test(value)
  })
})

const visibleKeyAccounts = computed(() => allKeyAccounts.value.slice(0, 5))

const hiddenKeyAccountCount = computed(() => Math.max(0, allKeyAccounts.value.length - visibleKeyAccounts.value.length))

const coordinationNarrative = computed(() => {
  if (allKeyAccounts.value.length) {
    return '已识别出需要持续关注的协同行为线索。'
  }
  if (visibleKeyCommunities.value.length) {
    return '已识别出需要继续核验的协同群体。'
  }
  return '当前未发现需要重点关注的协同行为线索。'
})

const decisionLocked = computed(() => {
  return Boolean(
    currentCase.value?.confirmed_decision
    && currentCase.value.action_required !== 'reconfirm_decision',
  )
})

const canConfirmDecision = computed(() => {
  return Boolean(
    currentCase.value
    && !decisionLocked.value
    && !draftConflict.value
    && !savingDraft.value
    && !confirming.value
    && draftForm.rationale.trim(),
  )
})

const draftStatusText = computed(() => {
  if (draftConflict.value) return '草稿存在版本冲突，请刷新案件'
  if (savingDraft.value) return '草稿正在保存'
  if (draftDirty.value) return '有尚未保存的修改'
  if (draftSavedAt.value) return `草稿已保存：${formatTime(draftSavedAt.value)}`
  return '草稿尚未保存'
})

watch(
  () => [
    draftForm.conclusion,
    draftForm.urgency,
    draftForm.disposition,
    draftForm.rationale,
    keyEvidenceInput.value,
    unresolvedInput.value,
  ],
  () => {
    if (!draftHydrating.value && currentCase.value && !decisionLocked.value) {
      draftDirty.value = true
      draftConflict.value = ''
      draftEditRevision.value += 1
      scheduleDraftSave()
    }
  },
)

function typedOptions<T extends string>(labels: Record<T, string>) {
  return Object.entries(labels).map(([value, label]) => ({ value, label })) as Array<{ value: T; label: string }>
}

function handleCaseSearch(value: string) {
  if (caseSearchTimer) window.clearTimeout(caseSearchTimer)
  caseSearchTimer = window.setTimeout(() => {
    void loadCaseOptions(value)
  }, 250)
}

async function handleCaseChange(value: string | undefined) {
  if (!value) return
  await loadCase(value)
}

async function loadCaseOptions(query = '') {
  const requestSequence = ++caseSearchSequence
  searching.value = true
  try {
    const res = await searchReviewCases({ query, limit: 20 })
    if (requestSequence === caseSearchSequence) {
      caseItems.value = res.data.items
    }
  } finally {
    if (requestSequence === caseSearchSequence) {
      searching.value = false
    }
  }
}

async function refreshCurrentCase() {
  if (currentCase.value) {
    await loadCase(currentCase.value.case_id)
  } else {
    await loadInitialCase()
  }
}

async function loadInitialCase() {
  const linkedCaseId = queryText(route.query.case_id)
  const linkedEventId = queryText(route.query.event_id)
  if (linkedCaseId) {
    await loadCase(linkedCaseId)
    return
  }
  if (linkedEventId) {
    await loadCaseOptions(linkedEventId)
    const matched = caseItems.value.find((item) => item.event_id === linkedEventId)
    if (matched) {
      await loadCase(matched.case_id)
      return
    }
    currentCase.value = null
    evidence.value = null
    message.warning('未找到对应事件')
    return
  }
  loading.value = true
  try {
    const res = await getLatestReviewCase()
    await applyCase(res.data)
    await loadCaseOptions('')
  } catch {
    currentCase.value = null
    evidence.value = null
  } finally {
    loading.value = false
  }
}

async function loadCase(caseId: string) {
  loading.value = true
  try {
    const [detailRes, evidenceRes] = await Promise.all([
      getReviewCase(caseId),
      getReviewCaseEvidence(caseId),
    ])
    await applyCase(detailRes.data, evidenceRes.data)
  } finally {
    loading.value = false
  }
}

async function applyCase(detail: ReviewCaseDetail, evidenceData?: ReviewCaseEvidence) {
  currentCase.value = detail
  selectedCaseId.value = detail.case_id
  evidence.value = evidenceData || null
  selectedEvidenceRefs.value = []
  hydrateDraft(detail)
  void router.replace({
    query: {
      ...route.query,
      case_id: detail.case_id,
      event_id: detail.event_id,
    },
  })
  if (!evidenceData) {
    const res = await getReviewCaseEvidence(detail.case_id)
    evidence.value = res.data
  }
  await loadActivities(detail.case_id)
  startActivityRecovery(detail.case_id)
}

function hydrateDraft(detail: ReviewCaseDetail) {
  draftHydrating.value = true
  const serverDraft = detail.decision_draft
  if (serverDraft) {
    draftForm.conclusion = serverDraft.conclusion
    draftForm.urgency = serverDraft.urgency
    draftForm.disposition = serverDraft.disposition
    draftForm.rationale = serverDraft.rationale
    keyEvidenceInput.value = serverDraft.key_evidence_refs.join('\n')
    unresolvedInput.value = serverDraft.unresolved_items.join('\n')
  } else if (detail.confirmed_decision) {
    draftForm.conclusion = detail.confirmed_decision.conclusion
    draftForm.urgency = detail.confirmed_decision.urgency
    draftForm.disposition = detail.confirmed_decision.disposition
    draftForm.rationale = detail.confirmed_decision.rationale
    keyEvidenceInput.value = detail.confirmed_decision.key_evidence_refs.join('\n')
    unresolvedInput.value = detail.confirmed_decision.unresolved_items.join('\n')
  } else if (detail.review_advisory) {
    draftForm.conclusion = detail.review_advisory.conclusion
    draftForm.urgency = detail.review_advisory.urgency
    draftForm.disposition = detail.review_advisory.disposition
    draftForm.rationale = advisoryNarrative(detail.review_advisory.conclusion)
    keyEvidenceInput.value = detail.review_advisory.key_evidence_refs.join('\n')
    unresolvedInput.value = detail.missing_evidence.join('\n')
  } else {
    draftForm.conclusion = detail.preliminary_finding.conclusion
    draftForm.urgency = detail.urgency
    draftForm.disposition = detail.disposition
    draftForm.rationale = conclusionNarrative(detail.preliminary_finding.conclusion)
    keyEvidenceInput.value = detail.preliminary_finding.key_evidence_refs.join('\n')
    unresolvedInput.value = detail.missing_evidence.join('\n')
  }
  draftVersion.value = serverDraft?.draft_version || 0
  draftSavedAt.value = serverDraft?.saved_at || ''
  draftConflict.value = ''
  draftDirty.value = !decisionLocked.value && !serverDraft
  window.setTimeout(() => {
    draftHydrating.value = false
    if (draftDirty.value) scheduleDraftSave()
  }, 0)
}

async function loadActivities(caseId: string) {
  activityLoading.value = true
  try {
    const res = await listCaseActivities(caseId, { limit: 100 })
    activities.value = res.data.items
    activityCursor.value = res.data.next_cursor || 0
  } finally {
    activityLoading.value = false
  }
}

function startActivityRecovery(caseId: string) {
  if (activityRecoveryTimer) window.clearInterval(activityRecoveryTimer)
  activityRecoveryController?.abort()
  activityRecoveryTimer = window.setInterval(() => {
    void recoverCaseActivities(caseId)
  }, 10000)
}

async function recoverCaseActivities(caseId: string) {
  if (currentCase.value?.case_id !== caseId || activityRecoveryController) return
  const controller = new AbortController()
  activityRecoveryController = controller
  try {
    const events = await readCaseEventStream(caseId, activityCursor.value, controller.signal)
    if (events.length === 0) return
    const response = await listCaseActivities(caseId, {
      after_id: activityCursor.value,
      limit: 100,
    })
    const known = new Set(activities.value.map((item) => item.cursor))
    activities.value.push(...response.data.items.filter((item) => !known.has(item.cursor)))
    activityCursor.value = response.data.next_cursor || activityCursor.value

    const detail = await getReviewCase(caseId)
    if (currentCase.value?.case_id === caseId) {
      const localDraft = currentCase.value.decision_draft
      currentCase.value = detail.data
      if (draftDirty.value || savingDraft.value) {
        currentCase.value.decision_draft = localDraft
      } else {
        hydrateDraft(detail.data)
      }
    }

    if (events.some((item) => ['snapshot_added', 'reconfirmation_required'].includes(item.activity_type))) {
      const evidenceResponse = await getReviewCaseEvidence(caseId)
      evidence.value = evidenceResponse.data
    }
  } catch (error) {
    if ((error as { name?: string }).name !== 'AbortError') {
    }
  } finally {
    if (activityRecoveryController === controller) activityRecoveryController = null
  }
}

function toggleEvidenceRef(evidenceRef: string) {
  selectedEvidenceRefs.value = selectedEvidenceRefs.value.includes(evidenceRef)
    ? selectedEvidenceRefs.value.filter((item) => item !== evidenceRef)
    : [...selectedEvidenceRefs.value, evidenceRef]
}

function openAnnotation(item: EvidenceItem) {
  annotationTarget.value = item
  annotationForm.assessment = item.assessment
  annotationForm.note = ''
  annotationForm.source_url = item.source_url || ''
  annotationOpen.value = true
}

async function submitAnnotation() {
  if (!currentCase.value || !annotationTarget.value) return
  if (!annotationForm.note.trim()) {
    message.warning('请填写标注说明')
    return
  }
  if (!(await flushDraftBeforeCaseMutation())) return
  annotationSaving.value = true
  try {
    await annotateReviewCaseEvidence(currentCase.value.case_id, {
      evidence_ref: annotationTarget.value.evidence_ref,
      assessment: annotationForm.assessment,
      note: annotationForm.note.trim(),
      source_url: annotationForm.source_url.trim() || null,
    })
    annotationOpen.value = false
    message.success('证据标注已保存')
    await loadCase(currentCase.value.case_id)
  } finally {
    annotationSaving.value = false
  }
}

function openReviewRequest() {
  reviewRequestReason.value = ''
  reviewRequestOpen.value = true
}

async function submitReviewRequest() {
  if (!currentCase.value) return
  if (!reviewRequestReason.value.trim()) {
    message.warning('请填写复核原因')
    return
  }
  if (!(await flushDraftBeforeCaseMutation())) return
  reviewRequestSaving.value = true
  try {
    await requestReviewAdvisory(currentCase.value.case_id, {
      reason: reviewRequestReason.value.trim(),
      evidence_refs: selectedEvidenceRefs.value,
    })
    reviewRequestOpen.value = false
    message.success('复核申请已提交')
    await loadCase(currentCase.value.case_id)
  } finally {
    reviewRequestSaving.value = false
  }
}

function scheduleDraftSave() {
  if (draftSaveTimer.value) {
    window.clearTimeout(draftSaveTimer.value)
  }
  draftSaveTimer.value = window.setTimeout(() => {
    void saveDraftNow({ silent: true })
  }, 1200)
}

async function saveDraftNow(options: { silent?: boolean } = {}): Promise<DecisionDraft | null> {
  if (!currentCase.value || decisionLocked.value || !draftForm.rationale.trim()) return null
  if (draftSaveTimer.value) {
    window.clearTimeout(draftSaveTimer.value)
    draftSaveTimer.value = undefined
  }
  if (draftSavePromise) await draftSavePromise
  if (!draftDirty.value && draftVersion.value > 0) return currentCase.value.decision_draft

  const editRevision = draftEditRevision.value
  const caseId = currentCase.value.case_id
  const payload = {
    conclusion: draftForm.conclusion,
    urgency: draftForm.urgency,
    disposition: draftForm.disposition,
    rationale: draftForm.rationale.trim(),
    key_evidence_refs: splitLines(keyEvidenceInput.value),
    unresolved_items: splitLines(unresolvedInput.value),
    expected_version: draftVersion.value,
  }

  savingDraft.value = true
  draftSavePromise = saveDecisionDraft(caseId, payload)
    .then((res) => {
      applyDraftReceipt(res.data)
      if (draftEditRevision.value === editRevision) {
        draftDirty.value = false
      } else {
        scheduleDraftSave()
      }
      if (!options.silent) message.success('草稿已保存')
      return res.data
    })
    .catch((error: unknown) => {
      if (isConflictError(error)) {
        draftConflict.value = 'version_conflict'
        message.warning('草稿已被其他分析员更新，请刷新案件后继续')
      }
      return null
    })

  try {
    return await draftSavePromise
  } finally {
    draftSavePromise = null
    savingDraft.value = false
  }
}

function applyDraftReceipt(draft: DecisionDraft) {
  draftVersion.value = draft.draft_version
  draftSavedAt.value = draft.saved_at
  if (currentCase.value) currentCase.value.decision_draft = draft
}

async function flushDraftBeforeCaseMutation() {
  if (decisionLocked.value || (!draftDirty.value && draftVersion.value > 0)) return true
  return Boolean(await saveDraftNow({ silent: true }))
}

function openConfirmDecision() {
  Modal.confirm({
    title: '确认提交当前结论？',
    content: '提交后将形成不可变更的确认结论。后续如有新证据，需要重新确认。',
    okText: '明确确认',
    cancelText: '再检查',
    okButtonProps: { danger: true },
    onOk: submitDecisionConfirmation,
  })
}

async function submitDecisionConfirmation() {
  if (!currentCase.value || decisionLocked.value || draftConflict.value) return
  confirming.value = true
  try {
    while (draftDirty.value || draftVersion.value === 0) {
      const saved = await saveDraftNow({ silent: true })
      if (!saved) return
    }
    await confirmDecision(currentCase.value.case_id, {
      expected_draft_version: draftVersion.value,
      confirmation_note: '已完成业务复核并确认结论。',
    })
    message.success('确认结论已提交')
    await loadCase(currentCase.value.case_id)
  } finally {
    confirming.value = false
  }
}

function queryText(value: unknown) {
  return Array.isArray(value) ? String(value[0] || '') : String(value || '')
}

function isConflictError(error: unknown) {
  return Number((error as { response?: { status?: number } })?.response?.status) === 409
}

function splitLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function conclusionLabel(value: ReviewConclusion) {
  return conclusionLabels[value]
}

function conclusionNarrative(value: ReviewConclusion | undefined) {
  if (value === 'harmful') return '现有材料显示该事件存在需要持续关注的风险线索。'
  if (value === 'non_harmful') return '现有材料未显示需要进一步处置的明确风险。'
  return '现有材料尚不足以形成明确结论，建议继续补充相关证据。'
}

function advisoryNarrative(value: ReviewConclusion) {
  if (value === 'harmful') return '复核结果提示该事件存在需要进一步处置的风险线索。'
  if (value === 'non_harmful') return '复核结果未发现需要进一步处置的明确风险。'
  return '复核结果认为当前材料仍需结合更多证据进行判断。'
}

function sufficiencyLabel(value: EvidenceSufficiency) {
  return sufficiencyLabels[value]
}

function urgencyLabel(value: ReviewUrgency) {
  return urgencyLabels[value]
}

function dispositionLabel(value: Disposition) {
  return dispositionLabels[value]
}

function assessmentLabel(value: EvidenceAssessment) {
  return assessmentLabels[value]
}

function activityLabel(value: CaseActivityType) {
  return activityLabels[value]
}

function evidenceTypeLabel(value: string) {
  return value === 'comment' ? '评论' : value === 'post' ? '帖文' : '其他材料'
}

function conclusionColor(value: ReviewConclusion) {
  return value === 'harmful' ? 'red' : value === 'non_harmful' ? 'green' : 'gold'
}

function urgencyColor(value: ReviewUrgency) {
  if (value === 'critical') return 'red'
  if (value === 'urgent') return 'orange'
  if (value === 'watch') return 'gold'
  return 'blue'
}

function assessmentColor(value: EvidenceAssessment) {
  if (value === 'supports') return 'green'
  if (value === 'contradicts') return 'red'
  if (value === 'irrelevant') return 'default'
  return 'gold'
}

function formatTime(value?: string | null) {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => {
  void loadInitialCase()
})

onBeforeUnmount(() => {
  if (draftSaveTimer.value) {
    window.clearTimeout(draftSaveTimer.value)
  }
  if (caseSearchTimer) window.clearTimeout(caseSearchTimer)
  if (activityRecoveryTimer) window.clearInterval(activityRecoveryTimer)
  activityRecoveryController?.abort()
})
</script>

<style scoped>
.review-page {
  color: #1f2329;
}

.selector-bar {
  align-items: center;
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 8px;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  margin-bottom: 16px;
  padding: 14px 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.section-subtitle {
  color: #86909c;
  font-size: 12px;
  margin: 4px 0 0;
}

.selector-actions {
  justify-content: flex-end;
}

.case-select {
  width: min(460px, 58vw);
}

.empty-state {
  background: #fff;
  border-radius: 8px;
  padding: 80px 0;
}

.summary-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(320px, 1.2fr) repeat(2, minmax(220px, 1fr));
  margin-bottom: 16px;
}

.summary-card {
  min-height: 224px;
}

.case-title {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  margin-bottom: 8px;
}

.case-meta {
  color: #86909c;
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 8px;
  line-height: 1.5;
}

.preliminary-status {
  border-left: 3px solid #d9d9d9;
  margin-top: 16px;
  padding: 4px 0 4px 12px;
}

.preliminary-status.is-harmful {
  border-left-color: #cf1322;
}

.preliminary-status.is-non_harmful {
  border-left-color: #389e0d;
}

.preliminary-status.is-insufficient_evidence {
  border-left-color: #d48806;
}

.preliminary-title {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
}

.preliminary-status p {
  color: #4e5969;
  line-height: 1.65;
  margin: 4px 0 0;
}

.summary-meta {
  color: #86909c;
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 6px;
  line-height: 1.6;
  margin-top: 16px;
}

.tag-row {
  margin: 12px 0;
}

.rationale {
  line-height: 1.7;
  margin: 8px 0 12px;
  white-space: pre-wrap;
}

.mini-list {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.mini-label {
  color: #4e5969;
  font-size: 12px;
  font-weight: 600;
}

.focus-label {
  color: #1d39c4;
  font-size: 13px;
  line-height: 1.5;
}

.muted {
  color: #86909c;
  font-size: 12px;
}

.workspace-grid {
  align-items: start;
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(560px, 1fr) minmax(360px, 420px);
}

.evidence-panel,
.side-card {
  border-radius: 8px;
}

.decision-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 4px;
}

.evidence-item {
  border: 1px solid #eef0f4;
  border-radius: 8px;
  padding: 12px;
}

.evidence-heading {
  align-items: flex-start;
  display: grid;
  gap: 10px;
  grid-template-columns: auto 1fr;
}

.evidence-heading h4 {
  font-size: 14px;
  line-height: 1.45;
  margin: 0 0 4px;
}

.evidence-excerpt {
  background: #f7f8fa;
  border-radius: 6px;
  line-height: 1.7;
  margin: 10px 0;
  padding: 10px;
  white-space: pre-wrap;
  word-break: break-word;
}

.evidence-footer {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.annotation-list {
  margin-top: 8px;
}

.annotation-note {
  margin-left: 6px;
}

.draft-status {
  color: #4e5969;
  font-size: 12px;
  margin: 0 0 12px;
  min-height: 20px;
}

.confirmed-alert {
  margin-top: 12px;
}

.activity-list {
  width: 100%;
}

.activity-item {
  width: 100%;
}

.activity-summary {
  font-weight: 600;
  line-height: 1.5;
}

@media (max-width: 1280px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(280px, 1fr));
  }

  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .case-select {
    width: min(420px, 70vw);
  }
}
</style>
