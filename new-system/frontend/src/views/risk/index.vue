<!--
  风险研判页面：阶段检测 + D-S 融合 + DISARM 攻击路径分析
-->
<template>
  <div>
    <PageHeader title="风险研判">
      <template #description>
        基于阶段感知危险模型、Dempster-Shafer 证据融合和 DISARM 攻击路径分析，
        对协同操纵事件进行多维风险评估。需先在「数据采集」中创建任务。
      </template>
    </PageHeader>

    <!-- 参数 + 操作 -->
    <a-card size="small" style="margin-bottom: 16px">
      <a-form layout="inline" :model="params" @finish="handleAssess">
        <a-form-item label="平台">
          <a-select v-model:value="params.platform" placeholder="全部" allowClear style="width: 140px">
            <a-select-option value="mock_weibo">Mock 微博</a-select-option>
            <a-select-option value="weibo">微博</a-select-option>
            <a-select-option value="news">新闻</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="时间窗口(秒)">
          <a-input-number v-model:value="params.time_window" :min="1" :max="3600" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="assessing">运行评估</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 概览卡片 -->
    <a-row :gutter="16" style="margin-bottom: 16px" v-if="report">
      <a-col :span="4">
        <a-card size="small">
          <a-statistic title="综合风险" :value="report.scores.overall_risk_score" suffix="分"
            :valueStyle="{ color: riskColor }" />
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card size="small">
          <a-statistic title="风险等级" :value="report.scores.risk_level" :valueStyle="{ color: riskColor }" />
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card size="small">
          <a-statistic title="当前阶段" :value="phaseLabel" />
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card size="small">
          <a-statistic title="证据冲突" :value="(report.fusion.conflict_mass * 100).toFixed(1)" suffix="%" />
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card size="small">
          <a-statistic title="攻击路径" :value="report.disarm_analysis.attack_path.score.toFixed(1)" suffix="分" />
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card size="small">
          <a-statistic title="检测技术" :value="report.disarm_analysis.observed_techniques.length" suffix="个" />
        </a-card>
      </a-col>
    </a-row>

    <!-- 三维评分 -->
    <a-card size="small" title="三维评分（D-S 信念区间）" style="margin-bottom: 16px" v-if="report">
      <a-table :columns="scoreColumns" :dataSource="scoreData" :pagination="false" rowKey="dimension" size="small" />
    </a-card>

    <!-- DISARM 攻击路径 -->
    <a-row :gutter="16" style="margin-bottom: 16px" v-if="report">
      <a-col :span="12">
        <a-card size="small" title="观测到的 DISARM 技术">
          <a-table :columns="techColumns" :dataSource="report.disarm_analysis.observed_techniques"
            :pagination="false" rowKey="technique_id" size="small" />
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card size="small" title="预测下一步 & 反制建议">
          <div v-if="report.disarm_analysis.predicted_next.length > 0" style="margin-bottom: 12px">
            <strong>预测下一步：</strong>
            <a-tag v-for="p in report.disarm_analysis.predicted_next" :key="p.technique_id" color="orange">
              {{ p.technique_id }} {{ p.name }} ({{ (p.probability * 100).toFixed(0) }}%)
            </a-tag>
          </div>
          <a-table :columns="cmColumns" :dataSource="report.disarm_analysis.countermeasures"
            :pagination="false" rowKey="technique_id" size="small" />
        </a-card>
      </a-col>
    </a-row>

    <!-- 风险因子 & 建议 -->
    <a-row :gutter="16" style="margin-bottom: 16px" v-if="report">
      <a-col :span="12">
        <a-card size="small" title="风险因子">
          <div v-for="(factors, key) in report.risk_factors" :key="key" style="margin-bottom: 8px">
            <strong>{{ factorLabels[key] || key }}：</strong>
            <a-tag v-for="(f, i) in factors" :key="i" style="margin: 2px">{{ f }}</a-tag>
            <span v-if="factors.length === 0" style="color: #999">无</span>
          </div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card size="small" title="处置建议">
          <a-list :dataSource="report.recommendations" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-tag :color="priorityColor(item.priority)">{{ item.priority }}</a-tag>
                <strong>{{ item.action }}</strong> — {{ item.reason }}
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-if="report.recommendations.length === 0" description="暂无建议" />
        </a-card>
      </a-col>
    </a-row>

    <!-- 历史报告 -->
    <a-card size="small" title="历史报告" v-if="historyItems.length > 0">
      <a-table :columns="historyColumns" :dataSource="historyItems"
        :pagination="{ current: historyPage, pageSize: 10, total: historyTotal }"
        @change="handleHistoryChange" rowKey="report_id" size="small" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import PageHeader from '@/components/PageHeader.vue'
import { assessRisk, listRiskReports } from '@/api/risk'

const params = ref({ platform: undefined as string | undefined, time_window: 60 })
const assessing = ref(false)
const report = ref<any>(null)

const historyItems = ref<any[]>([])
const historyTotal = ref(0)
const historyPage = ref(1)

const phaseLabels: Record<string, string> = {
  seed: '播种期', synchronize: '同步期', breakout: '爆发期',
  saturation: '饱和期', regeneration: '再生期',
}
const phaseLabel = computed(() => report.value ? (phaseLabels[report.value.phase.current_phase] || report.value.phase.current_phase) : '')

const riskColor = computed(() => {
  if (!report.value) return '#999'
  const l = report.value.scores.risk_level
  return l === 'critical' ? '#f5222d' : l === 'high' ? '#fa8c16' : l === 'medium' ? '#faad14' : '#52c41a'
})

const factorLabels: Record<string, string> = {
  manipulation_factors: '操纵性', authenticity_factors: '行为真实性', impact_factors: '影响力',
}

function priorityColor(p: string) {
  return p === 'critical' ? 'red' : p === 'high' ? 'orange' : p === 'medium' ? 'blue' : 'default'
}

const scoreColumns = [
  { title: '维度', dataIndex: 'dimension', width: 120 },
  { title: '分数', dataIndex: 'score', width: 80 },
  { title: '信念 (Bel)', dataIndex: 'belief', width: 100 },
  { title: '似然 (Pl)', dataIndex: 'plausibility', width: 100 },
  { title: '区间', dataIndex: 'interval', width: 160 },
]

const scoreData = computed(() => {
  if (!report.value) return []
  const s = report.value.scores
  return [
    { dimension: '操纵性', score: s.manipulation.score, belief: s.manipulation.belief.toFixed(3), plausibility: s.manipulation.plausibility.toFixed(3), interval: `[${s.manipulation.belief.toFixed(3)}, ${s.manipulation.plausibility.toFixed(3)}]` },
    { dimension: '行为真实性', score: s.authenticity.score, belief: s.authenticity.belief.toFixed(3), plausibility: s.authenticity.plausibility.toFixed(3), interval: `[${s.authenticity.belief.toFixed(3)}, ${s.authenticity.plausibility.toFixed(3)}]` },
    { dimension: '影响力', score: s.impact.score, belief: s.impact.belief.toFixed(3), plausibility: s.impact.plausibility.toFixed(3), interval: `[${s.impact.belief.toFixed(3)}, ${s.impact.plausibility.toFixed(3)}]` },
  ]
})

const techColumns = [
  { title: 'ID', dataIndex: 'technique_id', width: 80 },
  { title: '战术', dataIndex: 'tactic', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '信念', dataIndex: 'belief', width: 80, customRender: ({ text }: any) => text?.toFixed(3) },
]

const cmColumns = [
  { title: '技术', dataIndex: 'technique_id', width: 80 },
  { title: '反制措施', dataIndex: 'action' },
  { title: '优先级', dataIndex: 'priority', width: 80 },
]

const historyColumns = [
  { title: '报告ID', dataIndex: 'report_id', width: 120, ellipsis: true },
  { title: '平台', dataIndex: 'platform', width: 80 },
  { title: '风险分', dataIndex: 'overall_risk_score', width: 80 },
  { title: '等级', dataIndex: 'risk_level', width: 80 },
  { title: '阶段', dataIndex: 'current_phase', width: 80 },
  { title: '冲突', dataIndex: 'conflict_mass', width: 80, customRender: ({ text }: any) => `${(text * 100).toFixed(1)}%` },
  { title: '时间', dataIndex: 'assessed_at', width: 160 },
]

async function handleAssess() {
  assessing.value = true
  try {
    const res = await assessRisk(params.value)
    report.value = res.data.data
    message.success(`评估完成：${report.value.scores.risk_level} (${report.value.scores.overall_risk_score}分)`)
    await loadHistory()
  } catch (e: any) {
    message.error(e.response?.data?.msg || '评估失败')
  } finally {
    assessing.value = false
  }
}

async function loadHistory() {
  try {
    const res = await listRiskReports({ page: historyPage.value, page_size: 10 })
    const d = res.data.data
    historyItems.value = d.items || []
    historyTotal.value = d.total || 0
  } catch { /* ignore */ }
}

function handleHistoryChange(pagination: any) {
  historyPage.value = pagination.current
  loadHistory()
}
</script>
