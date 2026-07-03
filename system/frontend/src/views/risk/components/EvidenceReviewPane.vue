<template>
  <a-card class="evidence-pane" size="small" title="证据研判">
    <template v-if="hasEvidence">
      <section class="evidence-column evidence-column-all">
        <div class="section-title">近期推文证据</div>
        <div class="evidence-grid">
          <article
            v-for="post in visibleAllPosts"
            :key="post.post_id || post.excerpt"
            class="summary-card"
            @click="$emit('select-post', post)"
          >
            <div class="summary-meta">
              <span>帖子 {{ post.post_id || '未知' }}</span>
              <span v-if="post.authorName">作者 {{ post.authorName }}</span>
              <span>匹配 {{ percentText(post.claimScore) }}</span>
            </div>
            <p class="summary-text">{{ post.excerpt || '暂无文本' }}</p>
            <div class="evidence-tags">
              <a-tag color="blue">{{ claimDisplayLabel(post.primaryClaimId) }}</a-tag>
              <a-tag :color="post.stanceAbstain ? 'orange' : 'green'">{{ stanceDisplayLabel(post.stanceLabel) }}</a-tag>
              <a-tag :color="post.harmLabel === 'harmful' ? 'red' : 'default'">{{ harmDisplayLabel(post.harmLabel) }}</a-tag>
              <a-button size="small" type="link" class="select-button">选择研判</a-button>
            </div>
          </article>
        </div>
        <div v-if="hasMorePosts" class="more-actions">
          <a-button size="small" @click="visibleLimit += 30">查看更多</a-button>
        </div>
      </section>

      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :lg="12">
          <section class="evidence-column evidence-column-danger">
            <div class="section-title">近期疑似传播内容</div>
            <div v-if="supportPosts.length" class="evidence-list">
              <article
                v-for="post in supportPosts"
                :key="post.post_id"
                class="evidence-item evidence-item-danger"
                @click="$emit('select-post', post)"
              >
                <div class="evidence-dot" />
                <div class="evidence-card">
                  <div class="evidence-meta">
                    <span>帖子 {{ post.post_id || '未知' }}</span>
                    <span>立场 {{ stanceDisplayLabel(post.stanceLabel) }}</span>
                    <span>匹配 {{ percentText(post.claimScore) }}</span>
                  </div>
                  <p class="evidence-text">{{ post.excerpt || '暂无文本' }}</p>
                  <div class="evidence-tags">
                    <a-tag color="red">{{ harmDisplayLabel(post.harmLabel) }}</a-tag>
                    <a-tag color="volcano">{{ harmTypeDisplayLabel(post.primaryType) }}</a-tag>
                    <a-tag v-if="post.stanceAbstain" color="orange">需要核验</a-tag>
                    <a-button size="small" type="link" class="select-button">选择研判</a-button>
                  </div>
                </div>
              </article>
            </div>
            <a-empty v-else description="暂无内容" />
          </section>
        </a-col>

        <a-col :xs="24" :lg="12">
          <section class="evidence-column evidence-column-safe">
            <div class="section-title">近期辟谣或反驳内容</div>
            <div v-if="denyPosts.length" class="evidence-list">
              <article
                v-for="post in denyPosts"
                :key="post.post_id"
                class="evidence-item evidence-item-safe"
                @click="$emit('select-post', post)"
              >
                <div class="evidence-dot" />
                <div class="evidence-card">
                  <div class="evidence-meta">
                    <span>帖子 {{ post.post_id || '未知' }}</span>
                    <span>立场 {{ stanceDisplayLabel(post.stanceLabel) }}</span>
                    <span>匹配 {{ percentText(post.claimScore) }}</span>
                  </div>
                  <p class="evidence-text">{{ post.excerpt || '暂无文本' }}</p>
                  <div class="evidence-tags">
                    <a-tag color="green">{{ harmDisplayLabel(post.harmLabel) }}</a-tag>
                    <a-tag color="blue">{{ claimDisplayLabel(post.primaryClaimId) }}</a-tag>
                    <a-tag v-if="post.stanceAbstain" color="orange">需要核验</a-tag>
                    <a-button size="small" type="link" class="select-button">选择研判</a-button>
                  </div>
                </div>
              </article>
            </div>
            <a-empty v-else description="暂无内容" />
          </section>
        </a-col>
      </a-row>
    </template>
    <a-empty v-else description="暂无数据" />
  </a-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  allPosts: any[]
  supportPosts: any[]
  denyPosts: any[]
}>()

defineEmits<{
  (event: 'select-post', post: any): void
}>()

const visibleLimit = ref(30)
const visibleAllPosts = computed(() => props.allPosts.slice(0, visibleLimit.value))
const hasMorePosts = computed(() => props.allPosts.length > visibleLimit.value)
const hasEvidence = computed(() => props.allPosts.length > 0 || props.supportPosts.length > 0 || props.denyPosts.length > 0)

watch(() => props.allPosts, () => {
  visibleLimit.value = 30
})

const stanceLabels: Record<string, string> = {
  support: '支持传播',
  deny: '反驳',
  query: '求证',
  neutral: '中性',
  uncertain: '需要核验',
  unlinked: '待关联',
}

const harmLabels: Record<string, string> = {
  harmful: '有害',
  non_harmful: '正常',
  uncertain: '需要核验',
}

const harmTypeLabels: Record<string, string> = {
  misinformation: '虚假信息',
  hate: '仇恨攻击',
  harassment: '骚扰',
  incitement: '煽动',
  amplification: '放大传播',
  spam: '垃圾传播',
  none: '暂无类型',
}

function stanceDisplayLabel(value: string | undefined) {
  const key = String(value || '').trim()
  return key ? (stanceLabels[key] || '需要核验') : '待关联'
}

function harmDisplayLabel(value: string | undefined) {
  const key = String(value || '').trim()
  return key ? (harmLabels[key] || '需要核验') : '需要核验'
}

function harmTypeDisplayLabel(value: string | undefined) {
  const key = String(value || '').trim()
  return key ? (harmTypeLabels[key] || '其他类型') : '暂无类型'
}

function claimDisplayLabel(value: string | undefined) {
  const text = String(value || '').trim()
  if (!text) return '待关联'
  return text.replace(/^claim[-_]/i, '线索-')
}

function percentText(value: number | undefined) {
  if (typeof value !== 'number') return '待核验'
  return `${(value * 100).toFixed(1)}%`
}
</script>

<style scoped>
.evidence-pane {
  border-radius: 18px;
}

.evidence-column {
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 18px;
  box-shadow: 0 14px 36px rgb(31 45 61 / 7%);
  min-height: 280px;
  padding: 16px;
}

.evidence-column-all {
  margin-bottom: 16px;
}

.evidence-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}

.summary-card {
  background: linear-gradient(180deg, #fff, #f8fbff);
  border: 1px solid #edf4ff;
  border-radius: 16px;
  cursor: pointer;
  padding: 14px 16px;
  transition: border-color 0.18s, box-shadow 0.18s, transform 0.18s;
}

.summary-card:hover {
  border-color: #91caff;
  box-shadow: 0 10px 28px rgb(24 144 255 / 12%);
  transform: translateY(-1px);
}

.summary-meta {
  color: #8c8c8c;
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 10px;
  margin-bottom: 8px;
}

.summary-text {
  color: #262626;
  display: -webkit-box;
  line-height: 1.7;
  margin: 0 0 10px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
}

.more-actions {
  display: flex;
  justify-content: center;
  margin-top: 14px;
}

.section-title {
  color: #262626;
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 14px;
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-left: 14px;
  position: relative;
}

.evidence-list::before {
  background: #f0f0f0;
  bottom: 8px;
  content: "";
  left: 20px;
  position: absolute;
  top: 8px;
  width: 2px;
}

.evidence-item {
  cursor: pointer;
  display: grid;
  gap: 10px;
  grid-template-columns: 14px 1fr;
  position: relative;
}

.evidence-dot {
  border: 3px solid #fff;
  border-radius: 50%;
  height: 12px;
  margin-top: 20px;
  width: 12px;
  z-index: 1;
}

.evidence-item-danger .evidence-dot {
  background: #ff7875;
  box-shadow: 0 0 0 3px #fff1f0;
}

.evidence-item-safe .evidence-dot {
  background: #52c41a;
  box-shadow: 0 0 0 3px #f6ffed;
}

.evidence-card {
  background: linear-gradient(180deg, #fff, #fffaf8);
  border: 1px solid #f5f5f5;
  border-radius: 14px;
  padding: 12px 14px;
  transition: border-color 0.18s, box-shadow 0.18s, transform 0.18s;
}

.evidence-item:hover .evidence-card {
  border-color: #91caff;
  box-shadow: 0 10px 28px rgb(24 144 255 / 12%);
  transform: translateY(-1px);
}

.evidence-meta {
  color: #8c8c8c;
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 10px;
  margin-bottom: 8px;
}

.evidence-text {
  color: #262626;
  line-height: 1.7;
  margin: 0 0 10px;
}

.evidence-tags {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.select-button {
  margin-left: auto;
  padding: 0;
}
</style>
