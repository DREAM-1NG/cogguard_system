<template>
  <div>
    <PageHeader title="风险研判">
      <template #description>
        对已采集的微博帖子执行模块三分析：有害内容检测、立场检测、证据汇聚、阶段评估、DISARM 映射、结构化报告与反制建议。<br />
        首版优先保证可运行与可交付，支持先用 mock 数据验证，再切换真实微博数据。
      </template>
    </PageHeader>

    <a-card size="small" style="margin-bottom: 16px">
      <a-form layout="inline">
        <a-form-item label="平台">
          <a-select v-model:value="form.platform" style="width: 160px" allow-clear>
            <a-select-option value="mock_weibo">模拟微博</a-select-option>
            <a-select-option value="weibo">微博</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="关键词">
          <a-input v-model:value="form.keyword" placeholder="如：热点话题" style="width: 200px" />
        </a-form-item>
        <a-form-item label="立场目标">
          <a-input v-model:value="form.stance_target" placeholder="默认自动推导" style="width: 200px" />
        </a-form-item>
        <a-form-item label="最大帖子数">
          <a-input-number v-model:value="form.max_posts" :min="1" :max="500" style="width: 120px" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" :loading="analyzing" @click="handleAssess">运行风险研判</a-button>
        </a-form-item>
        <a-form-item>
          <a-button :loading="loadingReports" @click="fetchReports">刷新历史</a-button>
        </a-form-item>
        <a-form-item>
          <a-button :disabled="!report" @click="exportCurrentReport">导出 JSON</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :span="6"><a-card size="small"><a-statistic title="总帖子数" :value="report?.input_overview?.total_posts || 0" suffix="条" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic title="总账户数" :value="report?.input_overview?.total_accounts || 0" suffix="个" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic title="风险分数" :value="report?.risk_assessment?.risk_score || 0" :precision="2" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic title="风险等级" :value="report?.risk_assessment?.risk_level || '-'"></a-statistic></a-card></a-col>
    </a-row>

    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :span="12">
        <a-card size="small" title="执行摘要">
          <a-empty v-if="!report" description="运行分析后展示" :image-style="{ height: '40px' }" />
          <template v-else>
            <p style="margin-bottom: 12px">{{ report.executive_summary }}</p>
            <a-space wrap>
              <a-tag color="blue">目标：{{ report.target }}</a-tag>
              <a-tag :color="dataSourceTagColor(report.data_source)">来源：{{ dataSourceLabel(report.data_source) }}</a-tag>
              <a-tag color="purple">阶段：{{ report.risk_assessment.phase_label }}</a-tag>
              <a-tag :color="riskTagColor(report.risk_assessment.risk_level)">等级：{{ report.risk_assessment.risk_level }}</a-tag>
              <a-tag color="orange">突破概率：{{ percent(report.risk_assessment.breakout_likelihood) }}</a-tag>
            </a-space>
          </template>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card size="small" title="立场 / 有害内容分布">
          <a-empty v-if="!report" description="运行分析后展示" :image-style="{ height: '40px' }" />
          <template v-else>
            <div class="distribution-block">
              <div>
                <h4>有害内容</h4>
                <a-space wrap>
                  <a-tag color="red">harmful: {{ report.harmful_content.distribution.harmful || 0 }}</a-tag>
                  <a-tag color="gold">borderline: {{ report.harmful_content.distribution.borderline || 0 }}</a-tag>
                  <a-tag color="green">safe: {{ report.harmful_content.distribution.safe || 0 }}</a-tag>
                </a-space>
              </div>
              <div>
                <h4>立场</h4>
                <a-space wrap>
                  <a-tag color="blue">support: {{ report.stance_analysis.distribution.support || 0 }}</a-tag>
                  <a-tag color="red">deny: {{ report.stance_analysis.distribution.deny || 0 }}</a-tag>
                  <a-tag color="orange">query: {{ report.stance_analysis.distribution.query || 0 }}</a-tag>
                  <a-tag>comment: {{ report.stance_analysis.distribution.comment || 0 }}</a-tag>
                </a-space>
              </div>
            </div>
          </template>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :span="12">
        <a-card size="small" title="核心证据">
          <a-empty v-if="!report" description="运行分析后展示" :image-style="{ height: '40px' }" />
          <template v-else>
            <a-descriptions :column="1" size="small" bordered>
              <a-descriptions-item label="协同账户数">{{ report.evidence.coordination.summary.coordinated_accounts }}</a-descriptions-item>
              <a-descriptions-item label="协同边数">{{ report.evidence.coordination.summary.coordinated_edges }}</a-descriptions-item>
              <a-descriptions-item label="传播边数">{{ report.evidence.propagation.graph.edge_count }}</a-descriptions-item>
              <a-descriptions-item label="平均自动化评分">{{ report.evidence.accounts.avg_automation_score }}</a-descriptions-item>
              <a-descriptions-item label="风险依据">
                <a-space wrap>
                  <a-tag v-for="item in report.risk_assessment.rationale" :key="item" color="processing">{{ item }}</a-tag>
                </a-space>
              </a-descriptions-item>
            </a-descriptions>
          </template>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card size="small" title="DISARM 映射">
          <a-empty v-if="!report" description="运行分析后展示" :image-style="{ height: '40px' }" />
          <template v-else>
            <a-list :data-source="report.disarm_assessment.mapped_techniques" size="small">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta :title="`${item.tactic} / ${item.technique}`" :description="item.reason" />
                  <div>{{ item.score }}</div>
                </a-list-item>
              </template>
            </a-list>
          </template>
        </a-card>
      </a-col>
    </a-row>

    <a-card size="small" style="margin-bottom: 16px">
      <template #title>LLM 预留接口</template>
      <a-empty v-if="!report" description="运行分析后展示" :image-style="{ height: '40px' }" />
      <template v-else>
        <a-descriptions :column="1" size="small" bordered>
          <a-descriptions-item label="状态">{{ report.llm_enhancement.status }}</a-descriptions-item>
          <a-descriptions-item label="提供方">{{ report.llm_enhancement.provider }}</a-descriptions-item>
          <a-descriptions-item label="模型">{{ report.llm_enhancement.model || '-' }}</a-descriptions-item>
          <a-descriptions-item label="说明">{{ report.llm_enhancement.reason }}</a-descriptions-item>
          <a-descriptions-item label="建议 Prompt">
            <a-typography-paragraph copyable style="margin-bottom: 0; white-space: pre-wrap">{{ report.llm_enhancement.suggested_prompt }}</a-typography-paragraph>
          </a-descriptions-item>
        </a-descriptions>
      </template>
    </a-card>

    <a-card size="small" style="margin-bottom: 16px">
      <template #title>高风险帖子</template>
      <template #extra v-if="report?.harmful_content?.top_posts?.length">
        <TableSettings v-model:size="tableSize" v-model:pageSize="pageSize" />
      </template>
      <a-table
        v-if="report?.harmful_content?.top_posts?.length"
        :columns="postColumns"
        :data-source="report.harmful_content.top_posts"
        rowKey="post_id"
        :size="tableSize"
        :pagination="{ pageSize }"
      />
      <a-empty v-else description="运行分析后展示" :image-style="{ height: '40px' }" />
    </a-card>

    <a-row :gutter="16">
      <a-col :span="14">
        <a-card size="small" title="反制建议">
          <a-empty v-if="!report" description="运行分析后展示" :image-style="{ height: '40px' }" />
          <template v-else>
            <a-timeline>
              <a-timeline-item v-for="(item, idx) in report.countermeasures" :key="idx" :color="priorityColor(item.priority)">
                <p style="margin-bottom: 4px"><strong>{{ item.action }}</strong> <a-tag>{{ item.priority }}</a-tag></p>
                <p style="margin: 0">{{ item.description }}</p>
              </a-timeline-item>
            </a-timeline>
          </template>
        </a-card>
      </a-col>
      <a-col :span="10">
        <a-card size="small" title="历史报告">
          <a-list v-if="reports.length > 0" :data-source="reports" size="small">
            <template #renderItem="{ item }">
              <a-list-item @click="selectReport(item)" style="cursor: pointer">
                <a-list-item-meta :title="item.executive_summary" :description="`${item.platform || 'all'} / ${item.target}`" />
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else description="暂无历史报告" :image-style="{ height: '40px' }" />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { assessRisk, getRiskReport, listRiskReports } from '@/api/risk'
import PageHeader from '@/components/PageHeader.vue'
import TableSettings from '@/components/TableSettings.vue'

const analyzing = ref(false)
const loadingReports = ref(false)
const report = ref<any | null>(null)
const reports = ref<any[]>([])
const tableSize = ref<'small' | 'middle' | 'default'>('middle')
const pageSize = ref(10)

const form = reactive({
  platform: 'mock_weibo',
  keyword: '',
  stance_target: '',
  max_posts: 50,
})

const postColumns = [
  { title: '帖子ID', dataIndex: 'post_id', key: 'post_id', width: 120, ellipsis: true },
  { title: '作者', dataIndex: 'author_id', key: 'author_id', width: 120, ellipsis: true },
  { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
  { title: '有害标签', dataIndex: 'harmful_label', key: 'harmful_label', width: 110 },
  { title: '有害分数', dataIndex: 'harmful_score', key: 'harmful_score', width: 110 },
  { title: '立场', dataIndex: 'stance_label', key: 'stance_label', width: 100 },
]

function percent(value: number) {
  return `${Math.round((value || 0) * 100)}%`
}

function riskTagColor(level: string) {
  if (level === 'critical') return 'red'
  if (level === 'high') return 'volcano'
  if (level === 'medium') return 'gold'
  return 'green'
}

function priorityColor(priority: string) {
  if (priority === 'high') return 'red'
  if (priority === 'medium') return 'orange'
  return 'blue'
}

function dataSourceLabel(source?: string) {
  if (source === 'mongo') return '已采集数据'
  if (source === 'mock_fallback') return 'Mock 回退数据'
  return '未知来源'
}

function dataSourceTagColor(source?: string) {
  if (source === 'mongo') return 'green'
  if (source === 'mock_fallback') return 'gold'
  return 'default'
}

async function fetchReports() {
  loadingReports.value = true
  try {
    const res = (await listRiskReports({ platform: form.platform || undefined, limit: 10 })) as any
    reports.value = res.data || []
  } finally {
    loadingReports.value = false
  }
}

function exportCurrentReport() {
  if (!report.value) return
  const blob = new Blob([JSON.stringify(report.value, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `risk-report-${report.value.report_id || 'latest'}.json`
  link.click()
  URL.revokeObjectURL(url)
}

async function handleAssess() {
  analyzing.value = true
  try {
    const res = (await assessRisk({
      platform: form.platform || undefined,
      keyword: form.keyword || undefined,
      stance_target: form.stance_target || undefined,
      max_posts: form.max_posts,
    })) as any
    if (!res.data) {
      message.warning(res.msg || '暂无可分析数据')
      return
    }
    report.value = res.data
    message.success(
      report.value.data_source === 'mock_fallback'
        ? '风险研判完成（当前使用 Mock 回退数据）'
        : '风险研判完成'
    )
    await fetchReports()
  } catch {
    /* handled by interceptor */
  } finally {
    analyzing.value = false
  }
}

async function selectReport(item: any) {
  const reportId = item?.report_id
  if (!reportId) {
    report.value = item
    return
  }
  loadingReports.value = true
  try {
    const res = (await getRiskReport(reportId)) as any
    report.value = res.data || item
  } finally {
    loadingReports.value = false
  }
}

onMounted(fetchReports)
</script>

<style scoped>
.distribution-block {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.distribution-block h4 {
  margin-bottom: 8px;
}
</style>
