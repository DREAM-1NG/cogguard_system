import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const source = readFileSync(new URL('../src/views/propagation/index.vue', import.meta.url), 'utf8')

test('propagation path graph renders one outward evidence backbone edge for each connected observation', () => {
  assert.match(source, /const treeEdges = summary\?\.tree_edges \?\? \[\]/)
  assert.match(source, /function buildPrimaryEvidenceBackbone\(/)
  assert.match(source, /targetDepth !== sourceDepth \+ 1/)
  assert.match(source, /targetDepth === 1 && source !== rootId/)
  assert.match(source, /const connectedNodeIds = new Set<string>\(\[rootId\]\)/)
  assert.match(source, /connectedNodeIds\.has\(String\(candidate\.source\)\)/)
  assert.match(source, /const backbone = buildPrimaryEvidenceBackbone\(nodes, treeEdges, rootId\)/)
  assert.match(source, /const graphEdges = \[\.\.\.backbone\.primaryEdges, \.\.\.backbone\.independentEdges\]/)
  assert.doesNotMatch(source, /const mergedEdges = new Map<string, DiffusionEdge>\(\)/)
  assert.doesNotMatch(source, /links:\s*\[\]/)
})

test('propagation path graph uses deterministic concentric evidence positions instead of backend layout coordinates', () => {
  assert.match(source, /function stableLayoutFraction\(value: string\)/)
  assert.match(source, /connected_depth/)
  assert.match(source, /const childIds = childrenByParent\.get\(parentId\) \?\? \[\]/)
  assert.match(source, /assignAngles\(childId, cursor, cursor \+ childSpan\)/)
  assert.doesNotMatch(source, /node\.layout_x/)
  assert.doesNotMatch(source, /node\.layout_y/)
})

test('propagation path graph marks independent observations outside the primary-source rings', () => {
  assert.match(source, /independent-observation-band/)
  assert.match(source, /independent_status/)
  assert.match(source, /未证实从当前主源头传播/)
})

test('propagation evidence workspace keeps exact layer counts and displays two-decimal proportions', () => {
  assert.match(source, /item\.node_count.*formatRatio\(item\.ratio\)/)
  assert.match(source, /toFixed\(2\)/)
  assert.doesNotMatch(source, /其它层/)
})

test('propagation objects are ranked evidence rows with representative-path availability', () => {
  assert.match(source, /object-evidence-list/)
  assert.match(source, /参与账号/)
  assert.match(source, /首次出现/)
  assert.match(source, /查看路径/)
  assert.match(source, /暂无可定位路径证据/)
})

test('propagation monitoring keeps the alert-disposition tab in the delivered page', () => {
  assert.match(source, /key="alerts" tab="预警处置"/)
  assert.match(source, /loadPropagationAlerts/)
  assert.match(source, /applyPropagationAlertAction/)
})

test('propagation page registers its date picker and result empty state locally', () => {
  assert.match(source, /import\s*{[\s\S]*DatePicker as ADatePicker[\s\S]*Result as AResult[\s\S]*}\s*from 'ant-design-vue'/)
})

test('role contributions expose evidence-backed sources, bridges, and amplifiers without a one-hop spoke graph', () => {
  assert.match(source, /role-contribution-list/)
  assert.match(source, /roleContributions/)
  assert.match(source, /直接带动/)
  assert.match(source, /下游覆盖/)
  assert.match(source, /查看证据/)
  assert.doesNotMatch(source, /roleIgnitionGraphRef/)
  assert.doesNotMatch(source, /function buildRoleIgnitionOption\(\)/)
})

test('changing the propagation scope clears stale graph focus and evidence drawers', () => {
  const resetScope = source.slice(
    source.indexOf('function resetScopeDependentProjections()'),
    source.indexOf('async function loadSemanticProjection()'),
  )

  assert.match(resetScope, /selectedObjectId\.value = ''/)
  assert.match(resetScope, /selectedClaim\.value = null/)
  assert.match(resetScope, /claimDetailOpen\.value = false/)
  assert.match(resetScope, /pathGraphChart\?\.dispose\(\)/)
})
