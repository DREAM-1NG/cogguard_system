import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const propagationView = readFileSync(resolve(frontendRoot, 'src/views/propagation/index.vue'), 'utf8')

function bodyOf(source, name) {
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
  let brace = source.indexOf('{', paramsEnd)
  if (source.slice(paramsEnd, brace).includes(': value is') && source.slice(brace, brace + 32).includes('cross_analysis')) {
    let typeDepth = 0
    for (let index = brace; index < source.length; index += 1) {
      const char = source[index]
      if (char === '{') typeDepth += 1
      if (char === '}') typeDepth -= 1
      if (typeDepth === 0) {
        brace = source.indexOf('{', index + 1)
        break
      }
    }
  }
  let depth = 0
  for (let index = brace; index < source.length; index += 1) {
    const char = source[index]
    if (char === '{') depth += 1
    if (char === '}') depth -= 1
    if (depth === 0) return source.slice(start, index + 1)
  }
  throw new Error(`Could not extract ${name}`)
}

function executableFunction(source, name, dependencies = {}) {
  const definition = bodyOf(source, name)
    .replace(/: unknown/g, '')
    .replace(/: string\[\]/g, '')
    .replace(/: EvidencePath/g, '')
    .replace(/: value is \{ cross_analysis: \{ propagation_path_overlays: SemanticPathOverlay\[\] \} \}/g, '')
    .replace(/: SemanticPathOverlay\[\]/g, '')
    .replace(/: Record<string, number>/g, '')
    .replace(/: 'term' \| 'label' \| 'text'/g, '')
    .replace(/: value is UnknownRecord/g, '')
    .replace(/\(item\): item is string =>/g, '(item) =>')
  return Function(...Object.keys(dependencies), `return (${definition})`)(...Object.values(dependencies))
}

function functionOr(source, name, fallback, dependencies = {}) {
  return source.includes(`function ${name}(`) ? executableFunction(source, name, dependencies) : fallback
}

function semanticOverlay(pathId = 'path-1', evidenceRefs = ['post-1']) {
  return {
    path_id: pathId,
    semantic_overlay: {
      sentiment: { positive: 1 },
      keywords: [{ term: 'keyword', count: 1 }],
      topics: [{ label: 'topic', count: 1 }],
      entities: [{ text: 'entity', count: 1 }],
      stance: { support: 1 },
      platforms: ['weibo'],
      time_range: { start: '2026-01-01T00:00:00Z', end: '2026-01-01T01:00:00Z' },
      evidence_refs: evidenceRefs,
    },
  }
}

test('loads the semantic projection for the selected propagation event', () => {
  const loadSemanticProjection = bodyOf(propagationView, 'loadSemanticProjection')

  assert.match(propagationView, /import \{ getEventSemantic, type SemanticEvidenceProjection \} from '@\/api\/analysis'/)
  assert.match(loadSemanticProjection, /const requestedEventId = eventId\.value\.trim\(\)/)
  assert.match(loadSemanticProjection, /await getEventSemantic\(requestedEventId\)/)
  assert.match(loadSemanticProjection, /requestedEventId !== eventId\.value\.trim\(\)/)
})

test('clears semantic projection state when event or platform scope changes', () => {
  const resetSemanticProjection = bodyOf(propagationView, 'resetSemanticProjection')
  const scopeWatchStart = propagationView.indexOf('watch([eventId, platform]')
  const scopeWatch = propagationView.slice(
    scopeWatchStart,
    propagationView.indexOf('watch(displayLayerRows', scopeWatchStart),
  )

  assert.match(resetSemanticProjection, /semanticProjection\.value = null/)
  assert.match(resetSemanticProjection, /semanticLoading\.value = false/)
  assert.match(scopeWatch, /resetSemanticProjection\(\)/)
  assert.match(scopeWatch, /void loadSemanticProjection\(\)/)
})

test('matches numeric path IDs before falling back to exact evidence references', () => {
  const normalizePathId = functionOr(propagationView, 'normalizePathId', (value) => String(value ?? '').trim())
  const sameEvidenceRefs = executableFunction(propagationView, 'sameEvidenceRefs')
  const findPathSemanticOverlay = executableFunction(propagationView, 'findPathSemanticOverlay', {
    normalizePathId,
    sameEvidenceRefs,
  })
  const pathIdMatch = semanticOverlay('42', ['different-ref'])
  const evidenceRefMatch = semanticOverlay('not-the-path', ['post-42'])

  assert.equal(
    findPathSemanticOverlay({ path_id: 42, evidence_refs: ['post-42'] }, [evidenceRefMatch, pathIdMatch]),
    pathIdMatch.semantic_overlay,
  )
  assert.equal(
    findPathSemanticOverlay({ path_id: 84, evidence_refs: ['post-42'] }, [evidenceRefMatch]),
    evidenceRefMatch.semantic_overlay,
  )
})

test('fails closed when any required nested semantic overlay field is empty or malformed', () => {
  const isRecord = executableFunction(propagationView, 'isRecord')
  const hasNonEmptyDistribution = functionOr(propagationView, 'hasNonEmptyDistribution', () => true, { isRecord })
  const hasSemanticFeatureRecords = functionOr(propagationView, 'hasSemanticFeatureRecords', () => true, { isRecord })
  const hasNonEmptyTextList = functionOr(propagationView, 'hasNonEmptyTextList', () => true)
  const normalizePathId = functionOr(propagationView, 'normalizePathId', (value) => String(value ?? '').trim())
  const hasPropagationPathOverlays = executableFunction(propagationView, 'hasPropagationPathOverlays', {
    isRecord,
    hasNonEmptyDistribution,
    hasSemanticFeatureRecords,
    hasNonEmptyTextList,
    normalizePathId,
  })
  const valid = semanticOverlay()

  assert.equal(hasPropagationPathOverlays({ cross_analysis: { propagation_path_overlays: [valid] } }), true)
  for (const mutate of [
    (overlay) => { overlay.semantic_overlay.sentiment = {} },
    (overlay) => { overlay.semantic_overlay.keywords = [{ term: '' }] },
    (overlay) => { overlay.semantic_overlay.topics = [{ label: 1 }] },
    (overlay) => { overlay.semantic_overlay.entities = [] },
    (overlay) => { overlay.semantic_overlay.stance = { support: '1' } },
    (overlay) => { overlay.semantic_overlay.platforms = [] },
    (overlay) => { overlay.semantic_overlay.time_range = { start: '', end: '2026-01-01T01:00:00Z' } },
    (overlay) => { overlay.semantic_overlay.evidence_refs = [''] },
  ]) {
    const malformed = structuredClone(valid)
    mutate(malformed)
    assert.equal(hasPropagationPathOverlays({ cross_analysis: { propagation_path_overlays: [malformed] } }), false)
  }
})

test('keeps malformed, blocked, and empty semantic projections unavailable', () => {
  const semanticPathOverlay = propagationView.slice(
    propagationView.indexOf('const semanticPathOverlay = computed'),
    propagationView.indexOf('function formatTimestamp'),
  )
  const pathDrawer = propagationView.slice(
    propagationView.indexOf('<a-drawer v-model:open="claimPathDetailOpen"'),
    propagationView.indexOf('<a-drawer v-model:open="nodeDetailOpen"'),
  )

  assert.match(semanticPathOverlay, /semanticProjection\.value\?\.status !== 'ready'/)
  assert.match(semanticPathOverlay, /!hasPropagationPathOverlays\(semanticProjection\.value\.evidence\)/)
  assert.match(pathDrawer, /v-if="semanticPathOverlay"/)
  assert.match(pathDrawer, /v-else description="暂无语义叠加"/)
  assert.match(pathDrawer, /语义叠加/)
})

test('renders all required semantic overlay fields without replacing observed path detail', () => {
  const pathDrawer = propagationView.slice(
    propagationView.indexOf('<a-drawer v-model:open="claimPathDetailOpen"'),
    propagationView.indexOf('<a-drawer v-model:open="nodeDetailOpen"'),
  )

  for (const label of ['情绪', '关键词', '主题', '实体', '立场', '平台范围', '时间范围', '证据引用']) {
    assert.match(pathDrawer, new RegExp(`label="${label}"`))
  }
  assert.match(pathDrawer, /selectedClaimPathDetail\.path\.explanation/)
  assert.match(pathDrawer, /selectedClaimPathDetail\.chain\.supporting_posts/)
})
