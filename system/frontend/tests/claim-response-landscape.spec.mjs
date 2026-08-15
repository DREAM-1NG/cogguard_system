import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const propagationView = readFileSync(resolve(frontendRoot, 'src/views/propagation/index.vue'), 'utf8')
const propagationApi = readFileSync(resolve(frontendRoot, 'src/api/propagation.ts'), 'utf8')

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

test('claim response API client exposes the event and platform-scoped projection', () => {
  assert.match(propagationApi, /export type ClaimResponseLandscapeParams = \{/)
  assert.match(propagationApi, /event_id: string/)
  assert.match(propagationApi, /platform\?: string/)
  assert.match(propagationApi, /export type ClaimResponseLandscapeProjection = \{/)
  assert.match(propagationApi, /claim_anchor\?: ClaimResponseClaimAnchor \| null/)
  assert.match(propagationApi, /official_publications: ClaimResponsePublication\[\]/)
  assert.match(propagationApi, /influential_responses: ClaimResponseInfluentialResponse\[\]/)
  assert.match(propagationApi, /function getClaimResponseLandscape\(params: ClaimResponseLandscapeParams\)/)
  assert.match(propagationApi, /request\.get\('\/propagation\/claim-response-landscape', \{ params \}\)/)
})

test('propagation page adds one claim-response tab without replacing existing propagation tabs', () => {
  for (const tab of [
    'key="path" tab="传播路径"',
    'key="objects" tab="传播对象"',
    'key="evidence" tab="角色分析"',
    'key="timeline" tab="时间线"',
    'key="model" tab="趋势预测"',
    'key="alerts" tab="预警处置"',
    'key="claim-response" tab="主张回应图谱"',
  ]) {
    assert.match(propagationView, new RegExp(tab))
  }
  assert.match(propagationView, /getClaimResponseLandscape/)
  assert.match(propagationView, /loadClaimResponseLandscape/)
})

test('claim response tab renders anchored claim, two evidence lanes, and explicit blocked or empty states', () => {
  const tabStart = propagationView.indexOf('key="claim-response" tab="主张回应图谱"')
  assert.notEqual(tabStart, -1, 'Expected claim response tab to exist')
  const tabSource = propagationView.slice(tabStart, propagationView.indexOf('</a-tab-pane>', tabStart))

  assert.match(tabSource, /权威主张锚点/)
  assert.match(tabSource, /claimResponseLandscape\?\.claim_anchor/)
  assert.match(tabSource, /authority_source_id/)
  assert.match(tabSource, /claim-response-official-lane/)
  assert.match(tabSource, /官方发布/)
  assert.match(tabSource, /claim-response-response-lane/)
  assert.match(tabSource, /影响回应/)
  assert.match(tabSource, /claim-response-node/)
  assert.match(tabSource, /claimResponseNodeSize\(item\)/)
  assert.match(tabSource, /claimResponseStanceClass\(item\)/)
  assert.match(tabSource, /claimResponseBlocked/)
  assert.match(tabSource, /claimResponseEmptyDescription/)
  assert.match(tabSource, /a-empty/)
})

test('claim response view keeps influence ranking platform-local and path-backed', () => {
  const requestParams = bodyOf(propagationView, 'claimResponseRequestParams')
  const openPathDetail = bodyOf(propagationView, 'openClaimResponsePathDetail')

  assert.match(propagationView, /v-model:value="claimResponsePlatform"/)
  assert.match(propagationView, /平台内影响力/)
  assert.match(requestParams, /platform: claimResponsePlatform\.value \|\| undefined/)
  assert.match(propagationView, /rank_scope === 'platform'/)
  assert.match(openPathDetail, /openClaimPathDetail/)
  assert.match(openPathDetail, /pathRef\.evidence_refs/)
  assert.doesNotMatch(propagationView, /author_name.*官方/)
  assert.doesNotMatch(propagationView, /verification_context.*authority_binding/)
})

test('claim response path drill-down uses only observed nodes and declines an unnamed path', () => {
  const openPathDetail = bodyOf(propagationView, 'openClaimResponsePathDetail')

  assert.match(openPathDetail, /pathRef\.nodes/)
  assert.match(openPathDetail, /if \(!nodes\.length\)/)
  assert.match(openPathDetail, /message\.info/)
  assert.doesNotMatch(openPathDetail, /anchor\?\.account/)
  assert.doesNotMatch(openPathDetail, /\[anchor\?\.account, response\.author_id\]/)
})

test('claim response scope reset clears projection and related path and node drawers before reload', () => {
  const reset = bodyOf(propagationView, 'resetClaimResponseLandscape')
  const load = bodyOf(propagationView, 'loadClaimResponseLandscape')

  assert.match(reset, /claimResponseLandscape\.value = null/)
  assert.match(reset, /selectedClaimPathDetail\.value = null/)
  assert.match(reset, /claimPathDetailOpen\.value = false/)
  assert.match(reset, /selectedNodeDetail\.value = null/)
  assert.match(reset, /nodeDetailOpen\.value = false/)
  assert.match(load, /resetClaimResponseLandscape\(\)/)
  assert.ok(
    load.indexOf('resetClaimResponseLandscape()') < load.indexOf('getClaimResponseLandscape'),
    'Expected stale claim-response state to clear before a replacement request begins',
  )
})
