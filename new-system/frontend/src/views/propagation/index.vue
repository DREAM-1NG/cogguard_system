<!--
  传播归因页面
-->
<template>
  <div>
    <PageHeader title="传播归因">
      <template #description>
        基于共享对象（URL/标签）的时序关系构建传播子图，识别信息传播链中的关键角色：<br />
        <strong>起爆节点</strong>（最早发布者）、<strong>桥接节点</strong>（连接不同群体，介数中心性高）、
        <strong>扩散节点</strong>（被大量跟随传播）。需先在「数据采集」中创建任务。
      </template>
    </PageHeader>

    <!-- 操作栏 -->
    <div style="margin-bottom: 16px">
      <a-button type="primary" @click="handleAnalyze" :loading="analyzing">运行传播分析</a-button>
    </div>

    <!-- 关键角色 -->
    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :span="8">
        <a-card size="small" title="起爆节点">
          <a-list v-if="keyRoles?.originators?.length" :dataSource="keyRoles.originators" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <span>{{ item.author_name }}</span>
                <template #actions><a-tag color="red">出度 {{ item.out_degree }}</a-tag></template>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else description="运行分析后展示" :image-style="{ height: '30px' }" />
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card size="small" title="桥接节点">
          <a-list v-if="keyRoles?.bridges?.length" :dataSource="keyRoles.bridges" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <span>{{ item.author_name }}</span>
                <template #actions><a-tag color="orange">介数 {{ item.betweenness }}</a-tag></template>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else description="运行分析后展示" :image-style="{ height: '30px' }" />
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card size="small" title="扩散节点">
          <a-list v-if="keyRoles?.amplifiers?.length" :dataSource="keyRoles.amplifiers" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <span>{{ item.author_name }}</span>
                <template #actions><a-tag color="blue">入度 {{ item.in_degree }}</a-tag></template>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else description="运行分析后展示" :image-style="{ height: '30px' }" />
        </a-card>
      </a-col>
    </a-row>

    <!-- 高频 Claim -->
    <a-card size="small" style="margin-bottom: 16px">
      <template #title>高频共享对象</template>
      <template #extra v-if="claims.length > 0">
        <TableSettings v-model:size="tableSize" v-model:pageSize="pageSize" />
      </template>
      <a-table v-if="claims.length > 0"
        :columns="claimColumns" :dataSource="claims" rowKey="object_id"
        :size="tableSize" :pagination="{ pageSize }"
      />
      <a-empty v-else description="运行分析后展示" :image-style="{ height: '40px' }" />
    </a-card>

    <!-- 时间线 -->
    <a-card size="small" title="传播时间线">
      <div v-if="timeline.length > 0" style="max-height: 500px; overflow-y: auto">
        <a-timeline mode="left">
          <a-timeline-item v-for="(item, i) in timeline.slice(0, 30)" :key="i" :color="item.author_id.includes('coord') ? 'red' : 'blue'">
            <p style="margin-bottom: 2px"><strong>{{ item.author_name }}</strong> <span style="color: #999; font-size: 12px">{{ item.timestamp }}</span></p>
            <p style="color: #666; margin: 0">{{ item.content }}</p>
          </a-timeline-item>
        </a-timeline>
      </div>
      <a-empty v-else description="运行分析后展示" :image-style="{ height: '40px' }" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { analyzePropagation } from '@/api/propagation'
import TableSettings from '@/components/TableSettings.vue'
import PageHeader from '@/components/PageHeader.vue'

const analyzing = ref(false)
const tableSize = ref<'small' | 'middle' | 'default'>('middle')
const pageSize = ref(10)
const keyRoles = ref<any>(null)
const claims = ref<any[]>([])
const timeline = ref<any[]>([])

const claimColumns = [
  { title: '共享对象', dataIndex: 'object_id', key: 'object_id', ellipsis: true },
  { title: '分享次数', dataIndex: 'share_count', key: 'share_count', sorter: (a: any, b: any) => a.share_count - b.share_count },
  { title: '涉及账户', dataIndex: 'account_count', key: 'account_count' },
  { title: '首次分享', dataIndex: 'first_share', key: 'first_share' },
]

async function handleAnalyze() {
  analyzing.value = true
  try {
    const res = (await analyzePropagation()) as { data: any }
    if (res.data.error) { message.warning(res.data.error); return }
    keyRoles.value = res.data.key_roles
    claims.value = res.data.claims || []
    timeline.value = res.data.timeline || []
    message.success('传播归因分析完成')
  } catch { /* handled */ } finally { analyzing.value = false }
}
</script>
