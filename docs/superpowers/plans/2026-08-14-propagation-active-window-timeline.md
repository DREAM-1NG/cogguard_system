# Propagation Active-Window Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display evidence-backed propagation timelines at useful short-term detail by default, with range controls and zoom for longer inspection.

**Architecture:** Add a read-only event-timeline projection independent of slow checkpoint inference. The backend derives a deterministic active window and adaptive aggregation resolution. The frontend defaults to that window, renders date-based evidence with ECharts zoom, and keeps model-relative prediction steps separate.

**Tech Stack:** FastAPI, Pydantic, MongoDB event data, Vue 3, TypeScript, ECharts, pytest, Node test runner.

## Global Constraints

- Preserve the observed-prefix versus retrospective-holdout leakage boundary.
- Do not invent forecast timestamps, interpolate curves, or add unsupported heat/rank signals.
- Do not change checkpoint inputs, model outputs, Coordination, Propagation, or Review scores.
- Keep public product copy evidence-focused and in Chinese.

---

### Task 1: Backend Time Projection

**Files:**
- Modify: `system/backend/app/schemas/propagation.py`
- Modify: `system/backend/app/services/propagation_model_service.py`
- Modify: `system/backend/tests/test_propagation_prediction_service.py`

**Interfaces:**
- Produces `build_current_event_timeline(event_id, platform, timeline_range)` with range, resolution, active/window bounds, observed points, and realized points.

- [x] **Step 1: Write failing tests**

```python
def test_event_timeline_defaults_to_densest_six_hour_window(monkeypatch):
    monkeypatch.setattr(propagation_model_service, "_load_prediction_event_data", fake_event_data)
    result = asyncio.run(propagation_model_service.build_current_event_timeline(event_id="event-1"))
    assert result["range"] == "active"
    assert result["resolution"] == "minute"
    assert len(result["observed_points"]) > 24


def test_event_timeline_uses_range_resolution(monkeypatch):
    monkeypatch.setattr(propagation_model_service, "_load_prediction_event_data", fake_event_data)
    assert asyncio.run(propagation_model_service.build_current_event_timeline(event_id="event-1", timeline_range="24h"))["resolution"] == "hour"
    assert asyncio.run(propagation_model_service.build_current_event_timeline(event_id="event-1", timeline_range="7d"))["resolution"] == "day"
    assert asyncio.run(propagation_model_service.build_current_event_timeline(event_id="event-1", timeline_range="all"))["resolution"] == "week"
```

- [x] **Step 2: Verify red**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\test_propagation_prediction_service.py -q`

Expected: FAIL because `build_current_event_timeline` does not exist.

- [x] **Step 3: Implement minimal projection**

```python
class EventTimelineProjection(BaseModel):
    range: Literal["active", "24h", "7d", "all"]
    resolution: Literal["minute", "hour", "day", "week"]
    active_window: TimeWindow
    window: TimeWindow
    observed_points: list[CumulativeTimelinePoint]
    realized_points: list[CumulativeTimelinePoint]


async def build_current_event_timeline(*, event_id: str, platform: str | None = None, timeline_range: str = "active") -> dict[str, Any]:
    posts, comments = await _load_prediction_event_data(event_id=event_id, platform=platform)
    records = _timeline_event_records(posts, comments)
    active_window = _densest_window(records, span=timedelta(hours=6))
    window = _timeline_range_window(records, active_window, timeline_range)
    observed, realized = _partition_timeline_records(records, observed_until=None, observation_ratio=0.5)
    return _project_timeline(window, active_window, observed, realized)
```

Use closed bucket boundaries and carry forward cumulative totals. Select minute buckets for the six-hour active window, hour for 24 hours, day for 7 days, and week for all history. The projection does not use the former fixed 24-point cap.

- [x] **Step 4: Verify green**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\test_propagation_prediction_service.py -q`

Expected: PASS.

### Task 2: Fast Timeline Route

**Files:**
- Modify: `system/backend/app/api/v1/propagation.py`
- Modify: `system/backend/tests/test_propagation_prediction_service.py`

**Interfaces:**
- Produces authenticated `GET /api/v1/propagation/model-event-timeline` with `event_id`, optional `platform`, and `timeline_range`.

- [x] **Step 1: Write failing route test**

```python
def test_event_timeline_route_exposes_range_parameter():
    parameters = app.openapi()["paths"]["/api/v1/propagation/model-event-timeline"]["get"]["parameters"]
    assert {item["name"] for item in parameters} == {"event_id", "platform", "timeline_range"}
```

- [x] **Step 2: Verify red**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\test_propagation_prediction_service.py -q`

Expected: FAIL because the route is absent.

- [x] **Step 3: Implement route**

```python
@router.get("/model-event-timeline")
async def get_model_event_timeline(
    event_id: str,
    platform: str | None = None,
    timeline_range: Literal["active", "24h", "7d", "all"] = "active",
    _: User = Depends(require_current_user),
) -> dict[str, Any]:
    result = await propagation_model_service.build_current_event_timeline(
        event_id=event_id, platform=platform, timeline_range=timeline_range,
    )
    return {"code": 0, "data": result, "msg": "ok"}
```

- [x] **Step 4: Verify green**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\test_propagation_prediction_service.py -q`

Expected: PASS.

### Task 3: Range Controls And Zoom

**Files:**
- Modify: `system/frontend/src/api/propagation.ts`
- Modify: `system/frontend/src/views/propagation/index.vue`
- Modify: `system/frontend/tests/propagation-semantic.spec.mjs`

**Interfaces:**
- Consumes `getPropagationEventTimeline({ event_id, platform, timeline_range })`.
- Produces active/24h/7d/all controls and an ECharts real-time evidence chart with `inside` and `slider` data zoom.

- [x] **Step 1: Write failing frontend test**

```javascript
test('renders active-window controls and real-time zoom without assigning timestamps to forecast steps', () => {
  const option = bodyOf(propagationView, 'buildEvidenceTimelineOption')
  assert.match(propagationView, /getPropagationEventTimeline/)
  assert.match(propagationView, /timelineRange/)
  assert.match(option, /type: 'inside'/)
  assert.match(option, /type: 'slider'/)
  assert.match(option, /真实观测累计/)
  assert.match(option, /历史实际累计/)
  assert.match(bodyOf(propagationView, 'buildModelTrendOption'), /模型相对步/)
})
```

- [x] **Step 2: Verify red**

Run: `npm test -- --test-name-pattern="active-window"`

Expected: FAIL because the client, range state, and evidence chart do not exist.

- [x] **Step 3: Implement client and chart**

```ts
export type PropagationTimelineRange = 'active' | '24h' | '7d' | 'all'

export function getPropagationEventTimeline(params: PropagationEventTimelineParams) {
  return request.get<ApiResponse<PropagationEventTimelineProjection>>('/api/v1/propagation/model-event-timeline', { params })
}
```

```ts
const timelineRange = ref<PropagationTimelineRange>('active')
const evidenceTimeline = ref<PropagationEventTimelineProjection | null>(null)

async function loadEvidenceTimeline() {
  evidenceTimeline.value = (await getPropagationEventTimeline({
    event_id: eventId.value,
    platform: platform.value || undefined,
    timeline_range: timelineRange.value,
  })).data
}
```

Add compact Chinese controls labelled `活跃期`, `24小时`, `7天`, and `全部`. The evidence option uses real date labels, `showSymbol: false`, and `dataZoom` entries of type `inside` and `slider`. Keep the model chart limited to its observation endpoint and normalized model steps.

- [x] **Step 4: Verify green**

Run: `npm test -- --test-name-pattern="active-window"`

Expected: PASS.

### Task 4: Verify And Document

**Files:**
- Modify: `doc/engineering/development-log.md`
- Modify: `doc/engineering/development-roadmap.md`
- Modify: `system/README.md`

- [x] **Step 1: Run backend integration tests**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\test_propagation_prediction_service.py -q`

Expected: PASS.

- [x] **Step 2: Run frontend tests and production build**

Run: `npm test`

Expected: PASS.

Run: `npm run build`

Expected: PASS with delivery checks.

- [x] **Step 3: Synchronize documentation and validate the scoped worktree changes**

Document that the model tab defaults to a deterministic active period, exposes range controls and zoom, and retains future archive data solely for retrospective validation. Then stage only timeline code, tests, documentation, and this plan before committing `feat(propagation): add active-window timeline zoom`.
