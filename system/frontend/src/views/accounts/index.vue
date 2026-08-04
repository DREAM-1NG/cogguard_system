<template>
  <div class="account-workbench">
    <a-card size="small" class="panel">
      <template #title>账户画像</template>
      <template #extra>
        <a-button size="small" :loading="loading" @click="loadProfiles">刷新</a-button>
      </template>

      <a-spin :spinning="loading">
        <a-table
          v-if="profiles.length"
          :columns="columns"
          :dataSource="profiles"
          rowKey="account_id"
          :pagination="{ pageSize, showSizeChanger: false }"
          size="middle"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'author_name'">
              <a href="#" @click.prevent="openDetail(record)">{{ displayName(record) }}</a>
            </template>
            <template v-else-if="column.key === 'platform'">
              {{ platformLabel(record.platform) }}
            </template>
            <template v-else-if="column.key === 'assessment'">
              <a-tag :color="assessmentColor(record.assessment?.level)">
                {{ assessmentLabel(record.assessment?.level) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'active_hours'">
              {{ activeHoursLabel(record.active_hours) }}
            </template>
            <template v-else-if="column.key === 'min_interval_seconds'">
              {{ intervalLabel(record.min_interval_seconds) }}
            </template>
          </template>
        </a-table>

        <a-empty v-else-if="!loading" description="暂无账号画像数据" />
      </a-spin>
    </a-card>

    <a-drawer
      v-model:open="detailOpen"
      width="760"
      :destroyOnClose="true"
      :title="detailTitle"
    >
      <a-spin :spinning="detailLoading">
        <template v-if="detail">
          <a-descriptions bordered size="small" :column="2" class="section">
            <a-descriptions-item label="昵称">{{ displayName(detail) }}</a-descriptions-item>
            <a-descriptions-item label="平台">{{ platformLabel(detail.platform) }}</a-descriptions-item>
            <a-descriptions-item label="发言数">{{ detail.post_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item label="活跃时段">{{ activeHoursLabel(detail.active_hours) }}</a-descriptions-item>
            <a-descriptions-item label="最短间隔">{{ intervalLabel(detail.min_interval_seconds) }}</a-descriptions-item>
            <a-descriptions-item label="研判结果">
              <a-tag :color="assessmentColor(detail.assessment?.level)">
                {{ assessmentLabel(detail.assessment?.level) }}
              </a-tag>
            </a-descriptions-item>
          </a-descriptions>

          <a-card size="small" title="近期发言" class="section">
            <a-list :dataSource="detail.recent_posts || []" size="small">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta :title="postTitle(item)" :description="postDesc(item)" />
                </a-list-item>
              </template>
            </a-list>
            <a-empty
              v-if="!(detail.recent_posts || []).length"
              description="暂无近期发言"
              :image-style="{ height: '42px' }"
            />
          </a-card>
        </template>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getAccountDetail, getAccountProfiles } from '@/api/accounts'

type AccountAssessment = {
  level?: 'attention' | 'normal' | 'pending'
  label?: string
}

type AccountProfile = Record<string, any> & {
  assessment?: AccountAssessment
}

const loading = ref(false)
const detailLoading = ref(false)
const profiles = ref<AccountProfile[]>([])
const detail = ref<AccountProfile | null>(null)
const detailOpen = ref(false)
const pageSize = ref(10)

const columns = [
  { title: '昵称', dataIndex: 'author_name', key: 'author_name', width: 200, ellipsis: true },
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 110 },
  { title: '发言数', dataIndex: 'post_count', key: 'post_count', width: 100 },
  { title: '研判结果', dataIndex: 'assessment', key: 'assessment', width: 130 },
  { title: '活跃时段', dataIndex: 'active_hours', key: 'active_hours', width: 130 },
  { title: '最短间隔', dataIndex: 'min_interval_seconds', key: 'min_interval_seconds', width: 130 },
]

const detailTitle = computed(() => `账户画像 · ${detail.value ? displayName(detail.value) : '-'}`)

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

function displayName(record: AccountProfile) {
  return String(record.author_name || '未命名账号')
}

function assessmentLabel(level: AccountAssessment['level']) {
  if (level === 'attention') return '需关注'
  if (level === 'normal') return '未见异常'
  return '暂无研判'
}

function assessmentColor(level: AccountAssessment['level']) {
  if (level === 'attention') return 'gold'
  if (level === 'normal') return 'green'
  return 'default'
}

function platformLabel(value: unknown) {
  const platform = String(value || '').toLowerCase()
  const labels: Record<string, string> = { weibo: '微博', douyin: '抖音', xhs: '小红书' }
  return labels[platform] || '其他平台'
}

function activeHoursLabel(value: unknown) {
  const count = Number(value)
  return Number.isFinite(count) && count > 0 ? `${count} 个时段` : '暂无'
}

function intervalLabel(value: unknown) {
  const seconds = Number(value)
  if (!Number.isFinite(seconds) || seconds <= 0) return '暂无'
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`
  return `${Math.round(seconds / 3600)} 小时`
}

function postTitle(post: Record<string, any>) {
  return String(post.content || '暂无内容')
}

function postDesc(post: Record<string, any>) {
  return `${post.timestamp || '时间未标明'} · 点赞 ${post.likes ?? 0} · 转发 ${post.reposts ?? 0} · 评论 ${post.comments_count ?? 0}`
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
</style>
