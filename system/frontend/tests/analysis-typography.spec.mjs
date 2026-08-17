import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const workbench = readFileSync(new URL('../src/components/SemanticEvidenceWorkbench.vue', import.meta.url), 'utf8')
const propagation = readFileSync(new URL('../src/views/propagation/index.vue', import.meta.url), 'utf8')

test('uses a readable typography tier for semantic evidence without enlarging its field labels', () => {
  assert.match(workbench, /\.section-heading h3 \{[^}]*font-size: 16px/)
  assert.match(workbench, /\.distribution-title \{[^}]*font-size: 14px/)
  assert.match(workbench, /\.distribution-legend-button \{[^}]*font-size: 14px/)
  assert.match(workbench, /\.entity-expand-button \{[^}]*font-size: 13px/)
  assert.match(workbench, /\.entity-type \{[^}]*font-size: 13px/)
  assert.match(workbench, /\.time-column \{[^}]*font-size: 13px/)
  assert.match(workbench, /\.community-row \{[^}]*font-size: 13px/)
  assert.match(workbench, /\.semantic-matrix-table \{[^}]*font-size: 14px/)
  assert.match(workbench, /\.semantic-matrix-table td::before \{[^}]*font-size: 12px/)
})

test('uses the same readable tier for propagation controls and evidence lists, not graph labels', () => {
  assert.match(propagation, /\.toolbar-group-label \{[^}]*font-size: 14px/)
  assert.match(propagation, /\.sync-hint \{[^}]*font-size: 14px/)
  assert.match(propagation, /\.section-title \{[^}]*font-size: 15px/)
  assert.match(propagation, /\.path-node-control-label,[^}]*font-size: 14px/)
  assert.match(propagation, /\.layer-row \{[^}]*font-size: 14px/)
  assert.match(propagation, /\.timeline-time \{[^}]*font-size: 14px/)
  assert.match(propagation, /\.forecast-label \{[^}]*font-size: 14px/)
  assert.match(propagation, /\.evidence-timeline-meta \{[^}]*font-size: 14px/)
})
