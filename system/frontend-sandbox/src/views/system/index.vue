<template>
  <div class="system-page">
    <PageHeader
      title="系统运维"
      description="配置研判服务，检查连通性并查看后台任务健康摘要。"
    />

    <div class="operation-message" aria-live="polite">{{ operationMessage }}</div>

    <div class="operations-grid">
      <a-card size="small" title="服务配置" class="configuration-card">
        <a-form :model="serviceForm" layout="vertical" @finish="handleCreateService">
          <div class="form-grid">
            <a-form-item label="服务名称" name="name" required>
              <a-input
                v-model:value="serviceForm.name"
                name="service-name"
                autocomplete="off"
                placeholder="例如：主研判服务…"
              />
            </a-form-item>
            <a-form-item label="服务用途" name="purpose" required>
              <a-select
                v-model:value="serviceForm.purpose"
                :options="servicePurposeOptions"
                aria-label="服务用途"
              />
            </a-form-item>
            <a-form-item label="服务地址" name="endpoint" class="wide-field" required>
              <a-input
                v-model:value="serviceForm.endpoint"
                name="service-url"
                type="url"
                inputmode="url"
                autocomplete="off"
                :spellcheck="false"
                placeholder="https://service.example/v1…"
              />
            </a-form-item>
            <a-form-item label="调用标识" name="service_identifier" required>
              <a-input
                v-model:value="serviceForm.service_identifier"
                name="service-identifier"
                autocomplete="off"
                :spellcheck="false"
                placeholder="请输入调用标识…"
              />
            </a-form-item>
            <a-form-item label="接口协议" name="protocol" required>
              <a-select
                v-model:value="serviceForm.protocol"
                :options="wireApiOptions"
                aria-label="接口协议"
              />
            </a-form-item>
            <a-form-item label="访问密钥" name="credential" class="wide-field">
              <a-input-password
                v-model:value="serviceForm.credential"
                name="service-secret"
                autocomplete="new-password"
                placeholder="留空则不更新；已保存内容不会回显…"
              />
            </a-form-item>
          </div>
          <div class="form-footer">
            <a-checkbox v-model:checked="serviceForm.supports_media">
              支持图像材料
            </a-checkbox>
            <a-button type="primary" html-type="submit" :loading="serviceLoading">
              保存服务
            </a-button>
          </div>
        </a-form>
      </a-card>

      <a-card size="small" title="任务健康" class="health-card">
        <div class="health-summary" :class="`health-${taskHealth.tone}`">
          <span class="health-indicator" aria-hidden="true" />
          <div>
            <div class="health-title">{{ taskHealth.label }}</div>
            <div class="health-detail">{{ taskHealth.detail }}</div>
          </div>
        </div>
        <a-descriptions :column="2" size="small" bordered>
          <a-descriptions-item label="处理中">{{ taskCounts.processing }}</a-descriptions-item>
          <a-descriptions-item label="等待中">{{ taskCounts.waiting }}</a-descriptions-item>
          <a-descriptions-item label="近期完成">{{ taskCounts.completed }}</a-descriptions-item>
          <a-descriptions-item label="需要检查">{{ taskCounts.failed }}</a-descriptions-item>
        </a-descriptions>
        <a-button class="health-refresh" :loading="healthLoading" @click="loadOperationHealth">
          <ReloadOutlined aria-hidden="true" />
          刷新健康状态
        </a-button>
      </a-card>
    </div>

    <section class="service-section" aria-labelledby="service-list-title">
      <div class="section-heading">
        <div>
          <h2 id="service-list-title">服务连通性</h2>
          <p>仅显示系统运行所需的服务配置和最近一次检查结果。</p>
        </div>
        <a-button :loading="serviceLoading" @click="loadServices">
          <ReloadOutlined aria-hidden="true" />
          刷新列表
        </a-button>
      </div>

      <a-table
        :columns="serviceColumns"
        :data-source="services"
        :row-key="serviceRowKey"
        size="small"
        :pagination="false"
        :loading="serviceLoading"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <strong>{{ formatServiceName(record) }}</strong>
            <div class="secondary-text">{{ record.endpoint || '由环境配置提供' }}</div>
          </template>
          <template v-else-if="column.key === 'purpose'">
            {{ formatServicePurpose(record.purpose) }}
          </template>
          <template v-else-if="column.key === 'enabled'">
            <a-badge :status="record.enabled ? 'success' : 'default'" :text="record.enabled ? '已启用' : '未启用'" />
          </template>
          <template v-else-if="column.key === 'connectivity'">
            <a-tag :color="connectivityColor(connectivity[serviceKey(record)])">
              {{ connectivityLabel(connectivity[serviceKey(record)]) }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space v-if="canOperateService(record)" :size="8">
              <a-button size="small" :loading="checkingServiceId === record.id" @click="handleCheckService(record)">
                检查
              </a-button>
              <a-button v-if="!record.enabled" size="small" @click="handleEnableService(record)">
                启用
              </a-button>
            </a-space>
            <span v-else class="secondary-text">系统默认</span>
          </template>
        </template>
      </a-table>
      <a-empty
        v-if="!serviceLoading && services.length === 0"
        description="暂无服务配置"
        :image-style="{ height: '40px' }"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import {
  checkServiceConnection,
  createServiceConfig,
  getOperationHealth,
  listServiceConfigs,
  setServiceEnabled,
} from '@/api/systemOperations'
import type { OperationHealth, ServiceConfig, ServicePurpose } from '@/api/systemOperations'

type ConnectivityState = 'unchecked' | 'ready' | 'incomplete' | 'failed'

const serviceLoading = ref(false)
const healthLoading = ref(false)
const checkingServiceId = ref<number | null>(null)
const services = ref<ServiceConfig[]>([])
const operationHealth = ref<OperationHealth>({
  processing_count: 0,
  waiting_count: 0,
  completed_count: 0,
  attention_required_count: 0,
  message: '',
})
const connectivity = ref<Record<string, ConnectivityState>>({})
const operationMessage = ref('')

const serviceForm = ref({
  name: '',
  purpose: 'text_review' as ServicePurpose,
  endpoint: '',
  service_identifier: '',
  protocol: 'responses',
  credential: '',
  supports_media: false,
})

const servicePurposeOptions = [
  { value: 'text_review', label: '文本研判' },
  { value: 'media_verification', label: '图像材料核验' },
  { value: 'source_retrieval', label: '公开来源检索' },
]

const wireApiOptions = [
  { value: 'responses', label: 'Responses' },
  { value: 'chat_completions', label: 'Chat Completions' },
]

const serviceColumns = [
  { title: '服务', key: 'name' },
  { title: '用途', key: 'purpose', width: 150 },
  { title: '启用状态', key: 'enabled', width: 120 },
  { title: '连通性', key: 'connectivity', width: 120 },
  { title: '操作', key: 'actions', width: 160 },
]

const taskCounts = computed(() => {
  return {
    processing: operationHealth.value.processing_count,
    waiting: operationHealth.value.waiting_count,
    completed: operationHealth.value.completed_count,
    failed: operationHealth.value.attention_required_count,
  }
})

const taskHealth = computed(() => {
  if (taskCounts.value.failed > 0) {
    return {
      tone: 'warning',
      label: '存在需要检查的任务',
      detail: `${taskCounts.value.failed} 个近期任务未正常完成。`,
    }
  }
  if (taskCounts.value.processing > 0 || taskCounts.value.waiting > 0) {
    return {
      tone: 'active',
      label: '后台任务正在处理',
      detail: `${taskCounts.value.processing} 个处理中，${taskCounts.value.waiting} 个等待中。`,
    }
  }
  return { tone: 'healthy', label: '后台任务状态正常', detail: '近期未发现需要人工检查的任务。' }
})

function serviceKey(record: ServiceConfig) {
  return String(record.id ?? `${record.source}:${record.purpose}`)
}

function serviceRowKey(record: ServiceConfig) {
  return serviceKey(record)
}

function canOperateService(record: ServiceConfig) {
  return typeof record.id === 'number' && Number.isFinite(record.id)
}

function formatServiceName(record: ServiceConfig) {
  if (record.source === 'environment') return `默认${formatServicePurpose(record.purpose)}服务`
  return String(record.name || '未命名服务')
}

function formatServicePurpose(value: ServicePurpose) {
  return servicePurposeOptions.find((item) => item.value === value)?.label || '其他服务'
}

function connectivityLabel(value: ConnectivityState | undefined) {
  return ({ ready: '可用', incomplete: '待完善', failed: '检查失败', unchecked: '未检查' } as const)[value || 'unchecked']
}

function connectivityColor(value: ConnectivityState | undefined) {
  return ({ ready: 'green', incomplete: 'gold', failed: 'red', unchecked: 'default' } as const)[value || 'unchecked']
}

async function loadServices() {
  serviceLoading.value = true
  try {
    const response = await listServiceConfigs() as any
    services.value = response.data?.items || []
  } finally {
    serviceLoading.value = false
  }
}

async function loadOperationHealth() {
  healthLoading.value = true
  try {
    const response = await getOperationHealth() as any
    operationHealth.value = response.data
    operationMessage.value = '任务健康状态已更新'
  } finally {
    healthLoading.value = false
  }
}

async function handleCreateService() {
  serviceLoading.value = true
  try {
    await createServiceConfig({
      ...serviceForm.value,
      credential: serviceForm.value.credential || undefined,
    })
    serviceForm.value.credential = ''
    operationMessage.value = '服务配置已保存'
    message.success('服务配置已保存')
    await loadServices()
  } finally {
    serviceLoading.value = false
  }
}

async function handleEnableService(record: ServiceConfig) {
  if (record.id === null) return
  await setServiceEnabled(record.id, true)
  operationMessage.value = `${formatServiceName(record)}已启用`
  await loadServices()
}

async function handleCheckService(record: ServiceConfig) {
  if (record.id === null) return
  checkingServiceId.value = record.id
  try {
    const response = await checkServiceConnection(record.id) as any
    const availability = String(response.data?.availability || '')
    connectivity.value[serviceKey(record)] = availability === 'available' ? 'ready' : 'incomplete'
    operationMessage.value = `${formatServiceName(record)}连通性检查完成`
  } catch {
    connectivity.value[serviceKey(record)] = 'failed'
  } finally {
    checkingServiceId.value = null
  }
}

onMounted(() => {
  void Promise.all([loadServices(), loadOperationHealth()])
})
</script>

<style scoped>
.system-page {
  color: inherit;
}

.operation-message {
  min-height: 20px;
  margin-bottom: 8px;
  color: #71717A;
  font-size: 12px;
}

.operations-grid {
  display: grid;
  grid-template-columns: minmax(620px, 1.5fr) minmax(300px, 0.8fr);
  gap: 16px;
  margin-bottom: 20px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.wide-field {
  grid-column: 1 / -1;
}

.form-footer,
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.health-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 78px;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #FFFFFF;
  border: 1px solid #E4E4E7;
  border-radius: 6px;
}

.health-warning {
  border-color: #E4E4E7;
  background: #FFFFFF;
}

.health-active {
  border-color: #E4E4E7;
  background: #FFFFFF;
}

.health-indicator {
  width: 10px;
  height: 10px;
  flex: 0 0 10px;
  border-radius: 50%;
  background: #059669;
  box-shadow: 0 0 0 2px rgba(5, 150, 105, 0.15);
}

.health-warning .health-indicator {
  background: #D97706;
  box-shadow: 0 0 0 2px rgba(217, 119, 6, 0.15);
}

.health-active .health-indicator {
  background: #2563EB;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}

.health-title {
  color: #18181B;
  font-weight: 600;
}

.health-detail,
.secondary-text,
.section-heading p {
  margin: 3px 0 0;
  color: #71717A;
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.health-refresh {
  margin-top: 16px;
}

.service-section {
  padding-top: 4px;
}

.section-heading {
  margin-bottom: 12px;
}

.section-heading h2 {
  margin: 0;
  font-size: 18px;
  color: #18181B;
}

@media (max-width: 1280px) {
  .operations-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
