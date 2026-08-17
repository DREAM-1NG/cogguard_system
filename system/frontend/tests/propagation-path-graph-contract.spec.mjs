import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const source = readFileSync(new URL('../src/views/propagation/index.vue', import.meta.url), 'utf8')

test('propagation path graph renders backend tree edges with forward-layer filtering', () => {
  assert.match(source, /const treeEdges = summary\?\.tree_edges \?\? \[\]/)
  assert.match(source, /targetLayer > sourceLayer/)
  assert.doesNotMatch(source, /links:\s*\[\]/)
})

test('propagation path graph prefers the backend clustered coordinates', () => {
  assert.match(source, /Number\.isFinite\(Number\(node\.layout_x\)\)/)
  assert.match(source, /Number\.isFinite\(Number\(node\.layout_y\)\)/)
})

test('propagation monitoring keeps the alert-disposition tab in the delivered page', () => {
  assert.match(source, /key="alerts" tab="预警处置"/)
  assert.match(source, /loadPropagationAlerts/)
  assert.match(source, /applyPropagationAlertAction/)
})

test('role analysis keeps the ignition overview concise and evidence-backed', () => {
  assert.match(source, /ref="roleIgnitionGraphRef"/)
  assert.match(source, /function buildRoleIgnitionOption\(\)/)
  assert.match(source, /function renderRoleIgnitionGraph\(\)/)
  assert.match(source, /if \(sourceId !== rootId \|\| !targetId \|\| targetId === rootId\) continue/)
  assert.match(source, /\.slice\(0, 12\)/)
  assert.match(source, /name: shortNodeLabel\(edge\.targetName\)/)
  assert.match(source, /type === 'explicit' \? 'solid' : 'dashed'/)
  assert.match(source, /openNodeDetail\(String\(params\.data\?\.userId/)
})
