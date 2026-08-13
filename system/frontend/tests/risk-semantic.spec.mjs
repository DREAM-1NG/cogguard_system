import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

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

function semanticEvidenceValidator() {
  const validator = bodyOf(riskView, 'hasSemanticEvidenceStructure')
  const objectHelper = bodyOf(riskView, 'objectValue')
  const compiled = ts.transpileModule(
    `${objectHelper}\n${validator}\nmodule.exports = hasSemanticEvidenceStructure`,
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
      },
    },
  ).outputText
  const module = { exports: undefined }
  new Function('module', compiled)(module)
  return module.exports
}

function validSemanticEvidence() {
  const item = {
    id: 'post-1',
    platform: 'weibo',
    timestamp: '2026-08-14T08:00:00Z',
    sentiment: { label: 'positive' },
    stance: { status: 'ready', label: 'entailment' },
    keywords: [{ term: 'trade' }],
    topics: [{ id: 'topic-1', label: 'policy' }],
    entities: [{ text: 'Beijing', label: 'LOC' }],
    near_duplicates: [{ id: 'post-0', similarity: 0.93 }],
  }

  return {
    layers: {
      posts: [item],
      comments: [{
        ...item,
        id: 'comment-1',
        stance: { status: 'blocked_missing_primary_claim', label: null },
      }],
    },
    cross_analysis: {
      time_slices: [{ date: '2026-08-14', count: 2 }],
      platform_slices: [{ platform: 'weibo', count: 2, sentiment: { positive: 2 } }],
      community_slices: [{
        community_id: 'community-1',
        members: ['account-1', 'account-2'],
        member_count: 2,
        item_count: 2,
        sentiment_distribution: { positive: 2 },
        stance_distribution: { entailment: 1, unknown: 1 },
        top_keywords: [{ term: 'trade', count: 2 }],
        top_topics: [{ label: 'policy', count: 2 }],
        top_entities: [{ text: 'Beijing', count: 2 }],
      }],
      propagation_path_overlays: [{
        path_id: 'path-1',
        semantic_overlay: {
          sentiment: { positive: 2 },
          keywords: [{ term: 'trade' }],
          topics: [{ label: 'policy' }],
          entities: [{ text: 'Beijing' }],
          stance: { entailment: 1, unknown: 1 },
          platforms: ['weibo'],
          time_range: {
            start: '2026-08-14T08:00:00Z',
            end: '2026-08-14T08:01:00Z',
          },
          associated_claim: 'A primary claim',
          evidence_refs: ['weibo:post:post-1', 'weibo:comment:comment-1'],
        },
      }],
    },
  }
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

test('does not let a stale event-linked initial load start a case load', () => {
  const loadInitialCase = bodyOf(riskView, 'loadInitialCase')
  const eventLinkedBranch = between(
    loadInitialCase,
    'if (linkedEventId) {',
    '  loading.value = true',
  )

  const sequenceGuard = eventLinkedBranch.indexOf('requestSequence !== caseLoadSequence')
  const caseItemsRead = eventLinkedBranch.indexOf('const matched = eventSearch.items.find')
  const caseLoad = eventLinkedBranch.indexOf('await loadCase(matched.case_id)')

  assert.notEqual(sequenceGuard, -1)
  assert.notEqual(caseItemsRead, -1)
  assert.notEqual(caseLoad, -1)
  assert.ok(sequenceGuard < caseItemsRead, 'the stale guard must run before reading the event search response')
  assert.ok(sequenceGuard < caseLoad, 'the stale guard must run before loading the matched case')
})

test('resolves an event-linked initial case from its own current search response', () => {
  const loadCaseOptions = bodyOf(riskView, 'loadCaseOptions')
  const loadInitialCase = bodyOf(riskView, 'loadInitialCase')
  const eventLinkedBranch = between(
    loadInitialCase,
    'if (linkedEventId) {',
    '  loading.value = true',
  )

  assert.match(loadCaseOptions, /if \(requestSequence !== caseSearchSequence\) return null/)
  assert.match(loadCaseOptions, /return \{\s*requestSequence,\s*items: res\.data\.items\s*\}/)
  assert.match(eventLinkedBranch, /const eventSearch = await loadCaseOptions\(linkedEventId\)/)
  assert.match(eventLinkedBranch, /eventSearch\.requestSequence !== caseSearchSequence/)
  assert.match(eventLinkedBranch, /const matched = eventSearch\.items\.find/)
  assert.doesNotMatch(eventLinkedBranch, /caseItems\.value/)

  const searchGuard = eventLinkedBranch.indexOf('eventSearch.requestSequence !== caseSearchSequence')
  const matchRead = eventLinkedBranch.indexOf('const matched = eventSearch.items.find')
  const caseLoad = eventLinkedBranch.indexOf('await loadCase(matched.case_id)')
  const warning = eventLinkedBranch.indexOf('message.warning')

  assert.ok(searchGuard < matchRead, 'the search guard must run before selecting an event case')
  assert.ok(searchGuard < caseLoad, 'the search guard must run before loading an event case')
  assert.ok(searchGuard < warning, 'the search guard must run before warning about a missing event case')
})

test('does not let a stale unauthorized activity recovery stop the current case recovery', () => {
  const recoverCaseActivities = bodyOf(riskView, 'recoverCaseActivities')
  const unauthorizedBranch = between(
    recoverCaseActivities,
    'if (isUnauthorizedCaseEventStreamError(error)) {',
    '    if ((error as { name?: string }).name !== \'AbortError\')',
  )

  assert.match(
    unauthorizedBranch,
    /if \(requestSequence === caseLoadSequence && currentCase\.value\?\.case_id === caseId\) \{\s*stopActivityRecovery\(\)\s*\}/,
  )
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

test('requires complete semantic evidence containers before the panel is ready', () => {
  const semanticEvidence = between(riskView, 'const semanticEvidence = computed', 'const semanticReady = computed')
  const hasSemanticEvidenceStructure = bodyOf(riskView, 'hasSemanticEvidenceStructure')

  assert.match(semanticEvidence, /!hasSemanticEvidenceStructure\(projection\.evidence\)/)
  assert.match(hasSemanticEvidenceStructure, /hasRecords\(layers\.posts, hasSemanticItem\)/)
  assert.match(hasSemanticEvidenceStructure, /hasRecords\(layers\.comments, hasSemanticItem\)/)
  assert.match(hasSemanticEvidenceStructure, /hasRecords\(timeSlices, hasTimeSlice\)/)
  assert.match(hasSemanticEvidenceStructure, /timeSlices\.length > 0/)
  assert.match(hasSemanticEvidenceStructure, /hasRecords\(platformSlices, hasPlatformSlice\)/)
  assert.match(hasSemanticEvidenceStructure, /platformSlices\.length > 0/)
  assert.match(hasSemanticEvidenceStructure, /hasRecords\(crossAnalysis\.community_slices, hasCommunitySlice\)/)
  assert.match(hasSemanticEvidenceStructure, /hasRecords\(crossAnalysis\.propagation_path_overlays, hasPathOverlay\)/)
})

test('accepts only runtime-shaped nested semantic evidence artifacts', () => {
  const validate = semanticEvidenceValidator()
  const valid = validSemanticEvidence()

  assert.equal(validate(valid), true)

  const malformedItems = structuredClone(valid)
  delete malformedItems.layers.posts[0].sentiment.label
  assert.equal(validate(malformedItems), false)

  const malformedFeatures = structuredClone(valid)
  malformedFeatures.layers.comments[0].near_duplicates = [{ similarity: 0.93 }]
  assert.equal(validate(malformedFeatures), false)

  const malformedSlices = structuredClone(valid)
  delete malformedSlices.cross_analysis.time_slices[0].date
  assert.equal(validate(malformedSlices), false)

  const malformedCommunities = structuredClone(valid)
  malformedCommunities.cross_analysis.community_slices[0].community_id = ''
  assert.equal(validate(malformedCommunities), false)

  const malformedOverlays = structuredClone(valid)
  delete malformedOverlays.cross_analysis.propagation_path_overlays[0].semantic_overlay
  assert.equal(validate(malformedOverlays), false)

  const emptyEvidence = structuredClone(valid)
  emptyEvidence.layers.posts = []
  emptyEvidence.layers.comments = []
  emptyEvidence.cross_analysis.time_slices = []
  emptyEvidence.cross_analysis.platform_slices = []
  emptyEvidence.cross_analysis.community_slices = []
  emptyEvidence.cross_analysis.propagation_path_overlays = []
  assert.equal(validate(emptyEvidence), false)

  const unavailableCrossAnalysis = structuredClone(valid)
  unavailableCrossAnalysis.cross_analysis.time_slices = []
  unavailableCrossAnalysis.cross_analysis.platform_slices = []
  unavailableCrossAnalysis.cross_analysis.community_slices = []
  unavailableCrossAnalysis.cross_analysis.propagation_path_overlays = []
  assert.equal(validate(unavailableCrossAnalysis), false)
})

test('requires time and platform slices when semantic layers contain items', () => {
  const validate = semanticEvidenceValidator()
  const populatedLayersWithoutRequiredSlices = validSemanticEvidence()

  populatedLayersWithoutRequiredSlices.cross_analysis.time_slices = []
  populatedLayersWithoutRequiredSlices.cross_analysis.platform_slices = []

  assert.equal(validate(populatedLayersWithoutRequiredSlices), false)
})

test('requires blocked missing-primary-claim stances to have a null label', () => {
  const validate = semanticEvidenceValidator()
  const blockedItemWithLabel = validSemanticEvidence()

  blockedItemWithLabel.layers.comments[0].stance.label = 'neutral'

  assert.equal(validate(blockedItemWithLabel), false)
})
