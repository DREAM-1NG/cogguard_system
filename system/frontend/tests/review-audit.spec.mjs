import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const riskView = readFileSync(resolve(frontendRoot, 'src/views/risk/index.vue'), 'utf8')
const dashboardView = readFileSync(resolve(frontendRoot, 'src/views/dashboard/index.vue'), 'utf8')
const reviewCaseApi = readFileSync(resolve(frontendRoot, 'src/api/reviewCases.ts'), 'utf8')

test('loads real audit projections without semantic artifact requests', () => {
  assert.match(riskView, /getReviewAudit/)
  assert.match(riskView, /getStudentAssessment/)
  assert.match(riskView, /getCountermeasureReport/)
  assert.doesNotMatch(riskView, /getEventSemantic/)
  assert.doesNotMatch(riskView, /SemanticEvidenceWorkbench/)
  assert.match(riskView, /智能审计/)
  assert.match(riskView, /本次审计使用的治理参考/)
  assert.match(riskView, /反制建议草案/)
  assert.doesNotMatch(riskView, /语义证据/)
  assert.match(riskView, /requestReviewAdvisory/)
})

test('keeps the review chain compact until an analyst expands a workflow step', () => {
  assert.match(riskView, /<h3>本案研判链<\/h3>/)
  assert.doesNotMatch(riskView, /从初步判断到人工处置草案/)
  assert.match(riskView, /<details class="step-body">/)
  assert.match(riskView, /<summary class="step-heading"/)
  assert.match(riskView, /step-body\[open\] \.step-heading/)
})

test('keeps the audit projection available to the selected event on the dashboard', () => {
  assert.match(reviewCaseApi, /export function getReviewAudit\(caseId: string\)/)
  assert.match(reviewCaseApi, /\/teacher-audit/)
  assert.match(dashboardView, /getReviewAudit\(matched\.case_id\)/)
  assert.match(dashboardView, /本案审计与治理参考/)
})
