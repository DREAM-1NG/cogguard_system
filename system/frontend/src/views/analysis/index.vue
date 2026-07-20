<template>
  <div class="analysis-page">
    <PageHeader
      title="Unified Analysis"
      description="Run KT1 coordination discovery, KT2 propagation hindcast, Student review, and asynchronous Teacher review from one EventSnapshot."
    />

    <a-alert
      type="info"
      show-icon
      class="analysis-alert"
      message="V2 analysis runtime"
      description="This workbench uses /api/v2/analysis, EventSnapshot, AnalysisRun events, REST recovery, and SSE backlog through Last-Event-ID compatible cursors."
    />

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="8">
        <a-card title="1. EventSnapshot" size="small" class="analysis-card">
          <a-form layout="vertical" :model="snapshotForm">
            <a-form-item label="Event ID">
              <a-input v-model:value="snapshotForm.event_id" placeholder="trump_visit_2026_05_21" />
            </a-form-item>
            <a-form-item label="Platform filter">
              <a-select v-model:value="snapshotForm.platform" allow-clear placeholder="All platforms">
                <a-select-option value="weibo">weibo</a-select-option>
                <a-select-option value="douyin">douyin</a-select-option>
                <a-select-option value="xhs">xhs</a-select-option>
                <a-select-option value="news">news</a-select-option>
              </a-select>
            </a-form-item>
            <div class="form-grid">
              <a-form-item label="Core start">
                <a-input v-model:value="snapshotForm.core_window.start" />
              </a-form-item>
              <a-form-item label="Core end">
                <a-input v-model:value="snapshotForm.core_window.end" />
              </a-form-item>
              <a-form-item label="Context start">
                <a-input v-model:value="snapshotForm.context_window.start" />
              </a-form-item>
              <a-form-item label="Context end">
                <a-input v-model:value="snapshotForm.context_window.end" />
              </a-form-item>
            </div>
            <a-button type="primary" block :loading="snapshotLoading" @click="handleCreateSnapshot">
              Create snapshot
            </a-button>
          </a-form>

          <a-divider />
          <a-descriptions v-if="snapshot" size="small" :column="1" bordered>
            <a-descriptions-item label="snapshot_id">{{ snapshot.snapshot_id }}</a-descriptions-item>
            <a-descriptions-item label="platforms">{{ (snapshot.platforms || []).join(', ') || '-' }}</a-descriptions-item>
            <a-descriptions-item label="quality">{{ snapshot.quality_report?.status || '-' }}</a-descriptions-item>
            <a-descriptions-item label="fingerprint">{{ snapshot.data_fingerprint || '-' }}</a-descriptions-item>
          </a-descriptions>
          <a-empty v-else description="No snapshot yet" :image-style="{ height: '44px' }" />
        </a-card>

        <a-card title="2. AnalysisRun" size="small" class="analysis-card">
          <a-form layout="vertical" :model="runForm">
            <a-form-item label="Event ID">
              <a-input v-model:value="runForm.event_id" />
            </a-form-item>
            <a-form-item label="Snapshot ID">
              <a-input v-model:value="runForm.snapshot_id" />
            </a-form-item>
            <a-form-item label="Stages">
              <a-checkbox-group v-model:value="runForm.requested_stages" :options="stageOptions" />
            </a-form-item>
            <a-form-item label="Options JSON">
              <a-textarea v-model:value="runForm.options_json" :rows="9" />
            </a-form-item>
            <a-space direction="vertical" class="full-width">
              <a-button type="primary" block :loading="runLoading" @click="handleCreateRun">Create run</a-button>
              <a-button block :disabled="!currentRunId" :loading="executeLoading" @click="handleExecuteRun">
                Execute run
              </a-button>
              <a-button block :disabled="!currentRunId" @click="handleLoadRun">Refresh status</a-button>
            </a-space>
          </a-form>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="16">
        <a-card title="Run status" size="small" class="analysis-card">
          <a-descriptions v-if="runDetail" size="small" :column="2" bordered>
            <a-descriptions-item label="run_id">{{ runDetail.run_id }}</a-descriptions-item>
            <a-descriptions-item label="status">
              <a-tag :color="statusColor(runDetail.status)">{{ runDetail.status }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="snapshot_id">{{ runDetail.snapshot_id }}</a-descriptions-item>
            <a-descriptions-item label="stages">{{ (runDetail.requested_stages || []).join(', ') }}</a-descriptions-item>
          </a-descriptions>
          <a-empty v-else description="No run yet" :image-style="{ height: '44px' }" />
        </a-card>

        <div class="result-grid">
          <a-card title="KT1 communities" size="small" class="result-card">
            <a-space wrap>
              <a-tag :color="statusColor(kt1?.status)">{{ kt1?.status || 'not run' }}</a-tag>
              <a-tag>{{ kt1?.model_version || '-' }}</a-tag>
            </a-space>
            <a-statistic title="Evidence edges" :value="numberValue(kt1?.summary?.evidence_edge_count)" />
            <a-statistic title="Lineages" :value="numberValue(kt1?.summary?.lineage_count)" />
            <div class="mini-list">
              <div v-for="item in communityRows" :key="item.lineage_id" class="mini-row">
                <strong>{{ item.lineage_id }}</strong>
                <span>{{ item.support_count }} windows, stability {{ item.stability_score }}</span>
              </div>
            </div>
          </a-card>

          <a-card title="KT2 hindcast" size="small" class="result-card">
            <a-space wrap>
              <a-tag :color="statusColor(kt2?.status)">{{ kt2?.status || 'not run' }}</a-tag>
              <a-tag>{{ kt2?.model_version || kt2?.model || '-' }}</a-tag>
            </a-space>
            <a-statistic title="Active accounts forecast" :value="numberValue(kt2?.scale_forecast?.point)" />
            <div class="intervals">
              <span>80% {{ intervalText(kt2?.conformal_intervals?.['80']) }}</span>
              <span>95% {{ intervalText(kt2?.conformal_intervals?.['95']) }}</span>
            </div>
            <div class="mini-list">
              <div v-for="item in nextHopRows" :key="item.author_id" class="mini-row">
                <strong>#{{ item.rank }} {{ item.author_id }}</strong>
                <span>score {{ item.score }}</span>
              </div>
            </div>
          </a-card>

          <a-card title="KT3 Student" size="small" class="result-card">
            <a-space wrap>
              <a-tag :color="statusColor(student?.status)">{{ student?.status || 'not run' }}</a-tag>
              <a-tag>{{ student?.model_status || '-' }}</a-tag>
              <a-tag>{{ student?.verdict_type || '-' }}</a-tag>
            </a-space>
            <a-statistic title="Score" :value="numberValue(student?.score)" :precision="3" />
            <p class="result-text">Label: {{ student?.label || '-' }}</p>
            <p class="result-text">Active learning: {{ activeLearningReasons }}</p>
          </a-card>

          <a-card title="KT3 Teacher" size="small" class="result-card">
            <a-space wrap>
              <a-tag :color="statusColor(teacher?.status)">{{ teacher?.status || 'not run' }}</a-tag>
              <a-tag>{{ teacher?.verdict_type || '-' }}</a-tag>
            </a-space>
            <p class="result-text">Decision: {{ teacher?.advisory?.decision || '-' }}</p>
            <p class="result-text">Canonical allowed: {{ teacher?.canonical_allowed === false ? 'no' : '-' }}</p>
            <div class="dag-strip">
              <a-tag v-for="node in teacherNodes" :key="node.node" :color="node.status === 'completed' || node.status === 'ok' ? 'green' : 'default'">
                {{ node.node }}
              </a-tag>
            </div>
          </a-card>
        </div>

        <a-card title="Run events and recovery" size="small" class="analysis-card">
          <a-space class="event-actions" wrap>
            <a-input v-model:value="currentRunId" class="run-input" placeholder="run_id" />
            <a-input-number v-model:value="afterId" :min="0" />
            <a-button :disabled="!currentRunId" :loading="eventsLoading" @click="handleLoadEvents">
              REST refresh
            </a-button>
            <a-button :disabled="!currentRunId || streamLoading" @click="handleReadStream">
              SSE backlog
            </a-button>
            <a-button :disabled="!streamAbort" danger @click="stopStream">Stop stream</a-button>
          </a-space>
          <a-list v-if="events.length" :data-source="events" size="small" class="event-list">
            <template #renderItem="{ item }">
              <a-list-item>
                <div class="event-item">
                  <div class="event-meta">
                    <a-tag>{{ item.id }}</a-tag>
                    <strong>{{ item.event_type }}</strong>
                    <a-tag :color="statusColor(item.status)">{{ item.status }}</a-tag>
                  </div>
                  <pre>{{ formatJson(item.payload) }}</pre>
                </div>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else description="No run events" :image-style="{ height: '44px' }" />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { message } from 'ant-design-vue'
import PageHeader from '@/components/PageHeader.vue'
import {
  analysisAuthHeaders,
  analysisStreamUrl,
  createAnalysisRun,
  createAnalysisSnapshot,
  executeAnalysisRun,
  getAnalysisRun,
  listAnalysisRunEvents,
  type AnalysisRunEvent,
  type AnalysisStage,
} from '@/api/analysis'

const defaultEventId = 'trump_visit_2026_05_21'

const snapshotForm = ref({
  event_id: defaultEventId,
  platform: undefined as string | undefined,
  core_window: {
    start: '2026-05-11T00:00:00Z',
    end: '2026-05-22T00:00:00Z',
  },
  context_window: {
    start: '2026-05-01T00:00:00Z',
    end: '2026-05-31T00:00:00Z',
  },
})

const runForm = ref({
  event_id: defaultEventId,
  snapshot_id: '',
  requested_stages: ['kt1', 'kt2', 'student', 'teacher'] as AnalysisStage[],
  options_json: JSON.stringify({
    kt1: { time_window: 3600, min_participation: 2, edge_weight: 0.5 },
    kt2: { top_k: 10 },
    student: {},
    teacher: { teacher_max_review_items: 20 },
  }, null, 2),
})

const stageOptions = [
  { label: 'KT1 coordination', value: 'kt1' },
  { label: 'KT2 propagation', value: 'kt2' },
  { label: 'Student review', value: 'student' },
  { label: 'Teacher review', value: 'teacher' },
]

const snapshot = ref<any>(null)
const runDetail = ref<any>(null)
const events = ref<AnalysisRunEvent[]>([])
const currentRunId = ref('')
const afterId = ref(0)
const snapshotLoading = ref(false)
const runLoading = ref(false)
const executeLoading = ref(false)
const eventsLoading = ref(false)
const streamLoading = ref(false)
const streamAbort = ref<AbortController | null>(null)

const latestEventId = computed(() => events.value.reduce((max, item) => Math.max(max, Number(item.id) || 0), 0))
const runResults = computed<Record<string, any>>(() => {
  return runDetail.value?.results || runDetail.value?.result?.results || {}
})
const kt1 = computed(() => runResults.value.kt1 || null)
const kt2 = computed(() => runResults.value.kt2 || null)
const student = computed(() => runResults.value.student || null)
const teacher = computed(() => runResults.value.teacher || null)
const communityRows = computed(() => (kt1.value?.community_lineage || []).slice(0, 5))
const nextHopRows = computed(() => (kt2.value?.next_hop_ranking?.items || []).slice(0, 5))
const teacherNodes = computed(() => teacher.value?.dag?.nodes || [])
const activeLearningReasons = computed(() => {
  const reasons = student.value?.signals?.active_learning?.reasons || []
  return reasons.length ? reasons.join(', ') : '-'
})

async function handleCreateSnapshot() {
  if (!snapshotForm.value.event_id.trim()) {
    message.warning('Event ID is required')
    return
  }
  snapshotLoading.value = true
  try {
    const res = await createAnalysisSnapshot(snapshotForm.value) as { data: any }
    snapshot.value = res.data
    runForm.value.event_id = res.data.event_id || snapshotForm.value.event_id
    runForm.value.snapshot_id = res.data.snapshot_id
    message.success('EventSnapshot created')
  } finally {
    snapshotLoading.value = false
  }
}

async function handleCreateRun() {
  if (!runForm.value.event_id.trim() || !runForm.value.snapshot_id.trim()) {
    message.warning('Event ID and Snapshot ID are required')
    return
  }
  if (!runForm.value.requested_stages.length) {
    message.warning('Select at least one stage')
    return
  }
  runLoading.value = true
  try {
    const res = await createAnalysisRun({
      event_id: runForm.value.event_id,
      snapshot_id: runForm.value.snapshot_id,
      requested_stages: runForm.value.requested_stages,
      options: parseOptions(),
    }) as { data: any }
    runDetail.value = res.data
    currentRunId.value = res.data.run_id
    await handleLoadEvents()
    message.success('AnalysisRun created')
  } finally {
    runLoading.value = false
  }
}

async function handleExecuteRun() {
  if (!currentRunId.value) return
  executeLoading.value = true
  try {
    const res = await executeAnalysisRun(currentRunId.value) as { data: any }
    runDetail.value = res.data
    await handleLoadEvents()
    message.success('AnalysisRun executed')
  } finally {
    executeLoading.value = false
  }
}

async function handleLoadRun() {
  if (!currentRunId.value) return
  const res = await getAnalysisRun(currentRunId.value) as { data: any }
  runDetail.value = res.data
}

async function handleLoadEvents() {
  if (!currentRunId.value) return
  eventsLoading.value = true
  try {
    const res = await listAnalysisRunEvents(currentRunId.value, {
      after_id: afterId.value,
      limit: 200,
    }) as { data: { events: AnalysisRunEvent[] } }
    events.value = mergeEvents(events.value, res.data.events || [])
  } finally {
    eventsLoading.value = false
  }
}

async function handleReadStream() {
  if (!currentRunId.value) return
  stopStream()
  const controller = new AbortController()
  streamAbort.value = controller
  streamLoading.value = true
  try {
    const response = await fetch(analysisStreamUrl(currentRunId.value, latestEventId.value), {
      headers: analysisAuthHeaders(),
      signal: controller.signal,
    })
    if (!response.ok) {
      throw new Error(`SSE backlog failed: ${response.status}`)
    }
    if (response.body) {
      await readSseBacklog(response.body.getReader())
    }
    message.success('SSE backlog loaded')
  } catch (error: any) {
    if (error?.name !== 'AbortError') {
      message.error(error?.message || 'SSE backlog failed')
    }
  } finally {
    streamAbort.value = null
    streamLoading.value = false
  }
}

async function readSseBacklog(reader: ReadableStreamDefaultReader<Uint8Array>) {
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\n\n/)
    buffer = parts.pop() || ''
    for (const part of parts) {
      const event = parseSseEvent(part)
      if (event) {
        events.value = mergeEvents(events.value, [event])
      }
    }
  }
}

function parseSseEvent(raw: string): AnalysisRunEvent | null {
  const lines = raw.split(/\n/).map((line) => line.trim())
  const idLine = lines.find((line) => line.startsWith('id:'))
  const typeLine = lines.find((line) => line.startsWith('event:'))
  const dataLine = lines.find((line) => line.startsWith('data:'))
  if (!idLine || !dataLine) return null
  try {
    const payload = JSON.parse(dataLine.replace(/^data:\s*/, ''))
    return {
      id: Number(idLine.replace(/^id:\s*/, '')),
      run_id: String(payload.run_id || currentRunId.value),
      event_type: typeLine ? typeLine.replace(/^event:\s*/, '') : 'message',
      status: String(payload.status || ''),
      payload: payload.payload || {},
    }
  } catch {
    return null
  }
}

function stopStream() {
  streamAbort.value?.abort()
  streamAbort.value = null
}

function parseOptions() {
  const text = runForm.value.options_json.trim()
  if (!text) return {}
  try {
    return JSON.parse(text)
  } catch {
    message.error('Options must be valid JSON')
    throw new Error('Invalid analysis options JSON')
  }
}

function mergeEvents(existing: AnalysisRunEvent[], incoming: AnalysisRunEvent[]) {
  const byId = new Map<number, AnalysisRunEvent>()
  for (const item of existing) {
    byId.set(Number(item.id), item)
  }
  for (const item of incoming) {
    byId.set(Number(item.id), item)
  }
  return Array.from(byId.values()).sort((a, b) => Number(a.id) - Number(b.id))
}

function formatJson(value: unknown) {
  return JSON.stringify(value || {}, null, 2)
}

function numberValue(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function intervalText(interval?: { low?: number; high?: number }) {
  if (!interval) return '-'
  return `[${interval.low ?? '-'}, ${interval.high ?? '-'}]`
}

function statusColor(status?: string) {
  return ({
    queued: 'default',
    running: 'processing',
    needs_evidence: 'warning',
    awaiting_review: 'purple',
    completed: 'success',
    failed: 'error',
    cancelled: 'default',
    ok: 'success',
    data_insufficient: 'warning',
    missing_checkpoint: 'warning',
    unavailable: 'warning',
  } as Record<string, string>)[status || ''] || 'default'
}

onBeforeUnmount(() => {
  stopStream()
})
</script>

<style scoped lang="less">
.analysis-page {
  min-height: 100%;
}

.analysis-alert {
  margin-bottom: 16px;
}

.analysis-card {
  margin-bottom: 16px;
}

.full-width {
  width: 100%;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.result-card {
  min-height: 260px;
}

.result-text {
  margin: 8px 0 0;
  color: #475569;
}

.intervals,
.dag-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 10px 0;
}

.intervals span {
  padding: 4px 8px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  color: #334155;
  font-size: 12px;
}

.mini-list {
  margin-top: 10px;
}

.mini-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 0;
  border-bottom: 1px solid #eef2f7;
  color: #475569;
  font-size: 12px;
}

.event-actions {
  margin-bottom: 12px;
}

.run-input {
  width: 360px;
}

.event-list {
  max-height: 520px;
  overflow: auto;
}

.event-item {
  width: 100%;
}

.event-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

pre {
  margin: 0;
  padding: 10px;
  max-height: 180px;
  overflow: auto;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 12px;
}

@media (max-width: 992px) {
  .result-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .run-input {
    width: 100%;
  }
}
</style>
