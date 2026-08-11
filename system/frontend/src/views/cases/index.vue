<template>
  <div class="case-page">
    <PageHeader title="案例闭环" description="围绕案例完成事件、证据、协同、传播、研判、处置和反馈闭环展示" />

    <div class="case-toolbar">
      <a-input
        v-model:value="eventId"
        class="event-input"
        allow-clear
        placeholder="trump_visit_2026_05_21"
        @pressEnter="loadCase"
      />
      <a-button type="primary" :loading="loading" @click="loadCase">刷新案例</a-button>
      <a-button @click="drawerOpen = true">证据下钻</a-button>
    </div>

    <a-alert
      v-if="errorText"
      class="case-alert"
      type="warning"
      show-icon
      :message="errorText"
    />

    <section v-if="caseDetail" class="case-context-bar">
      <div class="case-title-block">
        <div class="case-title-row">
          <h2>{{ caseDetail.title }}</h2>
          <a-tag :color="stateColor(caseDetail.state)">{{ caseDetail.state }}</a-tag>
          <a-tag>{{ caseDetail.event_id }}</a-tag>
        </div>
        <p>{{ caseDetail.workflow_summary.closed_loop || '事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈' }}</p>
      </div>
      <div class="case-claim-block">
        <span class="eyebrow">主核心主张</span>
        <strong>{{ caseDetail.primary_claim?.excerpt || '待审批' }}</strong>
        <small>
          {{ caseDetail.primary_claim?.source?.name || '-' }}
          · {{ caseDetail.primary_claim?.source?.tier || '-' }}
        </small>
        <a-space size="small">
          <a-tag color="orange">{{ caseDetail.primary_claim?.status || 'candidate_unvalidated' }}</a-tag>
          <a-tag>{{ caseDetail.primary_claim?.source?.status || 'unverified' }}</a-tag>
        </a-space>
      </div>
      <div class="case-blocker-block">
        <span class="eyebrow">阻塞项</span>
        <template v-if="caseDetail.active_blockers.length">
          <div v-for="item in caseDetail.active_blockers" :key="item.blocker_id" class="blocker-row">
            <a-tag color="orange">{{ item.code }}</a-tag>
            <span>{{ item.message }}</span>
            <a-button
              v-if="item.code === 'platform_gap'"
              size="small"
              type="primary"
              :disabled="caseDetail.state === 'closed'"
              :loading="savingBlockerId === item.blocker_id"
              @click="acknowledgeCaseBlocker(item.blocker_id)"
            >
              确认平台缺口继续
            </a-button>
          </div>
        </template>
        <a-tag v-else color="green">无活动阻塞</a-tag>
        <div v-if="caseDetail.blocker_acknowledgements?.length" class="blocker-acknowledgements">
          <span v-for="item in caseDetail.blocker_acknowledgements" :key="item.acknowledgement_id">
            {{ item.actor_id }}: {{ item.reason }}
          </span>
        </div>
      </div>
    </section>

    <a-card v-if="!caseDetail && loading" size="small" class="loading-card">
      <a-spin tip="正在加载案例闭环..." />
    </a-card>

    <template v-if="caseDetail">
      <div class="lifecycle-strip">
        <div
          v-for="step in caseDetail.lifecycle"
          :key="step.key"
          :class="['lifecycle-step', step.status]"
        >
          <span>{{ step.label }}</span>
        </div>
      </div>

      <a-tabs v-model:activeKey="activeTab" class="case-tabs">
        <a-tab-pane key="overview" tab="概览">
          <div class="overview-grid">
            <section class="panel">
              <div class="panel-title">事件证据</div>
              <a-descriptions size="small" :column="2" bordered>
                <a-descriptions-item label="Snapshot">{{ caseDetail.evidence.snapshot_id }}</a-descriptions-item>
                <a-descriptions-item label="Fingerprint">{{ compactHash(caseDetail.evidence.data_fingerprint) }}</a-descriptions-item>
                <a-descriptions-item label="帖子">{{ caseDetail.evidence.posts || 0 }}</a-descriptions-item>
                <a-descriptions-item label="评论">{{ caseDetail.evidence.comments || 0 }}</a-descriptions-item>
                <a-descriptions-item label="平台">{{ caseDetail.platforms.join(', ') || '-' }}</a-descriptions-item>
                <a-descriptions-item label="预期平台">{{ caseDetail.expected_platforms.join(', ') }}</a-descriptions-item>
              </a-descriptions>
            </section>
            <section class="panel">
              <div class="panel-title">分析运行</div>
              <a-table
                size="small"
                :columns="runColumns"
                :data-source="caseDetail.analysis_runs"
                row-key="run_id"
                :pagination="false"
              />
            </section>
          </div>
        </a-tab-pane>

        <a-tab-pane key="evidence" tab="证据矩阵">
          <div class="matrix-grid">
            <section class="panel">
              <div class="panel-title">权威主张</div>
              <a-table
                size="small"
                :columns="claimColumns"
                :data-source="claimRows"
                row-key="claim_id"
                :pagination="false"
              />
            </section>
            <section class="panel">
              <div class="panel-title">语义辅助</div>
              <a-space wrap class="semantic-tags">
                <a-tag color="blue">{{ semanticStatus }}</a-tag>
                <a-tag color="orange">candidate_unvalidated</a-tag>
                <a-tag>证据叠加，不改风险分</a-tag>
              </a-space>
              <div class="semantic-section">
                <h3>关键词</h3>
                <a-tag v-for="item in topKeywords" :key="item.term">{{ item.term }} {{ item.count }}</a-tag>
              </div>
              <div class="semantic-section">
                <h3>主题</h3>
                <div v-for="item in topicItems" :key="item.topic_id" class="topic-row">
                  <strong>{{ item.label }}</strong>
                  <span>{{ item.size }} 条 · {{ (item.keywords || []).join(', ') }}</span>
                </div>
              </div>
              <div class="semantic-section">
                <h3>实体</h3>
                <a-tag v-for="item in entityItems" :key="item.entity">{{ item.entity }}</a-tag>
              </div>
              <div class="semantic-section">
                <h3>Sentiment</h3>
                <div v-if="sentimentEntries.length" class="semantic-stat-row">
                  <a-statistic
                    v-for="item in sentimentEntries"
                    :key="item.label"
                    :title="item.label"
                    :value="item.value"
                  />
                </div>
                <span v-else class="semantic-empty">No sentiment distribution available.</span>
              </div>
              <div class="semantic-section">
                <h3>Stance</h3>
                <a-space v-if="stanceSummary" wrap>
                  <a-tag :color="stanceSummary.status === 'ok' ? 'blue' : 'default'">
                    {{ stanceSummary.status || 'unknown' }}
                  </a-tag>
                  <a-tag v-for="item in stanceEntries" :key="item.label">
                    {{ item.label }} {{ item.value }}
                  </a-tag>
                </a-space>
                <span v-else class="semantic-empty">No stance assessment available.</span>
              </div>
              <div class="semantic-section">
                <h3>Community comparison</h3>
                <div v-if="communityItems.length" class="compact-list">
                  <div v-for="item in communityItems" :key="item.community_id" class="topic-row">
                    <strong>{{ item.community_id }}</strong>
                    <span>{{ item.texts }} texts · {{ (item.top_keywords || []).join(', ') || '-' }}</span>
                  </div>
                </div>
                <span v-else class="semantic-empty">No community comparison available.</span>
              </div>
              <div class="semantic-section">
                <h3>Near duplicates</h3>
                <div v-if="nearDuplicateGroups.length" class="compact-list">
                  <div v-for="item in nearDuplicateGroups" :key="item.group_id" class="topic-row">
                    <strong>{{ item.group_id }} · {{ item.size }}</strong>
                    <span>{{ item.representative_text || '-' }}</span>
                  </div>
                </div>
                <span v-else class="semantic-empty">No near-duplicate groups available.</span>
              </div>
            </section>
          </div>
        </a-tab-pane>

        <a-tab-pane key="graph" tab="图谱">
          <section class="panel graph-panel">
            <div class="panel-title">协调与传播证据图谱</div>
            <div class="graph-summary">
              <a-statistic title="节点" :value="graphNodes.length" />
              <a-statistic title="边" :value="graphEdges.length" />
              <a-statistic title="来源" :value="caseDetail.graph.provenance || '-'" />
            </div>
            <div class="node-list">
              <a-tag v-for="node in graphNodes" :key="node.id">{{ node.label || node.id }}</a-tag>
            </div>
          </section>
        </a-tab-pane>

        <a-tab-pane key="actions" tab="处置">
          <section class="panel">
            <div class="panel-title">处置与反馈</div>
            <a-table
              size="small"
              :columns="actionColumns"
              :data-source="caseDetail.actions"
              row-key="action_id"
              :pagination="false"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'status'">
                  <a-tag :color="actionStatusColor(record.status)">{{ record.status }}</a-tag>
                </template>
                <template v-else-if="column.key === 'actions'">
                  <a-space>
                    <a-button
                      size="small"
                      type="primary"
                      :disabled="caseDetail.state === 'closed' || record.status === 'completed'"
                      :loading="savingActionId === record.action_id"
                      @click="completeCaseAction(record.action_id)"
                    >
                      标记完成
                    </a-button>
                    <a-button
                      size="small"
                      :disabled="caseDetail.state === 'closed' || record.status === 'waived'"
                      @click="waiveCaseAction(record.action_id)"
                    >
                      豁免
                    </a-button>
                  </a-space>
                </template>
              </template>
            </a-table>

            <div class="feedback-panel">
              <a-textarea v-model:value="feedbackText" :disabled="caseDetail.state === 'closed'" :rows="3" placeholder="记录人工反馈" />
              <a-button type="primary" :disabled="caseDetail.state === 'closed'" :loading="savingFeedback" @click="submitCaseFeedback">提交反馈</a-button>
            </div>

            <div class="feedback-list" v-if="caseDetail.feedback.length">
              <div v-for="item in caseDetail.feedback" :key="item.feedback_id" class="feedback-item">
                <strong>{{ item.actor_id }}</strong>
                <span>{{ formatTime(item.created_at) }}</span>
                <p>{{ item.content }}</p>
              </div>
            </div>

            <div class="feedback-panel">
              <a-textarea v-model:value="closeoutSummary" :disabled="caseDetail.state === 'closed'" :rows="3" placeholder="提交结案复核说明" />
              <a-button
                :disabled="caseDetail.state !== 'ready_to_close'"
                :loading="savingCloseout"
                @click="submitCaseCloseoutReview"
              >
                提交结案复核
              </a-button>
            </div>
            <a-alert
              v-if="caseDetail.closeout_review"
              class="case-alert"
              type="success"
              show-icon
              :message="`结案复核已提交：${caseDetail.closeout_review.summary}`"
            />
          </section>
        </a-tab-pane>

        <a-tab-pane key="reports" tab="报告">
          <section class="panel reports-panel">
            <div class="panel-title">冻结报告版本</div>
            <a-table
              size="small"
              :columns="reportColumns"
              :data-source="caseDetail.reports"
              row-key="version"
              :pagination="false"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'actions'">
                  <a-space>
                    <a-button size="small" :disabled="!record.html_url" @click="openReport(record.html_url)">预览</a-button>
                    <a-button size="small" :disabled="!record.pdf_url" @click="openReport(record.pdf_url)">PDF</a-button>
                  </a-space>
                </template>
                <template v-else-if="column.key === 'hash'">
                  {{ compactHash(record.content_hash) }}
                </template>
              </template>
            </a-table>
          </section>
        </a-tab-pane>
      </a-tabs>

      <a-drawer v-model:open="drawerOpen" title="EvidenceDrawer" width="560">
        <a-list :data-source="caseDetail.evidence.recent_posts || []" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <div class="drawer-post">
                <div>
                  <a-tag>{{ item.platform }}</a-tag>
                  <strong>{{ item.author_name || '-' }}</strong>
                  <span>{{ formatTime(item.timestamp) }}</span>
                </div>
                <p>{{ item.content }}</p>
              </div>
            </a-list-item>
          </template>
        </a-list>
      </a-drawer>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import PageHeader from '@/components/PageHeader.vue'
import {
  acknowledgeCaseBlocker as acknowledgeCaseBlockerRequest,
  completeCaseAction as completeCaseActionRequest,
  fetchCaseReport as fetchCaseReportRequest,
  getCase,
  listCases,
  submitCaseCloseoutReview as submitCaseCloseoutReviewRequest,
  submitCaseFeedback as submitCaseFeedbackRequest,
  waiveCaseAction as waiveCaseActionRequest,
} from '@/api/cases'
import type { CaseClaim, CaseDetail, SemanticDistribution } from '@/types/case'

const DEFAULT_EVENT_ID = 'trump_visit_2026_05_21'

const eventId = ref(DEFAULT_EVENT_ID)
const caseDetail = ref<CaseDetail | null>(null)
const activeTab = ref('overview')
const loading = ref(false)
const errorText = ref('')
const drawerOpen = ref(false)
const feedbackText = ref('')
const closeoutSummary = ref('')
const savingActionId = ref('')
const savingFeedback = ref(false)
const savingCloseout = ref(false)
const savingBlockerId = ref('')

const claimRows = computed<CaseClaim[]>(() => {
  if (!caseDetail.value) return []
  return [
    ...(caseDetail.value.primary_claim ? [caseDetail.value.primary_claim] : []),
    ...caseDetail.value.supplementary_claims,
  ]
})
const semanticArtifact = computed(() => caseDetail.value?.semantic_artifacts?.[0] || null)
const semanticStatus = computed(() => semanticArtifact.value?.status || 'not_run')
const topKeywords = computed<any[]>(() => semanticArtifact.value?.summary?.top_keywords || [])
const topicItems = computed<any[]>(() => semanticArtifact.value?.summary?.topics?.items || [])
const entityItems = computed<any[]>(() => semanticArtifact.value?.summary?.entities || [])
const sentimentEntries = computed(() => distributionEntries(semanticArtifact.value?.summary?.sentiment?.distribution))
const stanceSummary = computed(() => semanticArtifact.value?.summary?.stance || null)
const stanceEntries = computed(() => distributionEntries(semanticArtifact.value?.summary?.stance?.distribution))
const communityItems = computed(() => semanticArtifact.value?.summary?.community_comparison?.items || [])
const nearDuplicateGroups = computed(() => semanticArtifact.value?.summary?.near_duplicates || [])
const graphNodes = computed<any[]>(() => caseDetail.value?.graph?.nodes || [])
const graphEdges = computed<any[]>(() => caseDetail.value?.graph?.edges || [])

const runColumns = [
  { title: 'Run', dataIndex: 'run_id', key: 'run_id' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '阶段', dataIndex: 'requested_stages', key: 'requested_stages', customRender: ({ text }: { text: string[] }) => text?.join(', ') || '-' },
]

const claimColumns = [
  { title: 'Claim verification', dataIndex: 'status', key: 'status' },
  { title: 'Source verification', key: 'source_status', customRender: ({ record }: { record: CaseClaim }) => record.source?.status || 'unverified' },
  { title: '角色', dataIndex: 'role', key: 'role' },
  { title: '来源', key: 'source', customRender: ({ record }: { record: CaseClaim }) => `${record.source?.name || '-'} · ${record.source?.tier || '-'}` },
  { title: '原句', dataIndex: 'excerpt', key: 'excerpt' },
  { title: 'Hash', dataIndex: 'excerpt_hash', key: 'excerpt_hash', customRender: ({ text }: { text: string }) => compactHash(text) },
]

const actionColumns = [
  { title: '处置项', dataIndex: 'title', key: 'title' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '负责人', dataIndex: 'assignee', key: 'assignee' },
  { title: '操作', key: 'actions' },
]

const reportColumns = [
  { title: '版本', dataIndex: 'version', key: 'version' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '内容 Hash', key: 'hash' },
  { title: '操作', key: 'actions' },
]

async function loadCase() {
  loading.value = true
  errorText.value = ''
  try {
    const list = await listCases({ event_id: eventId.value.trim() || DEFAULT_EVENT_ID })
    const first = list.data.items?.[0]
    if (!first) {
      caseDetail.value = null
      errorText.value = '未找到匹配案例'
      return
    }
    const targetId = first.case_id
    const detail = await getCase(targetId)
    caseDetail.value = detail.data
  } catch (error: any) {
    errorText.value = error?.message || '案例加载失败'
    message.warning(errorText.value)
  } finally {
    loading.value = false
  }
}

function stateColor(state?: string) {
  return ({
    draft: 'default',
    collecting: 'processing',
    evidence_ready: 'blue',
    analyzing: 'purple',
    awaiting_review: 'orange',
    actioning: 'gold',
    ready_to_close: 'cyan',
    closed: 'green',
  } as Record<string, string>)[state || ''] || 'default'
}

function actionStatusColor(status?: string) {
  return ({
    required: 'orange',
    completed: 'green',
    waived: 'default',
  } as Record<string, string>)[status || ''] || 'default'
}

function compactHash(value?: string | null) {
  if (!value) return '-'
  return value.length > 16 ? `${value.slice(0, 8)}...${value.slice(-6)}` : value
}

function distributionEntries(distribution?: SemanticDistribution) {
  return Object.entries(distribution || {}).map(([label, value]) => ({ label, value }))
}

function formatTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

async function openReport(url?: string) {
  if (!url) return
  const blob = await fetchCaseReportRequest(url)
  const blobUrl = URL.createObjectURL(blob)
  window.open(blobUrl, '_blank', 'noopener,noreferrer')
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000)
}

async function completeCaseAction(actionId: string) {
  if (!caseDetail.value) return
  savingActionId.value = actionId
  try {
    const response = await completeCaseActionRequest(caseDetail.value.case_id, actionId, { note: '前端演示标记完成' })
    caseDetail.value = response.data
    message.success('处置项已完成')
  } finally {
    savingActionId.value = ''
  }
}

async function waiveCaseAction(actionId: string) {
  if (!caseDetail.value) return
  savingActionId.value = actionId
  try {
    const response = await waiveCaseActionRequest(caseDetail.value.case_id, actionId, { note: '前端演示豁免' })
    caseDetail.value = response.data
    message.success('处置项已豁免')
  } finally {
    savingActionId.value = ''
  }
}

async function acknowledgeCaseBlocker(blockerId: string) {
  if (!caseDetail.value) return
  savingBlockerId.value = blockerId
  try {
    const response = await acknowledgeCaseBlockerRequest(caseDetail.value.case_id, blockerId, {
      reason: 'Analyst acknowledges missing same-event platform evidence for prototype review.',
    })
    caseDetail.value = response.data
    message.success('平台缺口已确认，原始证据缺口仍保留')
  } finally {
    savingBlockerId.value = ''
  }
}

async function submitCaseFeedback() {
  if (!caseDetail.value || !feedbackText.value.trim()) {
    message.warning('请先填写反馈内容')
    return
  }
  savingFeedback.value = true
  try {
    const response = await submitCaseFeedbackRequest(caseDetail.value.case_id, { content: feedbackText.value.trim() })
    caseDetail.value = response.data
    feedbackText.value = ''
    message.success('反馈已提交')
  } finally {
    savingFeedback.value = false
  }
}

async function submitCaseCloseoutReview() {
  if (!caseDetail.value || !closeoutSummary.value.trim()) {
    message.warning('请先填写结案复核说明')
    return
  }
  if (caseDetail.value.state !== 'ready_to_close') {
    message.warning('请先完成必需处置并提交反馈，且确认没有活动阻塞项')
    return
  }
  savingCloseout.value = true
  try {
    const response = await submitCaseCloseoutReviewRequest(caseDetail.value.case_id, {
      summary: closeoutSummary.value.trim(),
    })
    caseDetail.value = response.data
    closeoutSummary.value = ''
    message.success('结案复核已提交')
  } finally {
    savingCloseout.value = false
  }
}

onMounted(() => {
  void loadCase()
})
</script>

<style scoped lang="less">
.case-page {
  min-height: 100%;
}

.case-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.event-input {
  width: min(420px, 100%);
}

.case-alert,
.loading-card {
  margin-bottom: 16px;
}

.case-context-bar {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 1fr) minmax(180px, 0.5fr);
  gap: 16px;
  align-items: stretch;
  margin-bottom: 14px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fbff;
}

.case-title-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;

  h2 {
    margin: 0;
    font-size: 18px;
  }
}

.case-title-block p {
  margin: 8px 0 0;
  color: #475569;
}

.case-claim-block,
.case-blocker-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.case-claim-block strong {
  color: #111827;
  line-height: 1.5;
}

.blocker-row {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
  color: #475569;
  font-size: 12px;
}

.blocker-acknowledgements {
  display: grid;
  gap: 4px;
  color: #64748b;
  font-size: 12px;
}

.case-claim-block small,
.eyebrow {
  color: #64748b;
}

.eyebrow {
  font-size: 12px;
}

.lifecycle-strip {
  display: grid;
  grid-template-columns: repeat(7, minmax(100px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
  overflow-x: auto;
}

.lifecycle-step {
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #64748b;
  white-space: nowrap;
}

.lifecycle-step.done {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #166534;
}

.lifecycle-step.active {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #c2410c;
  font-weight: 700;
}

.case-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 14px;
}

.overview-grid,
.matrix-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel {
  min-width: 0;
  padding: 14px;
  border: 1px solid #edf0f5;
  border-radius: 8px;
  background: #fff;
}

.panel-title {
  margin-bottom: 12px;
  color: #111827;
  font-weight: 700;
}

.semantic-tags,
.semantic-section {
  margin-bottom: 12px;
}

.semantic-section h3 {
  margin: 0 0 8px;
  color: #334155;
  font-size: 13px;
}

.semantic-stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(72px, 1fr));
  gap: 8px;
}

.semantic-stat-row :deep(.ant-statistic) {
  padding: 6px 8px;
  border: 1px solid #edf0f5;
}

.semantic-empty {
  color: #64748b;
  font-size: 12px;
}

.compact-list .topic-row:first-child {
  border-top: 1px solid #f1f5f9;
}

.topic-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
}

.topic-row span {
  color: #64748b;
}

.graph-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.node-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.feedback-panel {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.feedback-panel .ant-btn {
  flex: 0 0 auto;
}

.feedback-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.feedback-item {
  padding: 10px;
  border: 1px solid #edf0f5;
  border-radius: 6px;
  background: #f8fafc;
}

.feedback-item span {
  margin-left: 8px;
  color: #64748b;
}

.feedback-item p {
  margin: 6px 0 0;
}

.drawer-post div {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: #64748b;
}

.drawer-post p {
  margin: 8px 0 0;
  color: #1f2329;
  line-height: 1.6;
}

@media (max-width: 1180px) {
  .case-context-bar,
  .overview-grid,
  .matrix-grid,
  .graph-summary {
    grid-template-columns: 1fr;
  }
}

@media print {
  .case-toolbar,
  :deep(.ant-tabs-nav),
  :deep(.ant-drawer) {
    display: none !important;
  }

  .case-context-bar,
  .panel {
    box-shadow: none;
    break-inside: avoid;
  }
}
</style>
