import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  annotateReviewCaseEvidence: vi.fn(),
  confirmDecision: vi.fn(),
  getLatestReviewCase: vi.fn(),
  getReviewCase: vi.fn(),
  getReviewCaseEvidence: vi.fn(),
  listCaseActivities: vi.fn(),
  readCaseEventStream: vi.fn(),
  requestReviewAdvisory: vi.fn(),
  saveDecisionDraft: vi.fn(),
  searchReviewCases: vi.fn(),
}))

vi.mock('@/api/reviewCases', () => apiMocks)
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace: vi.fn() }),
}))

import RiskView from '@/views/risk/index.vue'

const caseDetail = {
  case_id: 'case-1',
  event_id: 'event-1',
  title: '待研判事件',
  preliminary_finding: {
    conclusion: 'insufficient_evidence',
    rationale: '当前证据尚不足以形成结论。',
    key_evidence_refs: [],
  },
  evidence_sufficiency: 'limited',
  sufficiency_reasons: ['已有部分来源'],
  missing_evidence: ['需要补充原始链接'],
  urgency: 'watch',
  disposition: 'gather_evidence',
  action_required: 'add_evidence',
  coordination_summary: {
    narrative: '暂未发现稳定的协调模式。',
    key_communities: [],
    key_accounts: [],
  },
  propagation_summary: {
    narrative: '传播范围仍在观察。',
    trend: 'stable',
    forecast_range: null,
    likely_next_targets: [],
  },
  updated_at: '2026-09-04T00:00:00Z',
  review_advisory: null,
  confirmed_decision: null,
  decision_draft: null,
}

const caseEvidence = {
  case_id: 'case-1',
  supports: [
    {
      evidence_ref: 'evidence-1',
      evidence_type: 'post',
      assessment: 'supports',
      title: '原始帖文',
      excerpt: '一条需要复核的公开帖文。',
      source_url: 'https://example.test/post/1',
      platform: 'weibo',
      observed_at: '2026-09-04T00:00:00Z',
      annotations: [],
    },
  ],
  contradicts: [],
  irrelevant: [],
  unresolved: [],
}

const caseSummary = {
  ...caseDetail,
  review_advisory: undefined,
  confirmed_decision: undefined,
  decision_draft: undefined,
}

function mountRiskView() {
  return mount(RiskView, {
    global: {
      stubs: {
        'a-alert': { template: '<div class="alert"><slot /></div>' },
        'a-button': { template: '<button><slot /></button>' },
        'a-card': { template: '<section><slot name="title" /><slot name="extra" /><slot /></section>' },
        'a-checkbox': { template: '<input type="checkbox" />' },
        'a-descriptions': { template: '<div><slot /></div>' },
        'a-descriptions-item': { template: '<div><slot /></div>' },
        'a-empty': { template: '<div class="empty"><slot /></div>' },
        'a-form': { template: '<form><slot /></form>' },
        'a-form-item': { template: '<label><slot /></label>' },
        'a-input': { template: '<input />' },
        'a-list': { template: '<div />' },
        'a-list-item': { template: '<div><slot /></div>' },
        'a-modal': { template: '<div v-if="open"><slot /></div>', props: { open: Boolean } },
        'a-popover': { template: '<div><slot /></div>' },
        'a-select': { template: '<div><slot /></div>' },
        'a-segmented': { template: '<div><slot /></div>' },
        'a-space': { template: '<div><slot /></div>' },
        'a-spin': { template: '<div><slot /></div>' },
        'a-tab-pane': { template: '<div><slot /></div>' },
        'a-tabs': { template: '<div><slot /></div>' },
        'a-tag': { template: '<span><slot /></span>' },
        'a-textarea': { template: '<textarea />' },
        'a-divider': { template: '<hr />' },
      },
    },
  })
}

describe('risk review view', () => {
  beforeEach(() => {
    apiMocks.getLatestReviewCase.mockResolvedValue({ data: caseDetail })
    apiMocks.getReviewCaseEvidence.mockResolvedValue({ data: caseEvidence })
    apiMocks.listCaseActivities.mockResolvedValue({
      data: { items: [], next_cursor: null },
    })
    apiMocks.searchReviewCases.mockResolvedValue({
      data: { items: [caseSummary], total: 1 },
    })
    apiMocks.saveDecisionDraft.mockResolvedValue({
      data: {
        case_id: 'case-1',
        draft_version: 1,
        conclusion: 'insufficient_evidence',
        urgency: 'watch',
        disposition: 'gather_evidence',
        rationale: '当前证据尚不足以形成结论。',
        key_evidence_refs: [],
        unresolved_items: ['需要补充原始链接'],
        saved_at: '2026-09-04T00:00:00Z',
      },
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('renders the loaded case after the initial empty state', async () => {
    const wrapper = mountRiskView()

    expect(wrapper.find('.empty-state').exists()).toBe(true)

    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.empty-state').exists()).toBe(false)
    expect(wrapper.find('.case-title').text()).toBe('待研判事件')
    expect(wrapper.text()).toContain('证据不足')
    expect(apiMocks.getLatestReviewCase).toHaveBeenCalledOnce()

    wrapper.unmount()
  })

  it('aborts the activity stream when the mounted view is unmounted', async () => {
    vi.useFakeTimers()
    let streamSignal: AbortSignal | undefined
    apiMocks.readCaseEventStream.mockImplementation(
      (_caseId: string, _cursor: number, signal?: AbortSignal) => {
        streamSignal = signal
        return new Promise((resolve) => {
          signal?.addEventListener('abort', () => resolve([]), { once: true })
        })
      },
    )

    const wrapper = mountRiskView()
    await flushPromises()
    await wrapper.vm.$nextTick()

    await vi.advanceTimersByTimeAsync(10000)
    expect(apiMocks.readCaseEventStream).toHaveBeenCalledOnce()
    expect(streamSignal?.aborted).toBe(false)

    wrapper.unmount()

    expect(streamSignal?.aborted).toBe(true)
  })
})
