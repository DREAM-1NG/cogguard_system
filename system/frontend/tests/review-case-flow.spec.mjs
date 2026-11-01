import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const riskView = readFileSync(resolve(frontendRoot, 'src/views/risk/index.vue'), 'utf8')
const reviewCaseApi = readFileSync(resolve(frontendRoot, 'src/api/reviewCases.ts'), 'utf8')

function bodyOf(source, name) {
  const start = source.indexOf(`function ${name}(`)
  assert.notEqual(start, -1, `Expected ${name} to exist`)
  const brace = source.indexOf('{', source.indexOf(')', start))
  let depth = 0
  for (let index = brace; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1
    if (source[index] === '}') depth -= 1
    if (depth === 0) return source.slice(start, index + 1)
  }
  throw new Error(`Could not extract ${name}`)
}

test('restores a linked event to its exact review case', () => {
  const initialLoad = bodyOf(riskView, 'loadInitialCase')
  assert.match(initialLoad, /const linkedEventId = queryText\(route\.query\.event_id\)/)
  assert.match(initialLoad, /const matched = items\.find\(\(item\) => item\.event_id === linkedEventId\)/)
  assert.match(initialLoad, /return loadCase\(matched\.case_id\)/)
})

test('keeps the risk overview free of evidence-page loading', () => {
  const loadCase = bodyOf(riskView, 'loadCase')
  assert.match(loadCase, /getReviewCase\(caseId\)/)
  assert.match(loadCase, /listCaseActivities\(caseId/)
  assert.doesNotMatch(riskView, /getReviewCaseEvidence/)
  assert.doesNotMatch(riskView, /证据分组与标注/)
})

test('loads Student and audit data after case hydration, then Countermeasure after a completed audit', () => {
  const applyCase = bodyOf(riskView, 'applyCase')
  const loadAudit = bodyOf(riskView, 'loadAudit')
  assert.match(applyCase, /void loadStudent\(detail\.case_id\)/)
  assert.match(applyCase, /void loadAudit\(detail\.case_id\)/)
  assert.match(loadAudit, /response\.data\.status === 'completed'/)
  assert.match(loadAudit, /void loadCountermeasure\(caseId\)/)
  assert.match(reviewCaseApi, /export function getStudentAssessment/)
  assert.match(reviewCaseApi, /export function getReviewAudit/)
  assert.match(reviewCaseApi, /export function getCountermeasureReport/)
  assert.match(reviewCaseApi, /countermeasure-report\.md/)
})

test('requests a content-harm Teacher task and lets the server select representative posts', () => {
  const submit = bodyOf(riskView, 'submitReviewRequest')
  assert.match(submit, /review_tasks: \['interpersonal_harm'\]/)
  assert.match(submit, /evidence_refs: \[\]/)
  assert.match(riskView, /审计范围/)
  assert.match(riskView, /内容伤害/)
  assert.match(riskView, /代表性高互动帖子/)
})

test('shows only persisted governance references and an advisory-only Countermeasure draft', () => {
  assert.match(riskView, /teacherAudit\.governance\.available/)
  assert.match(riskView, /teacherAudit\.governance\.references/)
  assert.match(riskView, /countermeasure\?\.status === 'available'/)
  assert.match(riskView, /teacherAudit\.selection\.items/)
  assert.match(riskView, /本次实际审阅材料/)
  assert.match(riskView, /不会自动发布或执行内容、账号处置/)
  assert.match(riskView, /下载 Markdown/)
})

test('retains the human draft and immutable confirmation workflow', () => {
  const save = bodyOf(riskView, 'saveDraftNow')
  const confirm = bodyOf(riskView, 'submitDecisionConfirmation')
  assert.match(save, /saveDecisionDraft\(currentCase\.value\.case_id/)
  assert.match(save, /expected_version: draftVersion\.value/)
  assert.match(confirm, /await confirmDecision\(currentCase\.value\.case_id/)
  assert.match(riskView, /<a-form v-if="!decisionLocked"/)
  assert.match(riskView, /<a-descriptions v-else/)
})

test('refreshes lazily projected result areas after relevant activity events', () => {
  const recovery = bodyOf(riskView, 'recoverCaseActivities')
  assert.match(recovery, /review_advisory_available.*teacher_review_failed.*countermeasure_report_available/s)
  assert.match(recovery, /void loadAudit\(caseId\)/)
  assert.match(recovery, /void loadCountermeasure\(caseId\)/)
  assert.match(recovery, /student_assessed/)
  assert.doesNotMatch(recovery, /getReviewCaseEvidence/)
})
