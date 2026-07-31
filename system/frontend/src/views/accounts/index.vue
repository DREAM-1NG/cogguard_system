<template>
  <div class="account-workbench">
    <a-card size="small" class="panel">
      <template #title>
        账号检测
        <a-button type="link" size="small" :loading="loading" @click="loadProfiles">刷新</a-button>
      </template>

      <a-table
        v-if="profiles.length"
        :columns="columns"
        :dataSource="profiles"
        :loading="loading"
        rowKey="account_id"
        :pagination="{ pageSize }"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'account_id'">
            <a @click.prevent="openDetail(record)" href="#">{{ record.account_id }}</a>
          </template>
          <template v-if="column.key === 'automation_score'">
            <a-tag :color="scoreColor(record.automation_score)">{{ scoreLabel(record.automation_score) }}</a-tag>
          </template>
        </template>
      </a-table>

      <a-empty v-else description="暂无账号画像数据" />
    </a-card>

    <a-drawer
      v-model:open="detailOpen"
      width="980"
      :destroyOnClose="true"
      :title="detailTitle"
    >
      <a-spin :spinning="detailLoading">
        <template v-if="detail">
          <a-descriptions bordered size="small" :column="2" class="section">
            <a-descriptions-item label="账号ID">{{ detail.account_id }}</a-descriptions-item>
            <a-descriptions-item label="昵称">{{ detail.author_name || detail.account_id }}</a-descriptions-item>
            <a-descriptions-item label="平台">{{ detail.platform || '-' }}</a-descriptions-item>
            <a-descriptions-item label="发言数">{{ detail.post_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item label="自动化评分">
              <a-tag :color="scoreColor(detail.automation_score)">{{ detail.automation_score ?? 0 }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="判别状态">
              <a-tag :color="detectionTagColor">{{ detectionLabel }}</a-tag>
            </a-descriptions-item>
          </a-descriptions>

          <a-row :gutter="16" class="section">
            <a-col :span="12">
              <a-card size="small" title="判别结果" class="subpanel">
                <a-descriptions bordered size="small" :column="1">
                  <a-descriptions-item label="方法">{{ detectionMethod }}</a-descriptions-item>
                  <a-descriptions-item label="运行模式">{{ detectionMode }}</a-descriptions-item>
                  <a-descriptions-item label="最终概率">{{ formatPercent(detectorAccount.final_bot_probability) }}</a-descriptions-item>
                  <a-descriptions-item label="基线概率">{{ formatPercent(detectorAccount.base_bot_probability) }}</a-descriptions-item>
                  <a-descriptions-item label="局部可靠性">{{ formatPercent(detectorAccount.local_reliability) }}</a-descriptions-item>
                </a-descriptions>
                <a-divider />
                <div class="method-note">{{ methodNote }}</div>
              </a-card>
            </a-col>
            <a-col :span="12">
              <a-card size="small" title="相近用户" class="subpanel">
                <a-list :dataSource="similarUsers" size="small">
                  <template #renderItem="{ item }">
                    <a-list-item>
                      <a-list-item-meta :title="item.author_name || item.account_id" :description="similarUserDesc(item)" />
                    </a-list-item>
                  </template>
                </a-list>
              </a-card>
            </a-col>
          </a-row>

          <a-card size="small" title="账号发言" class="section">
            <a-list :dataSource="detail.recent_posts || []" size="small">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta :title="postTitle(item)" :description="postDesc(item)" />
                </a-list-item>
              </template>
            </a-list>
          </a-card>
        </template>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getAccountDetail, getAccountProfiles } from '@/api/accounts'

type AccountProfile = Record<string, any>

const loading = ref(false)
const detailLoading = ref(false)
const profiles = ref<AccountProfile[]>([])
const detail = ref<AccountProfile | null>(null)
const detailOpen = ref(false)
const pageSize = ref(10)

const columns = [
  { title: '账号ID', dataIndex: 'account_id', key: 'account_id', width: 180, ellipsis: true },
  { title: '昵称', dataIndex: 'author_name', key: 'author_name', width: 160, ellipsis: true },
  { title: '发言数', dataIndex: 'post_count', key: 'post_count', width: 90 },
  { title: '自动化评分', dataIndex: 'automation_score', key: 'automation_score', width: 120 },
  { title: '活跃时段', dataIndex: 'active_hours', key: 'active_hours', width: 100 },
  { title: '最短间隔', dataIndex: 'min_interval_seconds', key: 'min_interval_seconds', width: 100 },
]

const detectorAccount = computed(() => detail.value?.detection_result?.account || {})
const similarUsers = computed(() => detail.value?.similar_users || detail.value?.detection_result?.similar_users || [])
const detectionMethod = computed(() => detail.value?.detection_result?.method || detail.value?.detection?.method || 'BotRHG proxy')
const detectionMode = computed(() => detail.value?.detection_result?.method_card?.runtime_mode || 'proxy')
const methodNote = computed(() => detail.value?.detection_result?.method_card?.note || '暂无方法说明')
const detectionLabel = computed(() => {
  const label = detectorAccount.value?.final_prediction || 'human'
  return label === 'bot' ? '高风险' : '正常'
})
const detectionTagColor = computed(() => (detectorAccount.value?.final_prediction === 'bot' ? 'red' : 'green'))
const detailTitle = computed(() => `账号详情 · ${detail.value?.author_name || detail.value?.account_id || '-'}`)

async function loadProfiles() {
  loading.value = true
  try {
    const response = await getAccountProfiles()
    profiles.value = response?.data || []
  } finally {
    loading.value = false
  }
}

async function openDetail(record: AccountProfile) {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = record
  try {
    const response = await getAccountDetail(String(record.account_id))
    detail.value = response?.data || record
  } finally {
    detailLoading.value = false
  }
}

function scoreLabel(score: number) {
  if (Number(score) >= 60) return '高风险'
  if (Number(score) >= 30) return '可疑'
  return '正常'
}

function scoreColor(score: number) {
  if (Number(score) >= 60) return 'red'
  if (Number(score) >= 30) return 'orange'
  return 'green'
}

function formatPercent(value: unknown) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '-'
  return `${(number * 100).toFixed(1)}%`
}

function postTitle(post: Record<string, any>) {
  return `${post.timestamp || '-'} · ${post.content || '(empty)'}`
}

function postDesc(post: Record<string, any>) {
  return `点赞 ${post.likes ?? 0} · 转发 ${post.reposts ?? 0} · 评论 ${post.comments_count ?? 0}`
}

function similarUserDesc(user: Record<string, any>) {
  return `相似度 ${formatPercent(user.similarity)} · 判别 ${user.final_prediction || '-'} · 概率 ${formatPercent(user.final_bot_probability)}`
}

onMounted(loadProfiles)
</script>

<style scoped>
.account-workbench {
  display: grid;
  gap: 16px;
}

.section {
  margin-bottom: 16px;
}

.subpanel {
  min-height: 100%;
}

.method-note {
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.6;
}
</style>
