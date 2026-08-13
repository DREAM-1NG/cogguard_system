import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const riskView = readFileSync(resolve(frontendRoot, 'src/views/risk/index.vue'), 'utf8')

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

function between(source, startMarker, endMarker) {
  const start = source.indexOf(startMarker)
  assert.notEqual(start, -1, `Expected ${startMarker} to exist`)
  const end = source.indexOf(endMarker, start)
  assert.notEqual(end, -1, `Expected ${endMarker} to exist after ${startMarker}`)
  return source.slice(start, end)
}

test('loads the semantic projection with the current Event Review Case event id', () => {
  const applyCase = bodyOf(riskView, 'applyCase')
  const loadSemanticProjection = bodyOf(riskView, 'loadSemanticProjection')

  assert.match(riskView, /import \{ getEventSemantic \} from '@\/api\/analysis'/)
  assert.match(applyCase, /currentCase\.value = detail/)
  assert.match(applyCase, /void loadSemanticProjection\(\)/)
  assert.match(loadSemanticProjection, /const eventId = currentCase\.value\?\.event_id/)
  assert.match(loadSemanticProjection, /await getEventSemantic\(eventId\)/)
})

test('ignores stale semantic responses while a case is refreshed', () => {
  const loadSemanticProjection = bodyOf(riskView, 'loadSemanticProjection')

  assert.match(riskView, /let semanticRequestSequence = 0/)
  assert.match(loadSemanticProjection, /const requestSequence = \+\+semanticRequestSequence/)
  assert.match(loadSemanticProjection, /semanticLoading\.value = Boolean\(eventId\)/)
  assert.match(loadSemanticProjection, /requestSequence === semanticRequestSequence/)
})

test('does not let an older case load apply detail, evidence, activity, routing, or semantic state', () => {
  const loadCase = bodyOf(riskView, 'loadCase')
  const applyCase = bodyOf(riskView, 'applyCase')
  const loadSemanticProjection = bodyOf(riskView, 'loadSemanticProjection')
  const loadActivities = bodyOf(riskView, 'loadActivities')
  const recoverCaseActivities = bodyOf(riskView, 'recoverCaseActivities')
  const invalidatePendingCaseLoadState = bodyOf(riskView, 'invalidatePendingCaseLoadState')

  assert.match(riskView, /let caseLoadSequence = 0/)
  assert.match(loadCase, /const requestSequence = \+\+caseLoadSequence/)
  assert.match(loadCase, /if \(requestSequence !== caseLoadSequence\) return/)
  assert.match(loadCase, /applyCase\(detailRes\.data, evidenceRes\.data, activityRes\.data, requestSequence\)/)
  assert.match(applyCase, /if \(requestSequence !== caseLoadSequence\) return/)
  assert.match(applyCase, /void loadSemanticProjection\(\)/)
  assert.match(applyCase, /loadActivities\(detail\.case_id\)/)
  assert.match(applyCase, /startActivityRecovery\(detail\.case_id\)/)
  assert.match(loadSemanticProjection, /caseRequestSequence === caseLoadSequence/)
  assert.match(loadActivities, /requestSequence === caseLoadSequence/)
  assert.match(recoverCaseActivities, /requestSequence === caseLoadSequence/)
  assert.match(invalidatePendingCaseLoadState, /semanticRequestSequence \+= 1/)
  assert.match(invalidatePendingCaseLoadState, /activityLoading\.value = false/)
  assert.match(invalidatePendingCaseLoadState, /loadingEvidenceGroup\.value = null/)
})

test('renders ready semantic evidence from its layers and cross-analysis slices', () => {
  const semanticPanel = between(riskView, '<section class="semantic-panel"', '<section class="workspace-grid"')

  assert.match(semanticPanel, /v-else-if="semanticReady"/)
  assert.match(semanticPanel, /topSemanticKeywords/)
  assert.match(semanticPanel, /topSemanticTopics/)
  assert.match(semanticPanel, /semanticSentiment/)
  assert.match(semanticPanel, /semanticStance/)
  assert.match(semanticPanel, /topSemanticEntities/)
  assert.match(semanticPanel, /semanticTimeSlices/)
  assert.match(semanticPanel, /semanticPlatformSlices/)
  assert.match(semanticPanel, /semanticCommunities/)
  assert.match(semanticPanel, /semanticMatrixRows/)
  assert.match(semanticPanel, /帖子与评论语义矩阵/)
  assert.match(riskView, /semanticLayerItems\('posts'\)/)
  assert.match(riskView, /semanticLayerItems\('comments'\)/)
  assert.match(riskView, /semanticCrossAnalysis\.value\.time_slices/)
  assert.match(riskView, /semanticCrossAnalysis\.value\.platform_slices/)
  assert.match(riskView, /semanticCrossAnalysis\.value\.community_slices/)
})

test('fails closed when semantic evidence is missing or blocked', () => {
  const semanticEvidence = between(riskView, 'const semanticEvidence = computed', 'const semanticReady = computed')
  const semanticPanel = between(riskView, '<section class="semantic-panel"', '<section class="workspace-grid"')

  assert.match(semanticEvidence, /projection\.status !== 'ready'/)
  assert.match(semanticEvidence, /!projection\.evidence/)
  assert.match(semanticPanel, /v-if="semanticUnavailable"/)
  assert.match(semanticPanel, /语义证据暂不可用/)
  assert.match(semanticPanel, /semanticUnavailableText/)
  assert.doesNotMatch(semanticPanel, /currentCase|coordination_summary|preliminary_finding|review_advisory/)
})
