<template>
  <div ref="cloudRoot" class="keyword-cloud" role="list" aria-label="关键词词云">
    <svg
      class="word-cloud-canvas"
      :height="canvasHeight"
      :viewBox="`0 0 ${canvasWidth} ${canvasHeight}`"
      :width="canvasWidth"
      role="list"
      aria-label="可筛选关键词词云"
    >
      <g
        v-for="(item, index) in placements"
        :key="item.term"
        :aria-label="`${item.term}，出现 ${item.count} 次`"
        :aria-pressed="selectedTerm === item.term"
        :class="[
          'word-cloud-term',
          `rank-${Math.min(4, Math.floor(index / 6))}`,
          { 'is-selected': selectedTerm === item.term },
        ]"
        :transform="`rotate(${item.rotation} ${item.x} ${item.y})`"
        role="button"
        tabindex="0"
        @click="selectTerm(item.term)"
        @keydown.enter="selectTerm(item.term)"
        @keydown.space.prevent="selectTerm(item.term)"
      >
        <text
          :font-size="item.fontSize"
          :x="item.x"
          :y="item.y"
          dominant-baseline="central"
          text-anchor="middle"
        >{{ item.term }}</text>
      </g>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  layoutKeywordCloud,
  type KeywordCloudItem,
} from '@/features/semantic-evidence/model'

const props = defineProps<{
  items: KeywordCloudItem[]
  selectedTerm: string | null
}>()

const emit = defineEmits<{
  select: [term: string | null]
}>()

const cloudRoot = ref<HTMLElement | null>(null)
const canvasWidth = ref(640)
let resizeObserver: ResizeObserver | null = null

const canvasHeight = computed(() => (
  canvasWidth.value <= 440
    ? Math.max(460, Math.round(canvasWidth.value * 1.28))
    : Math.max(520, Math.round(canvasWidth.value * 0.78))
))

const placements = computed(() => layoutKeywordCloud(props.items, canvasWidth.value, canvasHeight.value))

onMounted(() => {
  if (!cloudRoot.value) return
  resizeObserver = new ResizeObserver(([entry]) => {
    const width = Math.floor(entry.contentRect.width)
    if (width > 0) canvasWidth.value = width
  })
  resizeObserver.observe(cloudRoot.value)
})

onBeforeUnmount(() => resizeObserver?.disconnect())

function selectTerm(term: string): void {
  emit('select', props.selectedTerm === term ? null : term)
}
</script>

<style scoped>
.keyword-cloud {
  min-width: 0;
  overflow: hidden;
  width: 100%;
}

.word-cloud-canvas {
  display: block;
  max-width: 100%;
  width: 100%;
}

.word-cloud-term {
  cursor: pointer;
  fill: #315b8f;
  outline: none;
}

.word-cloud-term.rank-0 { fill: #2e6b43; }
.word-cloud-term.rank-1 { fill: #6c8a48; }
.word-cloud-term.rank-2 { fill: #b84d4d; }
.word-cloud-term.rank-3 { fill: #3f6f66; }
.word-cloud-term.rank-4 { fill: #a58c46; }

.word-cloud-term text {
  font-family: inherit;
  paint-order: stroke;
  transition: fill 120ms ease, stroke 120ms ease;
}

.word-cloud-term:hover text,
.word-cloud-term:focus-visible text,
.word-cloud-term.is-selected text {
  fill: #0d3c78;
  stroke: #91caff;
  stroke-width: 1px;
}

@media (prefers-reduced-motion: reduce) {
  .word-cloud-term text {
    transition: none;
  }
}
</style>
