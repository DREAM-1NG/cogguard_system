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
  const start = source.indexOf(`function ${name}`)
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

test('opens an exact event deep link when event_id matches a review case', () => {
  const loadInitialCase = bodyOf(riskView, 'loadInitialCase')
  const applyCase = bodyOf(riskView, 'applyCase')

  assert.match(loadInitialCase, /const linkedEventId = queryText\(route\.query\.event_id\)/)
  assert.match(loadInitialCase, /await loadCaseOptions\(linkedEventId\)/)
  assert.match(loadInitialCase, /item\.event_id === linkedEventId/)
  assert.match(loadInitialCase, /await loadCase\(matched\.case_id\)/)
  assert.match(applyCase, /router\.replace\(\{\s*query:/s)
  assert.match(applyCase, /case_id: detail\.case_id/)
  assert.match(applyCase, /event_id: detail\.event_id/)
})

test('resets selected evidence when switching events', () => {
  const applyCase = bodyOf(riskView, 'applyCase')

  assert.match(applyCase, /selectedEvidenceRefs\.value = \[\]/)
  assert.match(applyCase, /hydrateDraft\(detail\)/)
  assert.match(applyCase, /await loadActivities\(detail\.case_id\)/)
})

test('groups evidence by assessment and binds annotations to the selected evidence ref', () => {
  const groups = riskView.slice(
    riskView.indexOf('const evidenceGroups = computed'),
    riskView.indexOf('const allEvidenceItems = computed'),
  )
  const submitAnnotation = bodyOf(riskView, 'submitAnnotation')

  assert.match(groups, /key: 'supports'.*items: data\?\.supports \|\| \[\]/)
  assert.match(groups, /key: 'contradicts'.*items: data\?\.contradicts \|\| \[\]/)
  assert.match(groups, /key: 'irrelevant'.*items: data\?\.irrelevant \|\| \[\]/)
  assert.match(groups, /key: 'unresolved'.*items: data\?\.unresolved \|\| \[\]/)
  assert.match(riskView, /@change="toggleEvidenceRef\(item\.evidence_ref\)"/)
  assert.match(submitAnnotation, /await flushDraftBeforeCaseMutation\(\)/)
  assert.match(submitAnnotation, /annotateReviewCaseEvidence\(currentCase\.value\.case_id,\s*\{[\s\S]*evidence_ref: annotationTarget\.value\.evidence_ref/)
})

test('allows review request submission without selected evidence refs', () => {
  const submitReviewRequest = bodyOf(riskView, 'submitReviewRequest')

  assert.match(riskView, /v-model:value="selectedEvidenceRefs"[\s\S]*mode="multiple"[\s\S]*:options="evidenceRefOptions"/)
  assert.match(submitReviewRequest, /await flushDraftBeforeCaseMutation\(\)/)
  assert.match(submitReviewRequest, /requestReviewAdvisory\(currentCase\.value\.case_id,\s*\{[\s\S]*evidence_refs: selectedEvidenceRefs\.value/)
  assert.doesNotMatch(submitReviewRequest, /selectedEvidenceRefs\.value\.length\s*[<>=!]/)
})

test('restores server draft before falling back to confirmed advisory or preliminary defaults', () => {
  const hydrateDraft = bodyOf(riskView, 'hydrateDraft')

  assert.match(hydrateDraft, /const serverDraft = detail\.decision_draft/)
  assert.match(hydrateDraft, /if \(serverDraft\) \{[\s\S]*draftForm\.conclusion = serverDraft\.conclusion/)
  assert.match(hydrateDraft, /else if \(detail\.confirmed_decision\)/)
  assert.match(hydrateDraft, /else if \(detail\.review_advisory\)/)
  assert.match(hydrateDraft, /else \{[\s\S]*draftForm\.conclusion = detail\.preliminary_finding\.conclusion/)
  assert.match(hydrateDraft, /draftVersion\.value = serverDraft\?\.draft_version \|\| 0/)
  assert.match(hydrateDraft, /draftDirty\.value = !decisionLocked\.value && !serverDraft/)
})

test('serializes autosave requests and reschedules when edits arrive during a save', () => {
  const saveDraftNow = bodyOf(riskView, 'saveDraftNow')

  assert.match(saveDraftNow, /if \(draftSavePromise\) await draftSavePromise/)
  assert.match(saveDraftNow, /const editRevision = draftEditRevision\.value/)
  assert.match(saveDraftNow, /expected_version: draftVersion\.value/)
  assert.match(saveDraftNow, /draftSavePromise = saveDecisionDraft\(caseId, payload\)/)
  assert.match(saveDraftNow, /if \(draftEditRevision\.value === editRevision\) \{[\s\S]*draftDirty\.value = false/)
  assert.match(saveDraftNow, /else \{[\s\S]*scheduleDraftSave\(\)/)
  assert.match(saveDraftNow, /draftSavePromise = null/)
})

test('marks a 409 draft conflict and blocks further mutation until refreshed', () => {
  const saveDraftNow = bodyOf(riskView, 'saveDraftNow')
  const isConflictError = bodyOf(riskView, 'isConflictError')
  const canConfirmDecision = riskView.slice(
    riskView.indexOf('const canConfirmDecision = computed'),
    riskView.indexOf('const draftStatusText = computed'),
  )

  assert.match(isConflictError, /status\) === 409/)
  assert.match(saveDraftNow, /if \(isConflictError\(error\)\) \{[\s\S]*draftConflict\.value = 'version_conflict'/)
  assert.match(saveDraftNow, /draftConflict\.value = 'version_conflict'/)
  assert.match(canConfirmDecision, /&& !draftConflict\.value/)
  assert.match(riskView, /:disabled="!draftDirty \|\| Boolean\(draftConflict\)"/)
})

test('flushes the latest draft before annotation review request or decision confirmation', () => {
  const flushDraftBeforeCaseMutation = bodyOf(riskView, 'flushDraftBeforeCaseMutation')
  const submitAnnotation = bodyOf(riskView, 'submitAnnotation')
  const submitReviewRequest = bodyOf(riskView, 'submitReviewRequest')
  const submitDecisionConfirmation = bodyOf(riskView, 'submitDecisionConfirmation')

  assert.match(flushDraftBeforeCaseMutation, /return Boolean\(await saveDraftNow\(\{ silent: true \}\)\)/)
  assert.match(submitAnnotation, /if \(!\(await flushDraftBeforeCaseMutation\(\)\)\) return[\s\S]*annotateReviewCaseEvidence/)
  assert.match(submitReviewRequest, /if \(!\(await flushDraftBeforeCaseMutation\(\)\)\) return[\s\S]*requestReviewAdvisory/)
  assert.match(submitDecisionConfirmation, /while \(draftDirty\.value \|\| draftVersion\.value === 0\) \{[\s\S]*await saveDraftNow\(\{ silent: true \}\)/)
  assert.match(submitDecisionConfirmation, /confirmDecision\(currentCase\.value\.case_id,\s*\{[\s\S]*expected_draft_version: draftVersion\.value/)
})

test('locks confirmed decisions as read-only but permits reconfirmation when action is required', () => {
  const decisionLocked = riskView.slice(
    riskView.indexOf('const decisionLocked = computed'),
    riskView.indexOf('const canConfirmDecision = computed'),
  )
  const submitDecisionConfirmation = bodyOf(riskView, 'submitDecisionConfirmation')

  assert.match(decisionLocked, /currentCase\.value\?\.confirmed_decision/)
  assert.match(decisionLocked, /currentCase\.value\.action_required !== 'reconfirm_decision'/)
  assert.match(riskView, /<a-form v-if="!decisionLocked"/)
  assert.match(riskView, /<a-descriptions v-else/)
  assert.match(submitDecisionConfirmation, /if \(!currentCase\.value \|\| decisionLocked\.value \|\| draftConflict\.value\) return/)
})

test('recovers business activities from the last cursor and refreshes case evidence for material events', () => {
  const loadActivities = bodyOf(riskView, 'loadActivities')
  const recoverCaseActivities = bodyOf(riskView, 'recoverCaseActivities')

  assert.match(loadActivities, /listCaseActivities\(caseId, \{ limit: 100 \}\)/)
  assert.match(loadActivities, /activityCursor\.value = res\.data\.next_cursor \|\| 0/)
  assert.match(recoverCaseActivities, /readCaseEventStream\(caseId, activityCursor\.value, controller\.signal\)/)
  assert.match(recoverCaseActivities, /listCaseActivities\(caseId,\s*\{[\s\S]*after_id: activityCursor\.value/)
  assert.match(recoverCaseActivities, /new Set\(activities\.value\.map\(\(item\) => item\.cursor\)\)/)
  assert.match(recoverCaseActivities, /activityCursor\.value = response\.data\.next_cursor \|\| activityCursor\.value/)
  assert.match(recoverCaseActivities, /snapshot_added.*reconfirmation_required/s)
  assert.match(recoverCaseActivities, /getReviewCaseEvidence\(caseId\)/)
})

test('sends Last-Event-ID only when recovering after a known activity cursor', () => {
  const readCaseEventStream = bodyOf(reviewCaseApi, 'readCaseEventStream')

  assert.match(readCaseEventStream, /events\/stream\?after_id=\$\{lastEventId\}/)
  assert.match(readCaseEventStream, /Accept: 'text\/event-stream'/)
  assert.match(readCaseEventStream, /lastEventId > 0 \? \{ 'Last-Event-ID': String\(lastEventId\) \} : \{\}/)
  assert.match(readCaseEventStream, /parseCaseEventStream\(await response\.text\(\)\)/)
})

test('parses event-stream blocks into ordered case activity events', () => {
  const parseCaseEventStream = bodyOf(reviewCaseApi, 'parseCaseEventStream')

  assert.match(parseCaseEventStream, /payload\.split\(\/\\r\?\\n\\r\?\\n\/\)/)
  assert.match(parseCaseEventStream, /line\.startsWith\('id:'\)/)
  assert.match(parseCaseEventStream, /line\.startsWith\('event:'\)/)
  assert.match(parseCaseEventStream, /line\.startsWith\('data:'\)/)
  assert.match(parseCaseEventStream, /JSON\.parse\(data\)/)
  assert.match(parseCaseEventStream, /events\.push\(\{ \.\.\.parsed, cursor, activity_type: activityType as CaseEvent\['activity_type'\] \}\)/)
})

test('does not leak prototype or mock wording in visible review case copy', () => {
  const visibleCopy = riskView
    .replace(/<script setup[\s\S]*?<\/script>/, '')
    .replace(/<style scoped>[\s\S]*?<\/style>/, '')
  assert.doesNotMatch(visibleCopy, /mock|mock_weibo|TODO|测试数据|示例数据|占位|假数据/i)
})
