import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const propagationView = readFileSync(resolve(frontendRoot, 'src/views/propagation/index.vue'), 'utf8')
const propagationApi = readFileSync(resolve(frontendRoot, 'src/api/propagation.ts'), 'utf8')

async function loadClaimResponsePresentation() {
  const helperSource = readFileSync(resolve(frontendRoot, 'src/views/propagation/claimResponsePresentation.ts'), 'utf8')
  const { outputText } = ts.transpileModule(helperSource, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2020,
    },
  })
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
}

const claimResponsePresentation = await loadClaimResponsePresentation()

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
    .replace(/: EvidencePath \| null \| undefined/g, '')
    .replace(/: EvidencePath/g, '')
    .replace(/: SemanticEvidenceProjection \| null/g, '')
    .replace(/: PropagationAnalysisArtifact \| null/g, '')
    .replace(/: SemanticOverlayPayload \| ClaimResponseSemanticOverlay \| null/g, '')
    .replace(/: SemanticEvidenceProjection/g, '')
    .replace(/: SemanticOverlayPayload/g, '')
    .replace(/: SemanticPathOverlay\['semantic_overlay'\]/g, '')
    .replace(/: value is \{ cross_analysis: \{ propagation_path_overlays: SemanticPathOverlay\[\] \} \}/g, '')
    .replace(/: value is SemanticPathOverlay\['semantic_overlay'\]/g, '')
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

function semanticOverlay(pathId = 'path-1', evidenceRefs = ['weibo:post:post-1']) {
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

  assert.match(propagationView, /import \{ getAnalysisArtifact, getEventSemantic, type SemanticEvidenceProjection \} from '@\/api\/analysis'/)
  assert.match(propagationView, /const PROPAGATION_ANALYSIS_ARTIFACT_KEY = 'stage:propagation_analysis:result'/)
  assert.match(loadSemanticProjection, /const requestedEventId = eventId\.value\.trim\(\)/)
  assert.match(loadSemanticProjection, /await getEventSemantic\(requestedEventId\)/)
  assert.match(loadSemanticProjection, /response\.data\.status === 'ready'/)
  assert.match(loadSemanticProjection, /response\.data\.run_id/)
  assert.match(loadSemanticProjection, /response\.data\.snapshot_id/)
  assert.match(loadSemanticProjection, /await getAnalysisArtifact\(response\.data\.run_id, PROPAGATION_ANALYSIS_ARTIFACT_KEY\)/)
  assert.match(loadSemanticProjection, /isVerifiedLinkedPropagationArtifact\(response\.data, artifactResponse\.data\)/)
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
  assert.match(resetSemanticProjection, /linkedPropagationArtifact\.value = null/)
  assert.match(resetSemanticProjection, /semanticLoading\.value = false/)
  assert.match(scopeWatch, /resetSemanticProjection\(\)/)
  assert.match(scopeWatch, /void loadSemanticProjection\(\)/)
})

test('verifies linked propagation artifacts before semantic drill-down can use them', () => {
  const gate = bodyOf(propagationView, 'isVerifiedLinkedPropagationArtifact')

  assert.match(gate, /semantic\.status !== 'ready'/)
  assert.match(gate, /!semantic\.run_id/)
  assert.match(gate, /!semantic\.snapshot_id/)
  assert.match(gate, /artifactSnapshotId\(artifact\) !== semantic\.snapshot_id/)
  assert.match(gate, /artifactStatus !== 'ok' && artifactStatus !== 'completed'/)
  assert.match(gate, /artifact\.fallback === true/)
  assert.match(gate, /semanticFingerprint && artifactFingerprint && semanticFingerprint !== artifactFingerprint/)
  assert.match(gate, /hasLinkedEvidenceChains\(artifact\)/)
})

test('matches semantic overlays only by path ID and exact canonical evidence references', () => {
  const isRecord = executableFunction(propagationView, 'isRecord')
  const optionalText = executableFunction(propagationView, 'optionalText')
  const normalizeEvidenceReference = executableFunction(propagationView, 'normalizeEvidenceReference', {
    isRecord,
    optionalText,
  })
  const normalizeEvidenceRefs = executableFunction(propagationView, 'normalizeEvidenceRefs', {
    normalizeEvidenceReference,
  })
  const normalizePathId = functionOr(propagationView, 'normalizePathId', (value) => String(value ?? '').trim())
  const sameEvidenceRefs = executableFunction(propagationView, 'sameEvidenceRefs', { normalizeEvidenceRefs })
  const pathEvidenceRefs = executableFunction(propagationView, 'pathEvidenceRefs', { normalizeEvidenceRefs })
  const normalizeSemanticOverlay = executableFunction(propagationView, 'normalizeSemanticOverlay', { normalizeEvidenceRefs })
  const findPathSemanticOverlay = executableFunction(propagationView, 'findPathSemanticOverlay', {
    normalizePathId,
    sameEvidenceRefs,
    pathEvidenceRefs,
    normalizeSemanticOverlay,
  })
  const exactMatch = semanticOverlay('42', ['weibo:post:post-42', 'weibo:comment:comment-42'])
  const wrongEvidence = semanticOverlay('42', ['weibo:post:other'])
  const evidenceOnlyMatch = semanticOverlay('not-the-path', ['weibo:post:post-42', 'weibo:comment:comment-42'])

  for (const invalid of [
    ' weibo:post:post-42',
    'weibo:post:post-42 ',
    'weibo::post-42',
    'weibo:video:post-42',
    'weibo:post:post-42:extra',
  ]) {
    assert.equal(normalizeEvidenceReference(invalid), '')
  }

  assert.deepEqual(
    normalizeEvidenceRefs([
      { platform: 'weibo', post_id: 'post-42' },
      { platform: 'weibo', comment_id: 'comment-42' },
      'weibo:post:post-43',
      { author_id: 'u1' },
      'post-44',
    ]),
    ['weibo:post:post-42', 'weibo:comment:comment-42', 'weibo:post:post-43'],
  )

  assert.deepEqual(
    findPathSemanticOverlay({
      path_id: 42,
      evidence_refs: [
        { platform: 'weibo', post_id: 'post-42' },
        { platform: 'weibo', comment_id: 'comment-42' },
      ],
    }, [wrongEvidence, evidenceOnlyMatch, exactMatch]),
    exactMatch.semantic_overlay,
  )
  assert.equal(findPathSemanticOverlay({ path_id: 42, evidence_refs: ['weibo:post:post-42'] }, [wrongEvidence]), null)
  assert.equal(findPathSemanticOverlay({ path_id: 84, evidence_refs: exactMatch.semantic_overlay.evidence_refs }, [exactMatch]), null)
  assert.equal(findPathSemanticOverlay({ path_id: 42 }, [exactMatch]), null)
})

test('never falls back to a generic propagation overlay for a Claim Response path', () => {
  const isRecord = executableFunction(propagationView, 'isRecord')
  const optionalText = executableFunction(propagationView, 'optionalText')
  const normalizeEvidenceReference = executableFunction(propagationView, 'normalizeEvidenceReference', {
    isRecord,
    optionalText,
  })
  const normalizeEvidenceRefs = executableFunction(propagationView, 'normalizeEvidenceRefs', {
    normalizeEvidenceReference,
  })
  const sameEvidenceRefs = executableFunction(propagationView, 'sameEvidenceRefs', { normalizeEvidenceRefs })
  const pathEvidenceRefs = executableFunction(propagationView, 'pathEvidenceRefs', { normalizeEvidenceRefs })
  const normalizeSemanticOverlay = executableFunction(propagationView, 'normalizeSemanticOverlay', { normalizeEvidenceRefs })
  const normalizePathId = functionOr(propagationView, 'normalizePathId', (value) => String(value ?? '').trim())
  const findPathSemanticOverlay = executableFunction(propagationView, 'findPathSemanticOverlay', {
    normalizePathId,
    sameEvidenceRefs,
    pathEvidenceRefs,
    normalizeSemanticOverlay,
  })
  const hasNonEmptyDistribution = functionOr(propagationView, 'hasNonEmptyDistribution', () => true, { isRecord })
  const hasSemanticFeatureRecords = functionOr(propagationView, 'hasSemanticFeatureRecords', () => true, { isRecord })
  const hasNonEmptyTextList = functionOr(propagationView, 'hasNonEmptyTextList', () => true)
  const hasCanonicalEvidenceRefs = executableFunction(propagationView, 'hasCanonicalEvidenceRefs', {
    normalizeEvidenceRefs,
  })
  const isSemanticOverlayPayload = executableFunction(propagationView, 'isSemanticOverlayPayload', {
    isRecord,
    hasNonEmptyDistribution,
    hasSemanticFeatureRecords,
    hasNonEmptyTextList,
    hasCanonicalEvidenceRefs,
  })
  const hasPropagationPathOverlays = executableFunction(propagationView, 'hasPropagationPathOverlays', {
    isRecord,
    normalizePathId,
    isSemanticOverlayPayload,
  })
  const selectSemanticPathOverlay = executableFunction(propagationView, 'selectSemanticPathOverlay', {
    selectClaimResponseSemanticOverlay: claimResponsePresentation.selectClaimResponseSemanticOverlay,
    hasPropagationPathOverlays,
    findPathSemanticOverlay,
  })
  const generic = semanticOverlay('claim-path', ['weibo:post:official', 'weibo:comment:response'])
  const path = {
    path_id: 'claim-path',
    evidence_refs: ['weibo:post:official', 'weibo:comment:response'],
    metadata: { claim_response: true },
  }

  assert.equal(selectSemanticPathOverlay(path, {
    status: 'ready',
    evidence: { cross_analysis: { propagation_path_overlays: [generic] } },
  }, {}), null)
})

test('selects the direct Claim Response semantic overlay without a generic propagation artifact', () => {
  const overlay = semanticOverlay('claim-path', ['weibo:post:official', 'weibo:comment:response']).semantic_overlay
  const selected = claimResponsePresentation.selectClaimResponseSemanticOverlay({
    evidence_refs: ['weibo:post:official', 'weibo:comment:response'],
    metadata: {
      claim_response: true,
      claim_response_semantic_overlay: overlay,
    },
  })

  assert.deepEqual(selected, overlay)
})

test('keeps direct-comment downstream reach unavailable rather than treating it as zero', () => {
  assert.equal(
    claimResponsePresentation.claimResponseDownstreamReachText({
      downstream_reach_status: 'unavailable',
      downstream_reach_reason: 'direct_comment_thread_network_reach_not_computed',
    }),
    '评论链路径，未计算网络下游覆盖',
  )
  assert.equal(claimResponsePresentation.claimResponseDownstreamReachText({
    downstream_reach_status: 'available',
    downstream_reach_reason: null,
  }), null)
})

test('fails closed when any required nested semantic overlay field is empty or malformed', () => {
  const isRecord = executableFunction(propagationView, 'isRecord')
  const optionalText = executableFunction(propagationView, 'optionalText')
  const hasNonEmptyDistribution = functionOr(propagationView, 'hasNonEmptyDistribution', () => true, { isRecord })
  const hasSemanticFeatureRecords = functionOr(propagationView, 'hasSemanticFeatureRecords', () => true, { isRecord })
  const hasNonEmptyTextList = functionOr(propagationView, 'hasNonEmptyTextList', () => true)
  const normalizePathId = functionOr(propagationView, 'normalizePathId', (value) => String(value ?? '').trim())
  const normalizeEvidenceReference = executableFunction(propagationView, 'normalizeEvidenceReference', {
    isRecord,
    optionalText,
  })
  const normalizeEvidenceRefs = executableFunction(propagationView, 'normalizeEvidenceRefs', {
    normalizeEvidenceReference,
  })
  const hasCanonicalEvidenceRefs = executableFunction(propagationView, 'hasCanonicalEvidenceRefs', {
    normalizeEvidenceRefs,
  })
  const isSemanticOverlayPayload = executableFunction(propagationView, 'isSemanticOverlayPayload', {
    isRecord,
    hasNonEmptyDistribution,
    hasSemanticFeatureRecords,
    hasNonEmptyTextList,
    hasCanonicalEvidenceRefs,
  })
  const hasPropagationPathOverlays = executableFunction(propagationView, 'hasPropagationPathOverlays', {
    isRecord,
    normalizePathId,
    isSemanticOverlayPayload,
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
    (overlay) => { overlay.semantic_overlay.evidence_refs = [{ post_id: 'post-1' }] },
    (overlay) => { overlay.semantic_overlay.evidence_refs = ['post-1'] },
  ]) {
    const malformed = structuredClone(valid)
    mutate(malformed)
    assert.equal(hasPropagationPathOverlays({ cross_analysis: { propagation_path_overlays: [malformed] } }), false)
  }
})

test('keeps malformed, blocked, and empty semantic projections unavailable', () => {
  const semanticPathOverlay = bodyOf(propagationView, 'selectSemanticPathOverlay')
  const pathDrawer = propagationView.slice(
    propagationView.indexOf('<a-drawer v-model:open="claimPathDetailOpen"'),
    propagationView.indexOf('<a-drawer v-model:open="nodeDetailOpen"'),
  )

  assert.match(semanticPathOverlay, /path\?\.metadata\?\.claim_response === true/)
  assert.match(semanticPathOverlay, /semantic\?\.status !== 'ready'/)
  assert.match(semanticPathOverlay, /!linkedArtifact/)
  assert.match(semanticPathOverlay, /!hasPropagationPathOverlays\(semantic\.evidence\)/)
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

test('renders backend clustered propagation nodes with forward evidence relationships', () => {
  const graphOption = bodyOf(propagationView, 'buildPathGraphOption')

  assert.match(graphOption, /const treeEdges = summary\?\.tree_edges \?\? \[\]/)
  assert.match(graphOption, /hasBackendLayout/)
  assert.match(graphOption, /layout_x/)
  assert.match(graphOption, /targetLayer > sourceLayer/)
  assert.match(graphOption, /links:\s*graphLinks/)
  assert.match(graphOption, /draggable:\s*false/)
  assert.match(graphOption, /edgeSymbol:/)
  assert.match(graphOption, /focus:\s*'adjacency'/)
})

test('keeps evidence time series separate from relative model forecast steps', () => {
  const trendOption = bodyOf(propagationView, 'buildModelTrendOption')
  const evidenceOption = bodyOf(propagationView, 'buildEvidenceTimelineOption')

  assert.match(trendOption, /真实观测累计/)
  assert.match(trendOption, /模型相对步/)
  assert.doesNotMatch(trendOption, /macro\.observed_points/)
  assert.doesNotMatch(trendOption, /macro\.realized_points/)
  assert.match(evidenceOption, /observed_points/)
  assert.match(evidenceOption, /realized_points/)
  assert.match(evidenceOption, /历史实际累计/)
})

test('renders active-window controls and evidence zoom without assigning timestamps to forecast steps', () => {
  const option = bodyOf(propagationView, 'buildEvidenceTimelineOption')

  assert.match(propagationView, /getPropagationEventTimeline/)
  assert.match(propagationView, /timelineRange/)
  assert.match(propagationView, /活跃期/)
  assert.match(propagationView, /24小时/)
  assert.match(propagationView, /7天/)
  assert.match(propagationView, /全部/)
  assert.match(option, /type: 'inside'/)
  assert.match(option, /type: 'slider'/)
  assert.match(option, /真实观测累计/)
  assert.match(option, /历史实际累计/)
  assert.match(bodyOf(propagationView, 'buildModelTrendOption'), /模型相对步/)
})

test('refreshes the evidence timeline after an analyst changes the event scope', () => {
  assert.match(bodyOf(propagationView, 'handleAnalyze'), /loadEvidenceTimeline\(\)/)
  assert.match(bodyOf(propagationView, 'handlePredict'), /loadEvidenceTimeline\(\)/)
})

test('claim response stance styling is disabled until semantic coverage is ready', () => {
  const ready = propagationView.slice(
    propagationView.indexOf('const claimResponseSemanticReady = computed'),
    propagationView.indexOf('function claimResponseStanceClass'),
  )
  const stanceClass = bodyOf(propagationView, 'claimResponseStanceClass')

  assert.match(ready, /claimResponseLandscape\.value\?\.coverage\?\.semantic\?\.status === 'available'/)
  assert.match(stanceClass, /if \(!claimResponseSemanticReady\.value\) return 'claim-response-node-stance-neutral'/)
  assert.match(stanceClass, /claimResponseResponseStance\(response\)/)
  assert.match(stanceClass, /return stance \? `claim-response-node-stance-\$\{stance\}` : 'claim-response-node-stance-neutral'/)
})
