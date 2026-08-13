<template>
  <div class="analysis-page">
    <PageHeader title="语义辅助分析" />
    <a-card size="small" class="toolbar">
      <a-space wrap>
        <a-input v-model:value="runId" allow-clear placeholder="输入 AnalysisRun ID" aria-label="AnalysisRun ID" />
        <a-button type="primary" :loading="loading" :disabled="!runId.trim()" @click="loadArtifact">读取语义结果</a-button>
      </a-space>
      <a-alert v-if="errorText" class="status-alert" type="error" show-icon :message="errorText" />
      <a-alert v-else-if="artifact?.runtime_status === 'blocked'" class="status-alert" type="error" show-icon message="语义模型未就绪" :description="artifact.blocking_reason || '请先准备本地模型权重'" />
    </a-card>

    <template v-if="artifact?.runtime_status === 'ready'">
      <a-alert class="status-alert" type="success" show-icon message="真实本地模型语义结果" :description="modelSummary" />
      <section class="summary-grid">
        <a-card size="small" title="关键词"><a-tag v-for="item in topKeywords" :key="item.term">{{ item.term }}</a-tag><span v-if="!topKeywords.length" class="muted">暂无</span></a-card>
        <a-card size="small" title="主题"><a-tag v-for="item in topTopics" :key="item.id">{{ item.label }}</a-tag><span v-if="!topTopics.length" class="muted">暂无</span></a-card>
        <a-card size="small" title="情感分布"><a-descriptions size="small" :column="1"><a-descriptions-item v-for="(value, key) in sentimentDistribution" :key="key" :label="String(key)">{{ value }}</a-descriptions-item></a-descriptions></a-card>
        <a-card size="small" title="NER 高频实体"><a-tag v-for="item in topEntities" :key="`${item.text}-${item.label}`">{{ item.text }} · {{ item.label }}</a-tag><span v-if="!topEntities.length" class="muted">暂无</span></a-card>
      </section>

      <a-card size="small" title="主帖 / 评论语义矩阵" class="section-card">
        <a-table :data-source="layerRows" :columns="columns" :pagination="{ pageSize: 10 }" row-key="id" size="small" />
      </a-card>
      <section class="cross-grid">
        <a-card size="small" title="时间切片"><a-list size="small" :data-source="artifact.cross_analysis?.time_slices || []"><template #renderItem="{ item }"><a-list-item>{{ item.date }}：{{ item.count }}</a-list-item></template></a-list></a-card>
        <a-card size="small" title="平台切片"><a-list size="small" :data-source="artifact.cross_analysis?.platform_slices || []"><template #renderItem="{ item }"><a-list-item>{{ item.platform }}：{{ item.count }}</a-list-item></template></a-list></a-card>
        <a-card size="small" title="协调社区"><a-list size="small" :data-source="artifact.cross_analysis?.community_slices || []"><template #renderItem="{ item }"><a-list-item>{{ item.community_id }}：{{ item.item_count }}</a-list-item></template></a-list><span v-if="artifact.cross_analysis?.community_slices_unavailable_reason" class="muted">{{ artifact.cross_analysis.community_slices_unavailable_reason }}</span></a-card>
      </section>
      <a-card size="small" title="传播路径语义摘要" class="section-card">
        <a-list size="small" :data-source="artifact.cross_analysis?.propagation_path_overlays || []"><template #renderItem="{ item }"><a-list-item><a-space direction="vertical" size="small"><strong>{{ item.path_id || '传播路径' }}</strong><span>{{ item.semantic_overlay?.evidence_refs?.join(' → ') || '无直接 post → comment 证据' }}</span><span class="muted">平台：{{ item.semantic_overlay?.platforms?.join('、') || '未知' }}</span></a-space></a-list-item></template></a-list>
        <a-empty v-if="!(artifact.cross_analysis?.propagation_path_overlays || []).length" description="暂无可解析的直接传播路径" />
      </a-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { getAnalysisArtifact } from '@/api/analysis'

const runId = ref('')
const loading = ref(false)
const errorText = ref('')
const artifact = ref<Record<string, any> | null>(null)

const allRows = computed(() => [...(artifact.value?.layers?.posts || []), ...(artifact.value?.layers?.comments || [])])
const layerRows = computed(() => allRows.value.map((row: any) => ({
  ...row,
  layer: artifact.value?.layers?.comments?.some((item: any) => item.id === row.id) ? '评论' : '主帖',
  sentimentLabel: row.sentiment?.label || 'unknown',
  stanceLabel: row.stance?.label || (row.stance?.status === 'blocked_missing_primary_claim' ? '缺少主张' : 'unknown'),
  topicLabel: row.topics?.map((item: any) => item.label).filter(Boolean).join('、') || '暂无',
  keywordLabel: row.keywords?.map((item: any) => item.term).filter(Boolean).join('、') || '暂无',
  entityLabel: row.entities?.map((item: any) => item.text).filter(Boolean).join('、') || '暂无',
})))
const columns = [
  { title: '层级', dataIndex: 'layer', key: 'layer' },
  { title: '平台', dataIndex: 'platform', key: 'platform' },
  { title: '情感', dataIndex: 'sentimentLabel', key: 'sentimentLabel' },
  { title: '立场', dataIndex: 'stanceLabel', key: 'stanceLabel' },
  { title: '主题', dataIndex: 'topicLabel', key: 'topicLabel' },
  { title: '关键词', dataIndex: 'keywordLabel', key: 'keywordLabel' },
  { title: '实体', dataIndex: 'entityLabel', key: 'entityLabel' },
]
const topKeywords = computed(() => artifact.value?.layers ? allRows.value.flatMap((row: any) => row.keywords || []).slice(0, 12) : [])
const topTopics = computed(() => artifact.value?.layers ? allRows.value.flatMap((row: any) => row.topics || []).slice(0, 12) : [])
const topEntities = computed(() => artifact.value?.layers ? allRows.value.flatMap((row: any) => row.entities || []).slice(0, 12) : [])
const sentimentDistribution = computed(() => allRows.value.reduce((result: Record<string, number>, row: any) => {
  const label = row.sentiment?.label || 'unknown'
  result[label] = (result[label] || 0) + 1
  return result
}, {}))
const modelSummary = computed(() => Object.values(artifact.value?.model_versions || {}).join('；'))

async function loadArtifact() {
  errorText.value = ''
  artifact.value = null
  loading.value = true
  try {
    artifact.value = (await getAnalysisArtifact(runId.value.trim())).data
  } catch (error: any) {
    errorText.value = error?.response?.data?.detail || '无法读取语义 artifact，请检查 AnalysisRun ID 和模型状态'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.analysis-page { color: #1f2329; }
.toolbar, .section-card { margin-bottom: 16px; }
.status-alert { margin-top: 12px; }
.summary-grid, .cross-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.cross-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.muted { color: #8c8c8c; }
@media (max-width: 900px) { .summary-grid, .cross-grid { grid-template-columns: 1fr; } }
</style>

