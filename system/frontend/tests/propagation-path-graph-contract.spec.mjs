import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const source = readFileSync(new URL('../src/views/propagation/index.vue', import.meta.url), 'utf8')

function functionBody(name) {
  const start = source.indexOf(`function ${name}(`)
  assert.notEqual(start, -1, `Expected ${name} to exist`)
  const paramsStart = source.indexOf('(', start)
  let paramsDepth = 0
  let paramsEnd = -1
  for (let index = paramsStart; index < source.length; index += 1) {
    const char = source[index]
    if (char === '(') paramsDepth += 1
    if (char === ')') paramsDepth -= 1
    if (paramsDepth === 0) {
      paramsEnd = index
      break
    }
  }
  const bodyStart = source.indexOf('{', paramsEnd)
  let depth = 0
  for (let index = bodyStart; index < source.length; index += 1) {
    const char = source[index]
    if (char === '{') depth += 1
    if (char === '}') depth -= 1
    if (depth === 0) return source.slice(start, index + 1)
  }
  throw new Error(`Expected ${name} to close`)
}

test('propagation path graph renders only outward observed display-backbone edges', () => {
  assert.match(source, /const treeEdges = projection\.edges/)
  assert.match(source, /if \(edge\.is_branch_backbone === false\) return false/)
  assert.match(source, /return targetLayer === sourceLayer \+ 1/)
  assert.match(source, /const graphEdges = treeEdges/)
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
  assert.match(source, /独立观测岛/)
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

test('propagation path opens with the backend key-path projection instead of all visible nodes', () => {
  const graphOption = functionBody('buildPathGraphOption')
  const projection = functionBody('buildKeyPropagationGraph')

  assert.match(projection, /summary\?\.key_path_projection/)
  assert.match(projection, /projection\?\.nodes/)
  assert.match(projection, /projection\?\.edges/)
  assert.match(graphOption, /const projection = buildKeyPropagationGraph\(summary\)/)
  assert.doesNotMatch(graphOption, /const nodes = summary\?\.visible_nodes \?\? \[\]/)
})

test('propagation path can expand and collapse only a backend-returned observed branch', () => {
  assert.match(source, /getPropagationBranch/)
  assert.match(source, /expandedBranchProjections/)
  assert.match(source, /async function togglePropagationBranch\(/)
  assert.match(source, /expandedBranchProjections\.value = \{\}/)
  assert.match(source, /togglePropagationBranch\(/)
})

test('layer composition reads the full server population even when no compact path is drawable', () => {
  assert.match(source, /const propagationSummary = computed\(\(\) => analysisResult\.value\?\.diffusion_summary \?\? null\)/)
  assert.match(source, /const layerRows = computed\(\(\) => propagationSummary\.value\?\.layers\?\.length/)
  assert.doesNotMatch(source, /const layerRows = computed\(\(\) => diffusionSummary\.value\?\.layers/)
})
