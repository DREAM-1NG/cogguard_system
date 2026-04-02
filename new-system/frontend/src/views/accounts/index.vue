<!--
  账户监测页面
-->
<template>
  <div>
    <PageHeader title="账户监测">
      <template #description>
        分析已采集帖子中每个账户的行为特征：发文频率与间隔规律性、作息节律（24h 分布）、互动指标、内容多样性。<br />
        综合计算<strong style="color: #f5222d">自动化倾向评分</strong>（0-100），分数越高越可能是自动化水军。
        进入页面自动加载，也可点击按钮手动刷新。
      </template>
    </PageHeader>

    <!-- 概览统计 -->
    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :span="6"><a-card size="small"><a-statistic title="总账户数" :value="profiles.length" suffix="个" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic title="高危 (≥60分)" :value="profiles.filter((p: any) => p.automation_score >= 60).length" suffix="个" :valueStyle="{ color: '#f5222d' }" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic title="可疑 (30-59分)" :value="profiles.filter((p: any) => p.automation_score >= 30 && p.automation_score < 60).length" suffix="个" :valueStyle="{ color: '#faad14' }" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic title="正常 (<30分)" :value="profiles.filter((p: any) => p.automation_score < 30).length" suffix="个" :valueStyle="{ color: '#52c41a' }" /></a-card></a-col>
    </a-row>

    <!-- 画像列表 -->
    <a-card size="small">
      <template #title>
        账户行为画像
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
            <a-typography-text :type="record.account_id.includes('coord_bot') ? 'danger' : undefined">
              {{ record.account_id }}
            </a-typography-text>
          </template>
        </template>
      </a-table>
      <a-empty v-else description="暂无账户数据，请先执行数据采集" :image-style="{ height: '40px' }" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getAccountProfiles } from '@/api/accounts'
import TableSettings from '@/components/TableSettings.vue'
import PageHeader from '@/components/PageHeader.vue'

const loading = ref(false)
const profiles = ref<any[]>([])
const tableSize = ref<'small' | 'middle' | 'default'>('middle')
const pageSize = ref(10)

const columns = [
  { title: '账户ID', dataIndex: 'account_id', key: 'account_id', width: 160, ellipsis: true },
  { title: '昵称', dataIndex: 'author_name', key: 'author_name', width: 120, ellipsis: true },
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

onMounted(fetchProfiles)
</script>
