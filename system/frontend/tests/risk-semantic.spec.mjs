import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const riskView = readFileSync(resolve(frontendRoot, 'src/views/risk/index.vue'), 'utf8')
const semanticPage = readFileSync(resolve(frontendRoot, 'src/views/semantic-analysis/index.vue'), 'utf8')
const router = readFileSync(resolve(frontendRoot, 'src/router/index.ts'), 'utf8')

test('keeps the Event Review overview free of semantic artifact work', () => {
  assert.match(riskView, /RiskSectionTabs/)
  assert.doesNotMatch(riskView, /getEventSemantic/)
  assert.doesNotMatch(riskView, /getSemanticPageProjection/)
  assert.doesNotMatch(riskView, /SemanticEvidenceWorkbench/)
  assert.doesNotMatch(riskView, /semanticRequestSequence/)
})

test('loads one linked semantic evidence workspace from a compact projection', () => {
  for (const route of [
    '/risk/semantic-evidence',
    '/risk/semantic-clusters',
    '/risk/named-entities',
    '/risk/temporal-change',
    '/risk/verifiable-content',
  ]) {
    assert.match(router, new RegExp(`path: '${route.slice(1)}'`))
  }
  assert.match(semanticPage, /getSemanticWorkspace\(requestedEventId/)
  assert.doesNotMatch(semanticPage, /getEventSemantic\(requestedEventId\)/)
  assert.doesNotMatch(semanticPage, /getSemanticPageProjection/)
  assert.doesNotMatch(semanticPage, /toSemanticRecords\(/)
  assert.match(semanticPage, /selectedRelation/)
  assert.match(semanticPage, /toggleSingle\('entity'/)
})

test('isolates stale semantic workspace responses when the selected event changes', () => {
  assert.match(semanticPage, /let requestSequence = 0/)
  assert.match(semanticPage, /const sequence = \+\+requestSequence/)
  assert.match(semanticPage, /sequence !== requestSequence/)
  assert.match(semanticPage, /watch\(\(\) => route\.query\.event_id, syncRouteScope\)/)
})

test('keeps traceable content paginated and does not present it as a truth verdict', () => {
  assert.match(semanticPage, /可核验仅表示可定位回事件快照中的原始内容和引用，不等于事实已被证实。/)
  assert.match(semanticPage, /<APagination/)
  assert.match(semanticPage, /@change="loadWorkspace"/)
  assert.match(semanticPage, /record\.evidence_ref/)
  assert.match(semanticPage, /record\.source_url/)
})

test('keeps the Event Review shell usable on narrow screens', () => {
  assert.match(riskView, /@media \(max-width:900px\) \{[\s\S]*?\.case-toolbar,[\s\S]*?grid-template-columns:1fr/)
  assert.match(riskView, /\.overview-strip \{[\s\S]*?grid-template-columns:1fr 1fr/)
  assert.match(riskView, /\.case-select \{ width:min\(320px,60vw\)/)
})
