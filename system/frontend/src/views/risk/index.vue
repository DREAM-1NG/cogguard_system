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
        <a-form-item label="事件ID">
          <a-input v-model:value="params.event_id" allowClear placeholder="可选" style="width: 180px" />
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
          <a-statistic title="KT3 Harm" :value="kt3RiskLabel" :valueStyle="{ color: kt3RiskColor }" />
        </a-card>
      </a-col>
    </a-row>

    <!-- 三维评分 -->
    <a-card size="small" title="三维评分（D-S 信念区间）" style="margin-bottom: 16px" v-if="report">
      <a-table :columns="scoreColumns" :dataSource="scoreData" :pagination="false" rowKey="dimension" size="small" />
    </a-card>

    <!-- KT3 分层 harmfulness -->
    <a-card size="small" title="KT3 分层 Harmfulness Characterization" style="margin-bottom: 16px" v-if="report">
      <template v-if="kt3">
        <a-row :gutter="16" style="margin-bottom: 12px">
          <a-col :span="6">
            <a-statistic title="KT3 风险等级" :value="kt3RiskLabel" :valueStyle="{ color: kt3RiskColor }" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="有害账户" :value="kt3.user_level?.summary?.harmful_accounts || 0" suffix="个" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="有害社区" :value="kt3.community_level?.summary?.harmful_communities || 0" suffix="个" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="语义帖子" :value="kt3.audit?.semantic_posts_used || 0" suffix="条" />
          </a-col>
        </a-row>

        <a-descriptions size="small" bordered :column="2" style="margin-bottom: 12px">
          <a-descriptions-item label="建模边界">
            {{ kt3.capability_boundary?.modeling_note || '暂无' }}
          </a-descriptions-item>
          <a-descriptions-item label="Claim 未匹配率">
            {{ percentText(kt3.audit?.missing_claim_match_ratio) }}
          </a-descriptions-item>
        </a-descriptions>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-table
              title="用户级 harmfulness"
              :columns="kt3AccountColumns"
              :dataSource="kt3AccountRows"
              :pagination="false"
              rowKey="account_id"
              size="small"
            />
          </a-col>
          <a-col :span="12">
            <a-table
              title="社区级 harmfulness"
              :columns="kt3CommunityColumns"
              :dataSource="kt3CommunityRows"
              :pagination="false"
              rowKey="community_id"
              size="small"
            />
          </a-col>
        </a-row>

        <div style="margin-top: 12px">
          <strong>Top Harmful Claims：</strong>
          <a-tag v-for="claim in kt3TopClaims" :key="claim.claim_id" color="volcano" style="margin: 2px">
            {{ claim.claim_id }} · H{{ claim.harmful_posts || 0 }}/L{{ claim.linked_posts || 0 }}
          </a-tag>
          <span v-if="kt3TopClaims.length === 0" style="color: #999">暂无</span>
        </div>

        <a-divider style="margin: 12px 0" />
        <div v-if="kt3GateSuite" style="margin-bottom: 12px">
          <strong>KT3 Gate Suite 验收汇总：</strong>
          <a-tag color="green" style="margin: 2px">执行 {{ kt3GateSummary.executed_gates || 0 }}</a-tag>
          <a-tag color="orange" style="margin: 2px">跳过 {{ kt3GateSummary.skipped_gates || 0 }}</a-tag>
          <a-tag :color="kt3GateSummary.overall_pass ? 'green' : 'default'" style="margin: 2px">
            Overall {{ kt3GateSummary.overall_pass ? 'Pass' : 'Not Passed' }}
          </a-tag>
          <span style="color: #999; margin-left: 8px">{{ kt3GateBoundary }}</span>
        </div>
        <a-table
          v-if="kt3GateRows.length > 0"
          :columns="kt3GateColumns"
          :dataSource="kt3GateRows"
          :pagination="false"
          rowKey="gate"
          size="small"
          style="margin-bottom: 12px"
        />

        <div>
          <strong>KT3 Agent/RAG 复核队列：</strong>
          <a-tag color="orange" style="margin: 2px">复核项 {{ kt3ReviewSummary.review_items || 0 }}</a-tag>
          <a-tag color="blue" style="margin: 2px">检索任务 {{ kt3ReviewSummary.retrieval_tasks || 0 }}</a-tag>
          <a-tag color="purple" style="margin: 2px">Agent 任务 {{ kt3ReviewSummary.agent_tasks || 0 }}</a-tag>
          <a-tag color="default" style="margin: 2px">{{ kt3ReviewSummary.recommended_next_action || 'no_review_required' }}</a-tag>
          <span style="color: #999; margin-left: 8px">
            {{ kt3ReviewBoundary }}
          </span>
        </div>
        <a-table
          v-if="kt3ReviewRows.length > 0"
          :columns="kt3ReviewColumns"
          :dataSource="kt3ReviewRows"
          :pagination="false"
          rowKey="id"
          size="small"
          style="margin-top: 8px"
        />

        <a-divider style="margin: 12px 0" />
        <div>
          <strong>KT3 MARO-style Manual Agent Review:</strong>
          <a-tag color="gold" style="margin: 2px">human-triggered LLM</a-tag>
          <a-tag color="default" style="margin: 2px">natural-language reports</a-tag>
          <a-tag color="default" style="margin: 2px">not benchmark fitting</a-tag>
          <span style="color: #999; margin-left: 8px">
            {{ kt3AgentSuggestions?.review_reason || 'Select suggested agents and run manual review.' }}
          </span>
        </div>
        <div style="margin-top: 8px">
          <a-tag
            v-for="item in kt3SuggestedAgents"
            :key="item.agent_name"
            color="blue"
            style="margin: 2px"
          >
            {{ item.agent_name }}: {{ item.reason }}
          </a-tag>
          <span v-if="kt3SuggestedAgents.length === 0" style="color: #999">No suggested agents</span>
        </div>
        <a-row :gutter="8" style="margin-top: 8px">
          <a-col :span="8">
            <a-select
              v-model:value="kt3SelectedAgents"
              mode="multiple"
              placeholder="Select KT3 agents"
              style="width: 100%"
            >
              <a-select-option v-for="name in kt3AllAgents" :key="name" :value="name">{{ name }}</a-select-option>
            </a-select>
          </a-col>
          <a-col :span="5">
            <a-input v-model:value="kt3SelectedPostIds" placeholder="Post IDs, e.g. p1,p2" />
          </a-col>
          <a-col :span="5">
            <a-input v-model:value="kt3SelectedTreeIds" placeholder="Tree IDs, optional" />
          </a-col>
          <a-col :span="6">
            <a-input v-model:value="kt3PolicyId" placeholder="Active policy ID, optional" />
          </a-col>
        </a-row>
        <a-row :gutter="8" style="margin-top: 8px">
          <a-col :span="8">
            <a-checkbox v-model:checked="kt3EnableActiveRetrieval">Active retrieval</a-checkbox>
            <a-checkbox v-model:checked="kt3EnableLightDebate" style="margin-left: 12px">Light debate</a-checkbox>
            <a-checkbox v-model:checked="kt3EnableFullDebate" style="margin-left: 12px">Full debate</a-checkbox>
          </a-col>
          <a-col :span="5">
            <a-input-number v-model:value="kt3RetrievalTopK" :min="1" :max="10" style="width: 100%" placeholder="Top K" />
          </a-col>
          <a-col :span="3">
            <a-input-number v-model:value="kt3DebateMaxRounds" :min="1" :max="5" style="width: 100%" placeholder="Debate rounds" />
          </a-col>
          <a-col :span="6">
            <a-button size="small" @click="fillSuggestedKT3Agents">Use suggested</a-button>
            <a-button
              size="small"
              type="primary"
              style="margin-left: 8px"
              :loading="kt3AgentReviewLoading"
              @click="handleRunKT3AgentReviewAscii"
            >
              Run review
            </a-button>
          </a-col>
        </a-row>
        <a-list
          v-if="kt3AgentReviews.length > 0"
          :dataSource="kt3AgentReviews"
          size="small"
          style="margin-top: 8px"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <a-card size="small" style="width: 100%">
                <template #title>
                  {{ item.agent_name }} · {{ item.status }}
                </template>
                <div v-if="agentAuditSidecar(item)" style="margin-bottom: 8px">
                  <a-tag color="cyan">system audit sidecar</a-tag>
                  <a-tag :color="agentAuditSidecar(item).active_retrieval_used ? 'blue' : 'default'">
                    retrieval {{ agentAuditSidecar(item).active_retrieval_used ? 'on' : 'off' }}
                  </a-tag>
                  <a-tag :color="agentAuditSidecar(item).light_debate_used ? 'orange' : 'default'">
                    debate {{ agentAuditSidecar(item).light_debate_used ? 'on' : 'off' }}
                  </a-tag>
                  <a-tag color="default">confidence {{ percentText(agentAuditSidecar(item).confidence) }}</a-tag>
                  <a-tag color="default">evidence {{ agentAuditSidecar(item).evidence_refs?.length || 0 }}</a-tag>
                  <div style="color: #666; margin-top: 4px">
                    Queries: {{ compactList(agentAuditSidecar(item).retrieval_queries, 2) }}
                  </div>
                  <div style="color: #666">
                    Actions: {{ compactList(agentAuditSidecar(item).suggested_actions, 4) }}
                  </div>
                  <div v-if="agentAuditSidecar(item).uncertainties?.length" style="color: #999">
                    Uncertainties: {{ compactList(agentAuditSidecar(item).uncertainties, 4) }}
                  </div>
                </div>
                <pre style="white-space: pre-wrap; margin: 0">{{ item.analysis_report?.text || item.report_text || item.error }}</pre>
              </a-card>
            </a-list-item>
          </template>
        </a-list>

        <div v-if="kt3ReviewExecution" style="margin-top: 12px">
          <strong>KT3 本地复核执行：</strong>
          <a-tag color="green" style="margin: 2px">已执行 {{ kt3ExecutionSummary.review_items_executed || 0 }}</a-tag>
          <a-tag color="blue" style="margin: 2px">本地检索 {{ kt3ExecutionSummary.retrieval_tasks_executed || 0 }}</a-tag>
          <a-tag color="orange" style="margin: 2px">需外部复核 {{ kt3ExecutionSummary.external_review_required || 0 }}</a-tag>
          <a-tag color="default" style="margin: 2px">Avg {{ percentText(kt3ExecutionSummary.avg_local_confidence) }}</a-tag>
          <span style="color: #999; margin-left: 8px">{{ kt3ExecutionBoundary }}</span>
        </div>
        <a-table
          v-if="kt3ExecutionRows.length > 0"
          :columns="kt3ExecutionColumns"
          :dataSource="kt3ExecutionRows"
          :pagination="false"
          rowKey="item_id"
          size="small"
          style="margin-top: 8px"
        />

        <div v-if="kt3GraphExport" style="margin-top: 12px">
          <strong>KT3 异构图导出：</strong>
          <a-tag color="cyan" style="margin: 2px">节点 {{ kt3GraphSummary.node_count || 0 }}</a-tag>
          <a-tag color="geekblue" style="margin: 2px">边 {{ kt3GraphSummary.edge_count || 0 }}</a-tag>
          <a-tag color="green" style="margin: 2px">Graph Ready {{ kt3GraphSummary.graph_native_ready ? '是' : '否' }}</a-tag>
          <a-tag color="default" style="margin: 2px">Graph Model {{ kt3GraphBoundary }}</a-tag>
          <span style="color: #999; margin-left: 8px">
            {{ kt3GraphTypeText }}
          </span>
        </div>
      </template>
      <a-empty v-else description="当前报告未包含 KT3 分层 harmfulness 输出" />
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

    <!-- KT3 Gate Dataset 契约与离线验收 -->
    <a-card size="small" title="KT3 Gate Dataset 契约与离线验收" style="margin-bottom: 16px">
      <a-alert
        type="info"
        show-icon
        style="margin-bottom: 12px"
        message="该区域只用于查看/校验 KT3 gold-control 契约；validate 不运行风险评估，Gate Suite 默认不持久化 gold/control 结果。"
      />
      <div style="margin-bottom: 12px">
        <a-button size="small" type="primary" :loading="kt3ContractLoading" @click="loadKT3Contract">
          加载契约
        </a-button>
        <a-button size="small" style="margin-left: 8px" :disabled="!kt3Contract" @click="fillKT3DatasetExample">
          填入示例 JSON
        </a-button>
        <a-button size="small" style="margin-left: 8px" :loading="kt3ValidationLoading" @click="handleValidateKT3Dataset">
          校验数据集
        </a-button>
        <a-button size="small" style="margin-left: 8px" :loading="kt3GateSuiteLoading" @click="handleRunKT3GateSuite">
          运行离线 Gate Suite
        </a-button>
      </div>

      <a-descriptions v-if="kt3Contract" size="small" bordered :column="2" style="margin-bottom: 12px">
        <a-descriptions-item label="契约版本">{{ kt3Contract.contract_version }}</a-descriptions-item>
        <a-descriptions-item label="契约类型">{{ kt3Contract.artifact_type }}</a-descriptions-item>
        <a-descriptions-item label="必填 metadata">{{ kt3RequiredMetadataText }}</a-descriptions-item>
        <a-descriptions-item label="层级">{{ kt3ContractLayerText }}</a-descriptions-item>
        <a-descriptions-item label="正式验收字段">{{ kt3ReadinessMetadataText }}</a-descriptions-item>
        <a-descriptions-item label="正式验收层级">{{ kt3ReadinessLayerText }}</a-descriptions-item>
        <a-descriptions-item label="Manifest 算法">{{ kt3Contract.manifest_policy?.fingerprint_algorithm || 'N/A' }}</a-descriptions-item>
        <a-descriptions-item label="Manifest 是否含 gold">{{ kt3Contract.manifest_policy?.contains_gold_payload ? '是' : '否' }}</a-descriptions-item>
      </a-descriptions>

      <a-textarea
        v-model:value="kt3DatasetJson"
        :rows="8"
        placeholder="粘贴 kt3_gate_dataset JSON；也可以先加载契约后填入 example_skeleton"
        style="font-family: Consolas, monospace; margin-bottom: 12px"
      />

      <div v-if="kt3Validation" style="margin-bottom: 12px">
        <strong>契约校验：</strong>
        <a-tag :color="kt3Validation.valid ? 'green' : 'orange'" style="margin: 2px">
          {{ kt3Validation.valid ? 'valid' : 'needs-fix' }}
        </a-tag>
        <a-tag color="blue" style="margin: 2px">post {{ kt3Validation.layer_coverage?.post_gate ? 'on' : 'off' }}</a-tag>
        <a-tag color="blue" style="margin: 2px">user {{ kt3Validation.layer_coverage?.user_gate ? 'on' : 'off' }}</a-tag>
        <a-tag color="blue" style="margin: 2px">community {{ kt3Validation.layer_coverage?.community_gate ? 'on' : 'off' }}</a-tag>
        <a-tag :color="kt3Validation.formal_acceptance_ready ? 'green' : 'orange'" style="margin: 2px">
          formal {{ kt3Validation.formal_acceptance_ready ? 'ready' : 'not-ready' }}
        </a-tag>
        <a-tag color="default" style="margin: 2px">fingerprint {{ shortFingerprint(kt3Validation.manifest?.dataset_fingerprint) }}</a-tag>
        <div style="color: #999; margin-top: 4px">
          counts: post={{ kt3Validation.counts?.post_cases || 0 }},
          user={{ kt3Validation.counts?.user_gold || 0 }},
          community={{ kt3Validation.counts?.community_gold || 0 }};
          warnings={{ kt3Validation.warnings?.length || 0 }};
          missing metadata={{ kt3Validation.missing_metadata_fields?.join(', ') || 'none' }};
          readiness warnings={{ kt3ReadinessWarningText }}
        </div>
        <div style="color: #999; margin-top: 4px">
          readiness:
          required_metadata={{ kt3ReadinessStatus.has_required_metadata ? 'yes' : 'no' }},
          control={{ kt3ReadinessStatus.has_control_notes ? 'yes' : 'no' }},
          split={{ kt3ReadinessStatus.has_split ? 'yes' : 'no' }},
          leakage={{ kt3ReadinessStatus.has_leakage_policy ? 'yes' : 'no' }},
          threshold={{ kt3ReadinessStatus.has_threshold_policy ? 'yes' : 'no' }},
          full_layers={{ kt3ReadinessStatus.has_full_layer_coverage ? 'yes' : 'no' }}
        </div>
      </div>

      <div v-if="kt3OfflineGateSuite" style="margin-bottom: 4px">
        <strong>离线 Gate Suite：</strong>
        <a-tag color="green" style="margin: 2px">执行 {{ kt3OfflineGateSummary.executed_gates || 0 }}</a-tag>
        <a-tag color="orange" style="margin: 2px">跳过 {{ kt3OfflineGateSummary.skipped_gates || 0 }}</a-tag>
        <a-tag :color="kt3OfflineGateSummary.overall_pass ? 'green' : 'default'" style="margin: 2px">
          Overall {{ kt3OfflineGateSummary.overall_pass ? 'Pass' : 'Not Passed' }}
        </a-tag>
        <a-tag color="default" style="margin: 2px">
          persisted {{ kt3GateSuiteResponse?.persistence?.persisted ? 'yes' : 'no' }}
        </a-tag>
        <a-tag color="default" style="margin: 2px">
          manifest {{ shortFingerprint(kt3OfflineGateManifest?.dataset_fingerprint) }}
        </a-tag>
      </div>
    </a-card>

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
import {
  assessKT3GateSuite,
  assessRisk,
  getKT3GateDatasetContract,
  listRiskReports,
  runKT3AgentReview,
  validateKT3GateDataset,
} from '@/api/risk'

const params = ref({
  platform: undefined as string | undefined,
  event_id: undefined as string | undefined,
  time_window: 60,
})
const assessing = ref(false)
const report = ref<any>(null)
const kt3ContractLoading = ref(false)
const kt3ValidationLoading = ref(false)
const kt3GateSuiteLoading = ref(false)
const kt3Contract = ref<any>(null)
const kt3Validation = ref<any>(null)
const kt3GateSuiteResponse = ref<any>(null)
const kt3DatasetJson = ref('')
const kt3AgentReviewLoading = ref(false)
const kt3SelectedAgents = ref<string[]>([])
const kt3SelectedPostIds = ref('')
const kt3SelectedTreeIds = ref('')
const kt3PolicyId = ref('')
const kt3EnableActiveRetrieval = ref(true)
const kt3EnableLightDebate = ref(true)
const kt3EnableFullDebate = ref(false)
const kt3RetrievalTopK = ref(3)
const kt3DebateMaxRounds = ref(3)

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

const kt3 = computed(() => report.value?.kt3_harmfulness || null)
const kt3RiskLabel = computed(() => kt3.value?.global_summary?.kt3_harm_risk_level || 'N/A')
const kt3RiskColor = computed(() => {
  const level = kt3RiskLabel.value
  return level === 'high' ? '#fa8c16' : level === 'medium' ? '#faad14' : level === 'low' ? '#52c41a' : '#999'
})
const kt3ReviewQueue = computed(() => kt3.value?.review_queue || null)
const kt3AgentSuggestions = computed(() => kt3.value?.agent_review_suggestions || null)
const kt3SuggestedAgents = computed(() => kt3AgentSuggestions.value?.suggested_agents || [])
const kt3AllAgents = computed(() => kt3AgentSuggestions.value?.all_agents || [
  'PostHarmAgent',
  'MultimodalConsistencyAgent',
  'ClaimEvidenceAgent',
  'PropagationTreeAgent',
  'QuestionReflectionAgent',
  'HarmfulnessJudgeAgent',
  'CountermeasureAgent',
])
const kt3AgentReviews = computed(() => report.value?.agent_reviews || [])
const kt3GateSuite = computed(() => kt3.value?.gate_suite || null)
const kt3GateSummary = computed(() => kt3GateSuite.value?.summary || {})
const kt3RequiredMetadataText = computed(() => (kt3Contract.value?.required_metadata_fields || []).join(', ') || 'N/A')
const kt3ContractLayerText = computed(() => Object.keys(kt3Contract.value?.layer_contracts || {}).join(', ') || 'N/A')
const kt3ReadinessMetadataText = computed(() => (kt3Contract.value?.readiness_policy?.formal_acceptance_metadata_fields || []).join(', ') || 'N/A')
const kt3ReadinessLayerText = computed(() => (kt3Contract.value?.readiness_policy?.required_gate_layers || []).join(', ') || 'N/A')
const kt3OfflineGateSuite = computed(() => kt3GateSuiteResponse.value?.gate_suite || null)
const kt3OfflineGateSummary = computed(() => kt3OfflineGateSuite.value?.summary || {})
const kt3OfflineGateManifest = computed(() => kt3OfflineGateSuite.value?.dataset_contract?.manifest || null)
const kt3ReadinessStatus = computed(() => kt3Validation.value?.evaluation_readiness || {})
const kt3ReadinessWarningText = computed(() => kt3Validation.value?.readiness_warnings?.join(', ') || 'none')
const kt3GateBoundary = computed(() => {
  const boundary = kt3GateSuite.value?.capability_boundary
  if (!boundary) return '未生成 Gate Suite'
  return boundary.evaluation_harness_only
    ? '离线评测汇总；无固定 gold 时仅记录 skipped，不代表真实评测已完成'
    : '非标准 Gate Suite 输出'
})
const kt3ReviewSummary = computed(() => kt3ReviewQueue.value?.summary || {})
const kt3ReviewBoundary = computed(() => {
  const boundary = kt3ReviewQueue.value?.capability_boundary
  if (!boundary) return '未生成复核队列'
  return boundary.live_llm_or_rag ? '已接入在线 LLM/RAG 复核' : '当前为复核任务脚手架，尚未执行在线 LLM/RAG'
})
const kt3ReviewExecution = computed(() => kt3.value?.review_execution || null)
const kt3ExecutionSummary = computed(() => kt3ReviewExecution.value?.summary || {})
const kt3ExecutionBoundary = computed(() => {
  const boundary = kt3ReviewExecution.value?.capability_boundary
  if (!boundary) return '未执行本地复核'
  return boundary.live_llm_or_external_rag
    ? '已接入外部 LLM/RAG'
    : '本地确定性复核执行，未调用外部 LLM/RAG'
})
const kt3GraphExport = computed(() => kt3.value?.graph_export || null)
const kt3GraphSummary = computed(() => kt3GraphExport.value?.summary || {})
const kt3GraphBoundary = computed(() => {
  const boundary = kt3GraphExport.value?.capability_boundary
  if (!boundary) return 'N/A'
  return boundary.trained_graph_model ? '已训练' : '未训练，仅导出'
})
const kt3GraphTypeText = computed(() => {
  const nodeTypes = kt3GraphSummary.value?.node_types || {}
  const edgeTypes = kt3GraphSummary.value?.edge_types || {}
  const nodes = Object.entries(nodeTypes).map(([key, value]) => `${key}:${value}`).join(', ')
  const edges = Object.entries(edgeTypes).map(([key, value]) => `${key}:${value}`).join(', ')
  return `nodes { ${nodes || 'none'} } · edges { ${edges || 'none'} }`
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

const kt3AccountColumns = [
  { title: '账户', dataIndex: 'account_id', width: 100, ellipsis: true },
  { title: 'Harmful', dataIndex: 'harmful_posts', width: 80 },
  { title: '持续性', dataIndex: 'persistence_score', width: 80 },
  { title: '轨迹', dataIndex: 'trajectory', width: 120 },
  { title: '角色', dataIndex: 'roles', ellipsis: true },
]

const kt3CommunityColumns = [
  { title: '社区', dataIndex: 'community_id', width: 120, ellipsis: true },
  { title: '成员', dataIndex: 'member_count', width: 70 },
  { title: 'Harmful', dataIndex: 'harmful_posts', width: 80 },
  { title: '放大', dataIndex: 'amplification_score', width: 80 },
  { title: '角色', dataIndex: 'roles', ellipsis: true },
]

const kt3ReviewColumns = [
  { title: '对象', dataIndex: 'id', width: 160, ellipsis: true },
  { title: '类型', dataIndex: 'type', width: 160 },
  { title: '优先级', dataIndex: 'priority', width: 80 },
  { title: 'Agent', dataIndex: 'agent_role', width: 160 },
  { title: '复核原因', dataIndex: 'reason', ellipsis: true },
]

const kt3GateColumns = [
  { title: 'Gate', dataIndex: 'gate', width: 150 },
  { title: '状态', dataIndex: 'status', width: 120 },
  { title: 'Overall', dataIndex: 'overall_pass', width: 100 },
  { title: '失败项', dataIndex: 'failed_items', width: 80 },
  { title: '复核项', dataIndex: 'review_items', width: 80 },
  { title: '说明', dataIndex: 'description', ellipsis: true },
]

const kt3ExecutionColumns = [
  { title: '对象', dataIndex: 'item_id', width: 160, ellipsis: true },
  { title: '角色', dataIndex: 'agent_role', width: 150 },
  { title: '本地结论', dataIndex: 'local_outcome', width: 220, ellipsis: true },
  { title: '置信度', dataIndex: 'local_confidence', width: 90 },
  { title: '需外部复核', dataIndex: 'external_review_required', width: 110 },
  { title: '执行模式', dataIndex: 'execution_mode', ellipsis: true },
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

const kt3AccountRows = computed(() => {
  const accounts = kt3.value?.user_level?.accounts || []
  return accounts.slice(0, 5).map((item: any) => ({
    account_id: item.account_id,
    harmful_posts: item.risk_summary?.harmful_posts || 0,
    persistence_score: item.risk_summary?.persistence_score?.toFixed?.(2) || '0.00',
    trajectory: item.risk_summary?.trajectory || 'unknown',
    roles: (item.role_profile?.harmful_roles || []).join(', '),
  }))
})

const kt3CommunityRows = computed(() => {
  const communities = kt3.value?.community_level?.communities || []
  return communities.slice(0, 5).map((item: any) => ({
    community_id: item.community_id,
    member_count: item.member_count || 0,
    harmful_posts: item.risk_summary?.harmful_posts || 0,
    amplification_score: item.risk_summary?.amplification_score?.toFixed?.(2) || '0.00',
    roles: Object.keys(item.subgroup_roles || {}).join(', '),
  }))
})

const kt3TopClaims = computed(() => kt3.value?.global_summary?.claim_rank?.slice?.(0, 8) || [])
const kt3GateRows = computed(() => {
  const suite = kt3GateSuite.value
  if (!suite) return []
  const gateStatus = suite.summary?.gate_status || {}
  const rows = Object.entries(gateStatus).map(([gate, status]: [string, any]) => ({
    gate,
    status: 'executed',
    overall_pass: status.overall_pass ? 'Pass' : 'Fail',
    failed_items: status.failed_items || 0,
    review_items: status.review_items || 0,
    description: status.failed_thresholds?.length
      ? `failed thresholds: ${status.failed_thresholds.join(', ')}`
      : (status.metrics || []).join(', '),
  }))
  const skipped = suite.skipped_gates || {}
  Object.entries(skipped).forEach(([gate, item]: [string, any]) => {
    rows.push({
      gate,
      status: 'skipped',
      overall_pass: 'N/A',
      failed_items: 0,
      review_items: 0,
      description: `${item.reason || 'missing_input'} · ${item.description || ''}`,
    })
  })
  return rows
})
const kt3ReviewRows = computed(() => kt3ReviewQueue.value?.review_items?.slice?.(0, 5) || [])
const kt3ExecutionRows = computed(() => {
  const rows = kt3ReviewExecution.value?.review_results?.slice?.(0, 5) || []
  return rows.map((item: any) => ({
    ...item,
    local_confidence: typeof item.local_confidence === 'number' ? item.local_confidence.toFixed(2) : item.local_confidence,
    external_review_required: item.external_review_required ? '是' : '否',
  }))
})

function percentText(value: number | undefined) {
  if (typeof value !== 'number') return 'N/A'
  return `${(value * 100).toFixed(1)}%`
}

function shortFingerprint(value: string | undefined) {
  if (!value) return 'N/A'
  return value.length > 12 ? `${value.slice(0, 12)}…` : value
}

function compactList(value: any[] | undefined, limit = 3) {
  const rows = (value || []).map((item) => String(item)).filter(Boolean)
  if (rows.length === 0) return 'none'
  const visible = rows.slice(0, limit).join('; ')
  return rows.length > limit ? `${visible}; +${rows.length - limit} more` : visible
}

function agentAuditSidecar(item: any) {
  return item?.system_audit_sidecar || item?.structured_sidecar || null
}

function parseKT3DatasetJson() {
  try {
    const parsed = JSON.parse(kt3DatasetJson.value || '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('KT3 Gate Dataset 必须是 JSON object')
    }
    return parsed as Record<string, unknown>
  } catch (error: any) {
    message.error(error?.message || 'KT3 Gate Dataset JSON 格式错误')
    return null
  }
}

function splitCsvLike(value: string) {
  return value
    .split(/[,，\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function fillSuggestedKT3Agents() {
  const suggested = kt3SuggestedAgents.value.map((item: any) => item.agent_name).filter(Boolean)
  kt3SelectedAgents.value = suggested.length ? suggested : kt3AllAgents.value.slice(0, 2)
}

async function handleRunKT3AgentReview() {
  if (!report.value?.report_id) {
    message.warning('请先运行或打开一个已持久化的风险报告')
    return
  }
  if (kt3SelectedAgents.value.length === 0) {
    message.warning('请至少选择一个 KT3 Agent')
    return
  }
  kt3AgentReviewLoading.value = true
  try {
    const res = await runKT3AgentReview({
      report_id: report.value.report_id,
      selected_post_ids: splitCsvLike(kt3SelectedPostIds.value),
      selected_tree_ids: splitCsvLike(kt3SelectedTreeIds.value),
      agent_names: kt3SelectedAgents.value,
      enable_active_retrieval: kt3EnableActiveRetrieval.value,
      enable_light_debate: kt3EnableLightDebate.value,
      enable_full_debate: kt3EnableFullDebate.value,
      debate_max_rounds: kt3DebateMaxRounds.value,
      policy_id: kt3PolicyId.value || undefined,
      active_policy_id: kt3PolicyId.value || undefined,
      retrieval_top_k: kt3RetrievalTopK.value,
    })
    const reviews = res.data?.agent_reviews || []
    report.value.agent_reviews = [...(report.value.agent_reviews || []), ...reviews]
    message.success(`KT3 Agent 研判完成：${res.data?.summary?.completed || 0} 成功，${res.data?.summary?.failed || 0} 失败`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.response?.data?.msg || e.message || 'KT3 Agent 研判失败')
  } finally {
    kt3AgentReviewLoading.value = false
  }
}

async function handleRunKT3AgentReviewAscii() {
  if (!report.value?.report_id) {
    message.warning('Please run or open a persisted risk report first')
    return
  }
  if (kt3SelectedAgents.value.length === 0) {
    message.warning('Select at least one KT3 Agent')
    return
  }
  kt3AgentReviewLoading.value = true
  try {
    const res = await runKT3AgentReview({
      report_id: report.value.report_id,
      selected_post_ids: splitCsvLike(kt3SelectedPostIds.value),
      selected_tree_ids: splitCsvLike(kt3SelectedTreeIds.value),
      agent_names: kt3SelectedAgents.value,
      enable_active_retrieval: kt3EnableActiveRetrieval.value,
      enable_light_debate: kt3EnableLightDebate.value,
      enable_full_debate: kt3EnableFullDebate.value,
      debate_max_rounds: kt3DebateMaxRounds.value,
      policy_id: kt3PolicyId.value || undefined,
      active_policy_id: kt3PolicyId.value || undefined,
      retrieval_top_k: kt3RetrievalTopK.value,
    })
    const reviews = res.data?.agent_reviews || []
    report.value.agent_reviews = [...(report.value.agent_reviews || []), ...reviews]
    message.success(`KT3 Agent review completed: ${res.data?.summary?.completed || 0} completed, ${res.data?.summary?.failed || 0} failed`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.response?.data?.msg || e.message || 'KT3 Agent review failed')
  } finally {
    kt3AgentReviewLoading.value = false
  }
}

void handleRunKT3AgentReview

async function loadKT3Contract() {
  kt3ContractLoading.value = true
  try {
    const res = await getKT3GateDatasetContract()
    kt3Contract.value = res.data
    message.success('KT3 Gate Dataset 契约已加载')
  } catch (e: any) {
    message.error(e.response?.data?.msg || e.message || '加载 KT3 契约失败')
  } finally {
    kt3ContractLoading.value = false
  }
}

function fillKT3DatasetExample() {
  const example = kt3Contract.value?.example_skeleton
  if (!example) {
    message.warning('请先加载 KT3 Gate Dataset 契约')
    return
  }
  kt3DatasetJson.value = JSON.stringify(example, null, 2)
  kt3Validation.value = null
  kt3GateSuiteResponse.value = null
}

async function handleValidateKT3Dataset() {
  const dataset = parseKT3DatasetJson()
  if (!dataset) return
  kt3ValidationLoading.value = true
  try {
    const res = await validateKT3GateDataset(dataset)
    kt3Validation.value = res.data
    message.success(kt3Validation.value.valid ? 'KT3 数据集契约校验通过' : 'KT3 数据集契约仍需修正')
  } catch (e: any) {
    message.error(e.response?.data?.msg || e.message || 'KT3 数据集校验失败')
  } finally {
    kt3ValidationLoading.value = false
  }
}

async function handleRunKT3GateSuite() {
  const dataset = parseKT3DatasetJson()
  if (!dataset) return
  kt3GateSuiteLoading.value = true
  try {
    const res = await assessKT3GateSuite({
      platform: params.value.platform,
      event_id: params.value.event_id,
      time_window: params.value.time_window,
      kt3_gate_dataset: dataset,
    })
    kt3GateSuiteResponse.value = res.data
    message.success('KT3 离线 Gate Suite 已返回，结果未默认持久化')
  } catch (e: any) {
    message.error(e.response?.data?.msg || e.message || 'KT3 Gate Suite 执行失败')
  } finally {
    kt3GateSuiteLoading.value = false
  }
}

async function handleAssess() {
  assessing.value = true
  try {
    const res = await assessRisk(params.value)
    report.value = res.data
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
    const d = res.data
    historyItems.value = d.items || []
    historyTotal.value = d.total || 0
  } catch { /* ignore */ }
}

function handleHistoryChange(pagination: any) {
  historyPage.value = pagination.current
  loadHistory()
}
</script>
