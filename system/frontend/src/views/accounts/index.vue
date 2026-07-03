<!--
  用户画像页面
-->
<template>
  <div>
    <a-card size="small">
      <template #title>
        用户行为画像
        <a-button type="link" size="small" @click="fetchProfiles" :loading="loading" style="margin-left: 8px">刷新</a-button>
      </template>
      <template #extra v-if="profiles.length > 0">
        <TableSettings v-model:size="tableSize" v-model:pageSize="pageSize" />
      </template>
      <a-table v-if="profiles.length > 0"
        :columns="columns" :dataSource="profiles" :loading="loading"
        rowKey="account_id" :pagination="{ pageSize }" :size="tableSize"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'automation_score'">
            <a-progress
              :percent="record.automation_score"
              :strokeColor="record.automation_score >= 60 ? '#f5222d' : record.automation_score >= 30 ? '#faad14' : '#52c41a'"
              :size="[100, 8]" :showInfo="true"
            />
          </template>
          <template v-if="column.key === 'account_id'">
            <a
              :href="profileLink(record)"
              target="_blank"
              rel="noopener noreferrer"
              :class="{ 'danger-link': record.account_id.includes('coord_bot') }"
            >
              {{ record.account_id }}
            </a>
          </template>
          <template v-if="column.key === 'author_name'">
            <a-button type="link" size="small" class="nickname-link" @click="openBehaviorSummary(record)">
              {{ record.author_name || record.account_id }}
            </a-button>
          </template>
        </template>
      </a-table>
      <a-empty v-else description="暂无用户数据，请先执行数据采集" :image-style="{ height: '40px' }" />
    </a-card>

    <a-drawer
      v-model:open="summaryDrawerOpen"
      title="用户行为总结"
      width="560"
      :destroyOnClose="true"
    >
      <template v-if="selectedProfile">
        <a-descriptions size="small" bordered :column="2" style="margin-bottom: 16px">
          <a-descriptions-item label="昵称">
            {{ selectedProfile.author_name || selectedProfile.account_id }}
          </a-descriptions-item>
          <a-descriptions-item label="用户ID">
            <a :href="profileLink(selectedProfile)" target="_blank" rel="noopener noreferrer">
              {{ selectedProfile.account_id }}
            </a>
          </a-descriptions-item>
          <a-descriptions-item label="自动化评分">
            {{ selectedProfile.automation_score }} 分
          </a-descriptions-item>
          <a-descriptions-item label="风险判断">
            <a-tag :color="scoreColor(selectedProfile.automation_score)">
              {{ scoreLabel(selectedProfile.automation_score) }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="帖子数">{{ selectedProfile.post_count }}</a-descriptions-item>
          <a-descriptions-item label="总点赞">{{ selectedProfile.total_likes }}</a-descriptions-item>
        </a-descriptions>

        <a-list size="small" bordered :dataSource="behaviorSummaryItems">
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta :title="item.title" :description="item.description" />
            </a-list-item>
          </template>
        </a-list>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { getAccountProfiles } from '@/api/accounts'
import TableSettings from '@/components/TableSettings.vue'

const loading = ref(false)
const profiles = ref<any[]>([])
const summaryDrawerOpen = ref(false)
const selectedProfile = ref<any | null>(null)
const tableSize = ref<'small' | 'middle' | 'default'>('middle')
const pageSize = ref(10)

const columns = [
  { title: '用户ID', dataIndex: 'account_id', key: 'account_id', width: 160, ellipsis: true },
  { title: '昵称', dataIndex: 'author_name', key: 'author_name', width: 140, ellipsis: true },
  { title: '帖子数', dataIndex: 'post_count', key: 'post_count', width: 80, sorter: (a: any, b: any) => a.post_count - b.post_count },
  { title: '自动化评分', dataIndex: 'automation_score', key: 'automation_score', width: 160, sorter: (a: any, b: any) => a.automation_score - b.automation_score, defaultSortOrder: 'descend' as const },
  { title: '规律性', dataIndex: 'regularity', key: 'regularity', width: 90 },
  { title: '活跃时段', dataIndex: 'active_hours', key: 'active_hours', width: 90 },
  { title: '峰值小时', dataIndex: 'peak_hour', key: 'peak_hour', width: 90 },
  { title: '最短间隔(秒)', dataIndex: 'min_interval_seconds', key: 'min_interval', width: 110 },
  { title: '总点赞', dataIndex: 'total_likes', key: 'total_likes', width: 80 },
]

async function fetchProfiles() {
  loading.value = true
  try { const r = (await getAccountProfiles()) as any; profiles.value = r.data || [] } catch { /* handled */ } finally { loading.value = false }
}

const behaviorSummaryItems = computed(() => {
  if (!selectedProfile.value) return []
  const profile = selectedProfile.value
  return [
    {
      title: '发文节律',
      description: `规律性 ${formatNumber(profile.regularity)}，平均间隔 ${formatSeconds(profile.avg_interval_seconds)}，最短间隔 ${formatSeconds(profile.min_interval_seconds)}。`,
    },
    {
      title: '活跃时段',
      description: `覆盖 ${profile.active_hours ?? 0} 个小时段，峰值发文小时为 ${profile.peak_hour ?? '-'} 点。`,
    },
    {
      title: '互动表现',
      description: `累计点赞 ${profile.total_likes ?? 0}，转发 ${profile.total_reposts ?? 0}，评论 ${profile.total_comments ?? 0}。`,
    },
    {
      title: '内容特征',
      description: `涉及 ${profile.unique_hashtags ?? 0} 个话题标签，${profile.unique_urls ?? 0} 个链接。`,
    },
    {
      title: '检测结论',
      description: behaviorConclusion(profile),
    },
  ]
})

function openBehaviorSummary(record: any) {
  selectedProfile.value = record
  summaryDrawerOpen.value = true
}

function profileLink(record: any) {
  if (record.user_url) return record.user_url
  const accountId = String(record.account_id || '').trim()
  if (!accountId) return ''
  const platform = String(record.platform || '').trim().toLowerCase()
  if (platform === 'xhs' || platform === 'xiaohongshu') {
    return `https://www.xiaohongshu.com/user/profile/${accountId}`
  }
  if (platform === 'douyin') {
    return `https://www.douyin.com/user/${accountId}`
  }
  return `https://weibo.com/u/${accountId}`
}

function scoreLabel(score: number) {
  if (score >= 60) return '高风险'
  if (score >= 30) return '可疑'
  return '正常'
}

function scoreColor(score: number) {
  if (score >= 60) return 'red'
  if (score >= 30) return 'orange'
  return 'green'
}

function behaviorConclusion(profile: any) {
  const score = Number(profile.automation_score || 0)
  const reasons = []
  if (Number(profile.regularity || 0) > 0.8) reasons.push('发文间隔高度规律')
  if (Number(profile.active_hours || 0) <= 2) reasons.push('活跃时段集中')
  if (Number(profile.min_interval_seconds || 0) > 0 && Number(profile.min_interval_seconds || 0) < 60) reasons.push('存在短间隔发文')
  if (Number(profile.post_count || 0) > 10 && Number(profile.avg_interval_seconds || 0) < 600) reasons.push('发文频率偏高')
  const prefix = score >= 60 ? '该用户呈现明显自动化行为特征' : score >= 30 ? '该用户存在一定自动化行为迹象' : '该用户暂未表现出明显自动化行为'
  return reasons.length ? `${prefix}，主要表现为：${reasons.join('、')}。` : `${prefix}。`
}

function formatNumber(value: unknown) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '-'
  return numeric.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
}

function formatSeconds(value: unknown) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric <= 0) return '暂无'
  return `${Math.round(numeric)} 秒`
}

onMounted(fetchProfiles)
</script>

<style scoped>
.nickname-link {
  height: auto;
  padding: 0;
  white-space: normal;
}

.danger-link {
  color: #ff4d4f;
}
</style>
