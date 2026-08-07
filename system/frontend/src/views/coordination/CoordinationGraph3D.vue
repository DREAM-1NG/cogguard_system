<template>
  <div class="graph-shell">
    <a-spin :spinning="loading">
      <div ref="containerRef" class="graph-canvas" :class="{ 'is-empty': !hasGraphData }" />
      <a-empty v-if="!hasGraphData" class="graph-empty" description="暂无可展示的协同网络数据" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import ForceGraph3D from '3d-force-graph'
import SpriteText from 'three-spritetext'
import * as THREE from 'three'

import type { CoordinationGraphLink, CoordinationGraphNode } from '@/api/coordination'

type GraphNode = CoordinationGraphNode & {
  color?: string
  val?: number
  x?: number
  y?: number
  z?: number
}
type GraphLink = CoordinationGraphLink & {
  color?: string
}

const props = defineProps<{
  nodes: CoordinationGraphNode[]
  links: CoordinationGraphLink[]
  showLabels: boolean
  loading: boolean
  active: boolean
}>()

const emit = defineEmits<{
  (event: 'node-click', node: CoordinationGraphNode): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
let graph: any = null
let resizeObserver: ResizeObserver | null = null

const palette = [
  '#2563eb',
  '#0f766e',
  '#f97316',
  '#dc2626',
  '#7c3aed',
  '#0891b2',
  '#db2777',
  '#4b5563',
  '#16a34a',
  '#ca8a04',
]

const hasGraphData = computed(() => props.nodes.length > 0)

function clusterIndex(clusterId: string | number | null | undefined) {
  const numeric = Number(clusterId)
  if (Number.isFinite(numeric)) {
    return Math.abs(Math.trunc(numeric)) % palette.length
  }
  const text = String(clusterId ?? '')
  let hash = 0
  for (const char of text) {
    hash = (hash * 31 + char.charCodeAt(0)) % 9973
  }
  return Math.abs(hash) % palette.length
}

function nodeColor(node: CoordinationGraphNode) {
  return palette[clusterIndex(node.cluster_id)]
}

function nodeSize(node: CoordinationGraphNode) {
  const score = Number(node.node_score ?? 0)
  return 3 + Math.max(0, Math.min(1, score)) * 9
}

function linkOpacity(link: CoordinationGraphLink) {
  const score = Number(link.edge_score ?? link.weight ?? 0)
  return Math.max(0.16, Math.min(0.68, 0.16 + score * 0.42))
}

function buildGraphData() {
  const nodes: GraphNode[] = props.nodes.map((node) => ({
    ...node,
    color: nodeColor(node),
    val: nodeSize(node),
  }))
  const links: GraphLink[] = props.links.map((link) => ({
    ...link,
    color: `rgba(148, 163, 184, ${linkOpacity(link)})`,
  }))
  return { nodes, links }
}

function initGraph() {
  if (!containerRef.value || graph) return
  graph = new ForceGraph3D(containerRef.value) as any
  graph
    .backgroundColor('#f8fafc')
    .showNavInfo(false)
    .nodeRelSize(4)
    .nodeResolution(16)
    .linkDirectionalParticles(1)
    .linkDirectionalParticleWidth(1.3)
    .linkDirectionalParticleSpeed(0.004)
    .linkOpacity(0.36)
    .linkWidth((link: GraphLink) => Math.max(0.5, Math.min(4, Number(link.edge_score ?? link.weight ?? 0) * 2.8)))
    .nodeLabel((node: GraphNode) => {
      const score = Number(node.node_score ?? 0).toFixed(4)
      return `${node.label || node.id}<br/>社区：${node.cluster_id ?? '-'}<br/>节点分数：${score}`
    })
    .nodeColor((node: GraphNode) => node.color || '#2563eb')
    .linkColor((link: GraphLink) => link.color || 'rgba(148, 163, 184, 0.35)')
    .onNodeClick((node: GraphNode) => {
      emit('node-click', node)
      const distance = 95
      const distRatio = 1 + distance / Math.hypot(node.x || 1, node.y || 1, node.z || 1)
      graph?.cameraPosition(
        {
          x: (node.x || 0) * distRatio,
          y: (node.y || 0) * distRatio,
          z: (node.z || 0) * distRatio,
        },
        node,
        900,
      )
    })

  graph.d3Force('charge')?.strength(-70)
  graph.d3Force('link')?.distance(46)
  updateDimensions()
}

function updateDimensions() {
  if (!props.active || !graph || !containerRef.value) return
  const { clientWidth, clientHeight } = containerRef.value
  graph.width(clientWidth || 960)
  graph.height(clientHeight || 620)
}

function syncAnimationState() {
  if (!graph) return
  if (props.active) {
    graph.resumeAnimation?.()
    updateDimensions()
    return
  }
  graph.pauseAnimation?.()
}

function updateGraphData() {
  if (!props.active || !graph) return
  graph.graphData(buildGraphData())
  graph.nodeThreeObject((node: GraphNode) => {
    if (!props.showLabels) {
      const geometry = new THREE.SphereGeometry(nodeSize(node), 16, 16)
      const material = new THREE.MeshLambertMaterial({
        color: node.color || nodeColor(node),
        transparent: true,
        opacity: 0.92,
      })
      return new THREE.Mesh(geometry, material)
    }
    const sprite = new SpriteText(node.label || node.id)
    sprite.color = node.color || nodeColor(node)
    sprite.textHeight = 5
    sprite.backgroundColor = 'rgba(255,255,255,0.72)'
    sprite.padding = 2
    return sprite
  })
}

async function ensureGraph() {
  await nextTick()
  if (!props.active && !graph) return
  initGraph()
  updateGraphData()
  updateDimensions()
  if (containerRef.value && !resizeObserver) {
    resizeObserver = new ResizeObserver(updateDimensions)
    resizeObserver.observe(containerRef.value)
  }
  syncAnimationState()
}

function resetCamera() {
  graph?.cameraPosition({ x: 0, y: 0, z: 420 }, { x: 0, y: 0, z: 0 }, 900)
}

watch(
  () => [props.nodes, props.links],
  () => {
    ensureGraph()
  },
  { deep: true, immediate: true },
)

watch(
  () => props.showLabels,
  () => {
    if (props.active) updateGraphData()
  },
)

watch(
  () => props.active,
  () => {
    if (props.active) {
      void ensureGraph()
      return
    }
    syncAnimationState()
  },
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (graph) {
    graph._destructor?.()
    graph = null
  }
})

defineExpose({ resetCamera })
</script>

<style scoped>
.graph-shell {
  width: 100%;
  position: relative;
}

.graph-canvas {
  width: 100%;
  height: 620px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background:
    radial-gradient(circle at 20% 15%, rgba(14, 165, 233, 0.18), transparent 26%),
    radial-gradient(circle at 80% 25%, rgba(249, 115, 22, 0.14), transparent 24%),
    linear-gradient(180deg, #f8fafc 0%, #eef6ff 100%);
}

.graph-canvas.is-empty {
  opacity: 0;
  pointer-events: none;
}

.graph-empty {
  position: absolute;
  inset: 0;
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed #cbd5e1;
  border-radius: 16px;
  background: #f8fafc;
}

@media (max-width: 960px) {
  .graph-canvas {
    height: 460px;
  }
}
</style>
