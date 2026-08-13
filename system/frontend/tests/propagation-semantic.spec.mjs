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
  const brace = source.indexOf('{', paramsEnd)
  let depth = 0
  for (let index = brace; index < source.length; index += 1) {
    const char = source[index]
    if (char === '{') depth += 1
    if (char === '}') depth -= 1
    if (depth === 0) return source.slice(start, index + 1)
  }
  throw new Error(`Could not extract ${name}`)
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

test('matches a path semantic overlay by path id before exact evidence references', () => {
  const findPathSemanticOverlay = bodyOf(propagationView, 'findPathSemanticOverlay')

  assert.match(findPathSemanticOverlay, /path\.path_id/)
  assert.match(findPathSemanticOverlay, /overlay\.path_id === pathId/)
  assert.match(findPathSemanticOverlay, /sameEvidenceRefs\(overlay\.semantic_overlay\.evidence_refs, pathEvidenceRefs\)/)
  assert.ok(
    findPathSemanticOverlay.indexOf('overlay.path_id === pathId')
      < findPathSemanticOverlay.indexOf('sameEvidenceRefs('),
    'path_id matching must be checked before evidence reference matching',
  )
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
