# Propagation Active-Window Timeline Design

## Goal

Make the propagation trend readable at the event's active period by default,
while allowing analysts to inspect both shorter and longer real-time ranges.
This replaces the fixed 24-point, event-wide timeline projection.

## Scope

- Keep the existing three series semantically separate: observed cumulative
  evidence, model-relative forecast steps, and archived retrospective actuals.
- Default the real-time evidence view to the deterministic high-activity window.
- Provide active-period, 24-hour, 7-day, and full-history ranges, together with
  slider and in-chart zoom.
- Select minute, hour, day, or week buckets from the requested real-time range.
- Keep real timestamps for observed and retrospective data. Do not manufacture
  timestamps for the model's normalized forecast steps.

## Out Of Scope

- No hot-search rank, heat score, or second y-axis: the event data has no
  evidence-backed equivalent.
- No interpolation, smoothing, or forecast recalibration.
- No change to Coordination, Propagation, or Review scores, checkpoint inputs,
  or model output semantics.

## Design

The prediction response will expose a time-range projection whose evidence
points are aggregated at the smallest practical bucket size for that range.
The server determines the active range from the densest continuous evidence
period and returns its bounds with the projection. The client opens on that
range, provides named range controls, and uses ECharts `dataZoom` for short
and long inspection without changing evidence provenance.

The model-relative forecast remains visibly separate from the date-based
observed and retrospective series. The retrospective series remains a holdout
for archived-case backtesting and is never supplied to inference.

## Acceptance Criteria

1. The default projection has more detail than the former fixed 24 points and
   is focused on the active propagation period.
2. Analysts can choose active, 24-hour, 7-day, and full-history ranges and can
   zoom with ECharts controls.
3. Short ranges use minute/hour buckets; longer ranges use day/week buckets.
4. Observed and realized evidence retain source timestamps; forecast labels
   remain normalized model steps.
5. Large ranges remain bounded enough for responsive rendering.
6. Tests prove active-window selection, bucket choice, range contract, and
   frontend zoom/range controls.
