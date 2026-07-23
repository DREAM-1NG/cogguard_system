<template>
  <div>
    <PageHeader title="系统管理">
      <template #description>
        管理智能研判服务、评测数据集、策略优化、任务记录和历史报告回填。
      </template>
    </PageHeader>

    <a-tabs v-model:activeKey="activeTab">
      <a-tab-pane key="providers" tab="服务配置">
        <a-card size="small" title="智能研判服务配置" class="section-card provider-config-card">
          <a-form :model="providerForm" layout="vertical" class="provider-form">
            <div class="provider-form-grid">
              <a-form-item label="服务名称" class="provider-form-item">
                <a-input v-model:value="providerForm.name" placeholder="请输入服务名称" />
              </a-form-item>

              <a-form-item label="服务类型" class="provider-form-item">
                <a-select v-model:value="providerForm.provider_type">
                  <a-select-option
                    v-for="option in providerTypeOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </a-select-option>
                </a-select>
              </a-form-item>

              <a-form-item label="服务地址" class="provider-form-item provider-form-item-wide">
                <a-input v-model:value="providerForm.base_url" placeholder="请输入服务地址" />
              </a-form-item>

              <a-form-item label="模型名称" class="provider-form-item">
                <a-input v-model:value="providerForm.model" placeholder="请输入模型名称" />
              </a-form-item>

              <a-form-item label="接口协议" class="provider-form-item">
                <a-select v-model:value="providerForm.wire_api">
                  <a-select-option
                    v-for="option in wireApiOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </a-select-option>
                </a-select>
              </a-form-item>

              <a-form-item label="访问密钥" class="provider-form-item provider-form-item-wide">
                <a-input-password
                  v-model:value="providerForm.api_key"
                  placeholder="已保存的密钥不会回显"
                />
              </a-form-item>
            </div>

            <div class="provider-form-footer">
              <a-checkbox v-model:checked="providerForm.supports_vision">支持视觉输入</a-checkbox>
              <a-space :size="12" wrap>
                <a-button type="primary" :loading="providerLoading" @click="handleCreateProvider">
                  保存服务
                </a-button>
                <a-button @click="loadProviders">刷新服务</a-button>
              </a-space>
            </div>
          </a-form>
        </a-card>

        <a-table :columns="providerColumns" :dataSource="providers" :rowKey="providerRowKey" size="small" :pagination="false">
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'name'">
              {{ formatProviderName(record.name, record.source, record.provider_type) }}
            </template>
            <template v-else-if="column.dataIndex === 'provider_type'">
              {{ formatProviderType(record.provider_type) }}
            </template>
            <template v-else-if="column.dataIndex === 'wire_api'">
              {{ formatWireApi(record.wire_api) }}
            </template>
            <template v-else-if="column.dataIndex === 'api_key_status'">
              {{ formatApiKeyStatus(record.api_key_status) }}
            </template>
            <template v-else-if="column.dataIndex === 'is_active'">
              {{ formatEnabledStatus(record.is_active) }}
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-space v-if="canOperateProvider(record)" :size="8" wrap>
                <a-button size="small" @click="handleActivateProvider(record)">启用</a-button>
                <a-button size="small" @click="handleTestProvider(record)">测试</a-button>
              </a-space>
              <span v-else class="provider-action-hint">系统默认</span>
            </template>
          </template>
        </a-table>
      </a-tab-pane>

      <a-tab-pane key="datasets" tab="评测数据集">
        <a-card size="small" title="上传评测数据集 JSON" class="section-card">
          <a-textarea
            v-model:value="gateDatasetJson"
            :rows="8"
            placeholder="粘贴评测数据集 JSON"
          />
          <div class="section-actions">
            <a-space :size="12" wrap>
              <a-button type="primary" :loading="datasetLoading" @click="handleUploadGateDataset">
                上传入库
              </a-button>
              <a-button @click="loadGateDatasets">刷新数据集</a-button>
            </a-space>
          </div>
        </a-card>
        <a-table :columns="datasetColumns" :dataSource="gateDatasets" rowKey="id" size="small" :pagination="false" />
      </a-tab-pane>

      <a-tab-pane key="policies" tab="策略管理">
        <a-card size="small" title="启动策略优化任务" class="section-card">
          <a-form layout="vertical">
            <div class="policy-form-grid">
              <a-form-item label="最大迭代次数" class="policy-form-item">
                <a-input-number v-model:value="policyForm.max_iterations" :min="1" :max="8" style="width: 100%" />
              </a-form-item>
              <a-form-item label="反馈报告编号" class="policy-form-item policy-form-item-wide">
                <a-input
                  v-model:value="policyForm.feedback_report_ids_text"
                  placeholder="多个编号请用逗号或空格分隔"
                />
              </a-form-item>
            </div>

            <div class="policy-checkboxes">
              <a-checkbox v-model:checked="policyForm.held_out_required">要求保留集验证</a-checkbox>
              <a-checkbox v-model:checked="policyForm.enable_llm_rule_generator">启用大模型规则候选</a-checkbox>
            </div>
          </a-form>

          <a-textarea
            v-model:value="policyManifestJson"
            :rows="8"
            class="policy-textarea"
            placeholder="请输入策略优化清单 JSON"
          />

          <div class="section-actions">
            <a-space :size="12" wrap>
              <a-button type="primary" :loading="policyLoading" @click="handleRefinePolicy">
                启动优化
              </a-button>
              <a-button @click="loadPolicies">刷新策略</a-button>
            </a-space>
          </div>
        </a-card>

        <a-table :columns="policyColumns" :dataSource="policies" rowKey="policy_id" size="small" :pagination="false">
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'activation_status'">
              {{ formatPolicyStatus(record.activation_status) }}
            </template>
            <template v-else-if="column.dataIndex === 'can_activate'">
              {{ formatActivatableStatus(record.can_activate) }}
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-button size="small" :disabled="!record.can_activate" @click="handleActivatePolicy(record)">
                人工激活
              </a-button>
            </template>
          </template>
        </a-table>
      </a-tab-pane>

      <a-tab-pane key="jobs" tab="任务记录">
        <a-card size="small" class="section-card">
          <a-button @click="loadJobs">刷新任务</a-button>
        </a-card>

        <a-table :columns="jobColumns" :dataSource="jobs" rowKey="job_id" size="small" :pagination="false">
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'job_type'">
              {{ formatJobType(record.job_type) }}
            </template>
            <template v-else-if="column.dataIndex === 'status'">
              {{ formatJobStatus(record.status) }}
            </template>
          </template>
        </a-table>
      </a-tab-pane>

      <a-tab-pane key="backfill" tab="历史回填">
        <a-card size="small" title="历史报告回填" class="section-card">
          <a-input
            v-model:value="backfillReportIdsText"
            placeholder="可留空自动扫描，也可输入报告编号"
          />
          <a-input-number
            v-model:value="backfillLimit"
            :min="1"
            :max="5000"
            class="backfill-limit-input"
          />
          <a-button type="primary" :loading="backfillLoading" @click="handleBackfill">
            启动回填
          </a-button>
        </a-card>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import PageHeader from '@/components/PageHeader.vue'
import {
  activateReviewPolicy,
  activateReviewProvider,
  createReviewProvider,
  listReviewGateDatasets,
  listReviewJobs,
  listReviewPolicies,
  listReviewProviders,
  refineReviewPolicy,
  startReviewBackfill,
  testReviewProvider,
  uploadReviewGateDataset,
} from '@/api/risk'

const activeTab = ref('providers')
const providerLoading = ref(false)
const datasetLoading = ref(false)
const policyLoading = ref(false)
const backfillLoading = ref(false)

const providers = ref<any[]>([])
const gateDatasets = ref<any[]>([])
const policies = ref<any[]>([])
const jobs = ref<any[]>([])

const providerTypeOptions = [
  { value: 'text_llm', label: '文本模型' },
  { value: 'vision_llm', label: '视觉模型' },
  { value: 'retrieval', label: '检索服务' },
]

const wireApiOptions = [
  { value: 'responses', label: 'Responses 接口' },
  { value: 'chat_completions', label: '对话补全接口' },
]

const providerForm = ref({
  name: '主系统模型服务',
  provider_type: 'text_llm',
  base_url: '',
  model: '',
  wire_api: 'responses',
  api_key: '',
  supports_vision: false,
})

const gateDatasetJson = ref('')
const policyManifestJson = ref('')
const policyForm = ref({
  max_iterations: 3,
  held_out_required: true,
  enable_llm_rule_generator: false,
  feedback_report_ids_text: '',
})
const backfillReportIdsText = ref('')
const backfillLimit = ref(500)

const providerColumns = [
  { title: '编号', dataIndex: 'id', width: 80 },
  { title: '服务名称', dataIndex: 'name' },
  { title: '服务类型', dataIndex: 'provider_type', width: 120 },
  { title: '模型名称', dataIndex: 'model' },
  { title: '接口协议', dataIndex: 'wire_api', width: 130 },
  { title: '密钥状态', dataIndex: 'api_key_status', width: 100 },
  { title: '启用状态', dataIndex: 'is_active', width: 100 },
  { title: '操作', key: 'actions', width: 140 },
]

const datasetColumns = [
  { title: '编号', dataIndex: 'id', width: 80 },
  { title: '数据集编号', dataIndex: 'dataset_id' },
  { title: '版本', dataIndex: 'version', width: 120 },
  { title: '指纹', dataIndex: 'manifest_fingerprint', ellipsis: true },
  { title: '样本数', dataIndex: ['summary', 'case_count'], width: 100 },
  { title: '创建时间', dataIndex: 'created_at', width: 200 },
]

const policyColumns = [
  { title: '策略编号', dataIndex: 'policy_id', ellipsis: true },
  { title: '状态', dataIndex: 'activation_status', width: 180 },
  { title: '可激活', dataIndex: 'can_activate', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', width: 200 },
  { title: '操作', key: 'actions', width: 120 },
]

const jobColumns = [
  { title: '任务编号', dataIndex: 'job_id', width: 90 },
  { title: '任务类型', dataIndex: 'job_type', width: 140 },
  { title: '状态', dataIndex: 'status', width: 120 },
  { title: '进度', dataIndex: 'progress', width: 90 },
  { title: '错误信息', dataIndex: 'error', ellipsis: true },
  { title: '创建时间', dataIndex: 'created_at', width: 200 },
]

const providerTypeLabelMap: Record<string, string> = {
  text_llm: '文本模型',
  vision_llm: '视觉模型',
  retrieval: '检索服务',
}

const wireApiLabelMap: Record<string, string> = {
  responses: 'Responses 接口',
  chat_completions: '对话补全接口',
}

const apiKeyStatusLabelMap: Record<string, string> = {
  configured: '已配置',
  missing: '未配置',
}

const policyStatusLabelMap: Record<string, string> = {
  candidate_pending_human_approval: '待人工审核',
  active_human_approved: '已人工激活',
  inactive: '未启用',
  persisted: '已保存',
}

const jobTypeLabelMap: Record<string, string> = {
  agent_review: '智能研判',
  policy_refine: '策略优化',
  gate_dataset_ingest: '数据集入库',
  backfill: '历史回填',
}

const jobStatusLabelMap: Record<string, string> = {
  pending: '排队中',
  running: '执行中',
  completed: '已完成',
  failed: '执行失败',
  cancelled: '已取消',
}

const providerCheckStatusLabelMap: Record<string, string> = {
  ready: '配置完整',
  incomplete: '信息不完整',
}

const providerNameAliasMap: Record<string, string> = {
  'Review LLM Provider': '主系统模型服务',
  'Review Provider': '主系统服务',
  'Environment LLM Provider': '环境变量模型服务',
}

const feedbackReportIds = computed(() => splitCsvLike(policyForm.value.feedback_report_ids_text))

function splitCsvLike(value: string) {
  return (value || '').split(/[,，\s]+/).map((item) => item.trim()).filter(Boolean)
}

function parseJson(value: string, fallback: Record<string, unknown>) {
  if (!value.trim()) return fallback
  return JSON.parse(value)
}

function formatProviderName(name: unknown, source?: unknown, providerType?: unknown) {
  if (source === 'env_fallback') {
    return `环境变量默认${formatProviderType(providerType)}`
  }

  const raw = String(name || '').trim()
  if (!raw) return '未命名服务'
  return providerNameAliasMap[raw] || raw
}

function formatProviderType(value: unknown) {
  return providerTypeLabelMap[String(value || '')] || '未知类型'
}

function formatWireApi(value: unknown) {
  return wireApiLabelMap[String(value || '')] || '未知协议'
}

function formatApiKeyStatus(value: unknown) {
  return apiKeyStatusLabelMap[String(value || '')] || '未知'
}

function formatEnabledStatus(value: unknown) {
  return value ? '已启用' : '未启用'
}

function formatActivatableStatus(value: unknown) {
  return value ? '是' : '否'
}

function formatPolicyStatus(value: unknown) {
  return policyStatusLabelMap[String(value || '')] || '未知状态'
}

function formatJobType(value: unknown) {
  return jobTypeLabelMap[String(value || '')] || '未知任务'
}

function formatJobStatus(value: unknown) {
  return jobStatusLabelMap[String(value || '')] || '未知状态'
}

function formatProviderCheckStatus(value: unknown) {
  return providerCheckStatusLabelMap[String(value || '')] || '未知结果'
}

function providerRowKey(record: any) {
  return record?.id ?? `${record?.source || 'provider'}-${record?.provider_type || 'unknown'}-${record?.model || 'default'}`
}

function canOperateProvider(record: any) {
  return typeof record?.id === 'number' && Number.isFinite(record.id)
}

async function loadProviders() {
  const res = await listReviewProviders()
  providers.value = res.data?.items || []
}

async function loadGateDatasets() {
  const res = await listReviewGateDatasets({ page: 1, page_size: 20 })
  gateDatasets.value = res.data?.items || []
}

async function loadPolicies() {
  const res = await listReviewPolicies({ page: 1, page_size: 20 })
  policies.value = res.data?.items || []
}

async function loadJobs() {
  const res = await listReviewJobs({ page: 1, page_size: 50 })
  jobs.value = res.data?.items || []
}

async function handleCreateProvider() {
  providerLoading.value = true
  try {
    await createReviewProvider({
      ...providerForm.value,
      api_key: providerForm.value.api_key || undefined,
      metadata: {},
    })
    providerForm.value.api_key = ''
    message.success('服务配置已保存，访问密钥不会回显')
    await loadProviders()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.response?.data?.msg || error.message)
  } finally {
    providerLoading.value = false
  }
}

async function handleActivateProvider(record: any) {
  if (!canOperateProvider(record)) {
    message.info('环境变量默认服务由系统配置直接提供，无需单独激活')
    return
  }
  await activateReviewProvider(record.id, true)
  message.success(`${formatProviderType(record.provider_type)}已启用`)
  await loadProviders()
}

async function handleTestProvider(record: any) {
  if (!canOperateProvider(record)) {
    message.info('环境变量默认服务没有独立配置记录，无法单独检测')
    return
  }
  const res = await testReviewProvider(record.id)
  message.info(`配置检测结果：${formatProviderCheckStatus(res.data?.status)}`)
}

async function handleUploadGateDataset() {
  datasetLoading.value = true
  try {
    await uploadReviewGateDataset(parseJson(gateDatasetJson.value, {}))
    message.success('评测数据集已入库')
    await loadGateDatasets()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.response?.data?.msg || error.message)
  } finally {
    datasetLoading.value = false
  }
}

async function handleRefinePolicy() {
  policyLoading.value = true
  try {
    const res = await refineReviewPolicy({
      dataset_manifest: parseJson(policyManifestJson.value, { splits: { validation: [], held_out: [] } }),
      feedback_report_ids: feedbackReportIds.value,
      max_iterations: policyForm.value.max_iterations,
      enable_llm_rule_generator: policyForm.value.enable_llm_rule_generator,
      held_out_required: policyForm.value.held_out_required,
    })
    message.success(`策略优化任务已启动：第 ${res.data?.job_id} 个`)
    await loadJobs()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.response?.data?.msg || error.message)
  } finally {
    policyLoading.value = false
  }
}

async function handleActivatePolicy(record: any) {
  await activateReviewPolicy(record.policy_id)
  message.success('策略已人工激活')
  await loadPolicies()
}

async function handleBackfill() {
  backfillLoading.value = true
  try {
    const res = await startReviewBackfill({
      report_ids: splitCsvLike(backfillReportIdsText.value),
      limit: backfillLimit.value,
    })
    message.success(`历史回填任务已启动：第 ${res.data?.job_id} 个`)
    await loadJobs()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.response?.data?.msg || error.message)
  } finally {
    backfillLoading.value = false
  }
}

onMounted(async () => {
  await Promise.allSettled([loadProviders(), loadGateDatasets(), loadPolicies(), loadJobs()])
})
</script>

<style scoped>
.section-card {
  margin-bottom: 12px;
}

.provider-config-card :deep(.ant-card-body) {
  padding-bottom: 20px;
}

.provider-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.provider-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px 24px;
}

.provider-form-item {
  margin-bottom: 0;
}

.provider-form-item-wide {
  grid-column: span 2;
}

.provider-form-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.policy-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px 20px;
}

.policy-form-item {
  margin-bottom: 0;
}

.policy-form-item-wide {
  grid-column: span 2;
}

.policy-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 24px;
  margin-top: 8px;
}

.policy-textarea {
  margin-top: 16px;
}

.section-actions {
  margin-top: 12px;
}

.backfill-limit-input {
  display: block;
  width: 180px;
  margin: 12px 0;
}

.provider-action-hint {
  color: #8c8c8c;
}

@media (max-width: 768px) {
  .provider-form-item-wide,
  .policy-form-item-wide {
    grid-column: span 1;
  }

  .provider-form-footer {
    align-items: flex-start;
    justify-content: flex-start;
  }
}
</style>

