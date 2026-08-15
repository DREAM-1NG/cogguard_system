import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')

async function loadPresentationHelper() {
  const helperSource = readFileSync(resolve(frontendRoot, 'src/views/propagation/claimResponsePresentation.ts'), 'utf8')
  const { outputText } = ts.transpileModule(helperSource, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2020,
    },
  })
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
}

const helper = await loadPresentationHelper()

const anchor = {
  case_id: 'case-1',
  claim_id: 'claim-1',
  authority_source_id: 'source-1',
  text: 'An anchored claim',
  account: 'authority-account',
  evidence_refs: ['anchor-evidence'],
}

test('ready projection preserves the anchor and exposes explicit empty lanes', () => {
  const projection = {
    status: 'ready',
    event_id: 'event-1',
    claim_anchor: anchor,
    official_publications: [],
    influential_responses: [],
    timeline: [],
    coverage: {},
  }

  const view = helper.presentClaimResponseLandscape(projection)

  assert.equal(view.status, 'ready')
  assert.equal(view.isReady, true)
  assert.deepEqual(view.anchor, anchor)
  assert.deepEqual(view.lanes, {
    officialPublications: [],
    influentialResponses: [],
    timeline: [],
  })
  assert.deepEqual(view.emptyLanes, {
    officialPublications: true,
    influentialResponses: true,
    timeline: true,
  })
})

test('presentation readiness requires both a ready projection and an anchor', () => {
  const readyWithoutAnchor = helper.presentClaimResponseLandscape({
    status: 'ready',
    event_id: 'event-1',
    official_publications: [],
    influential_responses: [],
    timeline: [],
    coverage: {},
  })
  const blockedWithAnchor = helper.presentClaimResponseLandscape({
    status: 'blocked',
    event_id: 'event-1',
    claim_anchor: anchor,
    official_publications: [],
    influential_responses: [],
    timeline: [],
    coverage: {},
  })

  assert.equal(readyWithoutAnchor.isReady, false)
  assert.equal(blockedWithAnchor.isReady, false)
  assert.equal(helper.presentClaimResponseLandscape(null).isReady, false)
})

test('path drill-down returns only observed nodes and exact evidence context', () => {
  const response = {
    rank: 1,
    platform: 'weibo',
    author_id: 'response-id',
    author_name: 'Response account',
    path_contribution: 0.42,
    path_refs: [],
  }
  const pathRef = {
    path_id: 'path-1',
    nodes: ['authority-node', 'response-node'],
    evidence_refs: ['evidence-1', 'evidence-2'],
    score: 0.88,
  }

  const model = helper.createClaimResponsePathDrilldown({ anchor, response, pathRef, index: 0 })

  assert.deepEqual(model, {
    pathId: 'path-1',
    nodes: ['authority-node', 'response-node'],
    evidenceRefs: ['evidence-1', 'evidence-2'],
    authorityAccount: 'authority-account',
    authoritySourceId: 'source-1',
    responseAccount: 'Response account',
    pathScore: 0.88,
    contribution: 0.42,
  })
  assert.equal(Object.hasOwn(model, 'supportingPosts'), false)
})

test('path drill-down rejects missing nodes or exact evidence references', () => {
  const response = { author_id: 'response-id', path_contribution: 0.42 }
  const missingNodes = helper.createClaimResponsePathDrilldown({
    anchor,
    response,
    pathRef: { path_id: 'path-1', nodes: [], evidence_refs: ['evidence-1'] },
    index: 0,
  })
  const missingEvidence = helper.createClaimResponsePathDrilldown({
    anchor,
    response,
    pathRef: { path_id: 'path-2', nodes: ['node-1'], evidence_refs: [] },
    index: 1,
  })

  assert.equal(missingNodes, null)
  assert.equal(missingEvidence, null)
})

test('production page delegates claim-response readiness and path detail decisions', () => {
  const source = readFileSync(resolve(frontendRoot, 'src/views/propagation/index.vue'), 'utf8')
  const readyStart = source.indexOf('const claimResponseReady = computed(() =>')
  const readyEnd = source.indexOf('const claimResponsePathEvidence', readyStart)
  const pathStart = source.indexOf('function openClaimResponsePathDetail(')
  const pathEnd = source.indexOf('function claimResponsePathEvidenceFromPath', pathStart)
  const readySource = source.slice(readyStart, readyEnd)
  const pathSource = source.slice(pathStart, pathEnd)

  assert.match(source, /from '\.\/claimResponsePresentation'/)
  assert.match(readySource, /claimResponsePresentation\.value\.isReady/)
  assert.doesNotMatch(readySource, /claimResponseLandscape\.value\?\.status/)
  assert.doesNotMatch(readySource, /claimResponseLandscape\.value\?\.claim_anchor/)
  assert.match(pathSource, /const drilldown = createClaimResponsePathDrilldown/)
  assert.doesNotMatch(pathSource, /const evidenceRefs = pathRef\.evidence_refs/)
  assert.doesNotMatch(pathSource, /const nodes = \(pathRef\.nodes/)
  assert.doesNotMatch(pathSource, /const pathScore = pathRef\.score/)
})
