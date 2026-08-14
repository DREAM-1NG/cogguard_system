# Propagation Active Timeline Design

> Status: design approved by the user; implementation has not started.
>
> Scope: improve the existing authenticated `/propagation` model trend and
> backtest views for one event. This is a presentation and timeline-projection
> change; it does not retrain the propagation model or change its inputs.

## Goal

Show a detailed, timestamp-faithful propagation timeline by default, focused on
the event's most active short-term window. Analysts can inspect shorter and
longer periods without confusing archived actuals with model predictions.

## Decisions

- Default range is the server-selected active window, not the entire archival
  span. It is the contiguous 24-hour interval with the most valid timestamped
  event records; ties select the latest interval. Events spanning at most 24
  hours return their full valid range. The API returns this exact start and end.
- The timeline projection is requested for its visible time range. The server
  chooses its native bucket from the selected duration: one minute at most six
  hours, 15 minutes at most 48 hours, one hour at most 14 days, one day at most
  90 days, and one week thereafter.
- The UI exposes `Active period`, `24 hours`, `7 days`, and `All history`
  commands, plus ECharts inside zoom and a slider. Changing the visible range
  reloads the evidence projection at an appropriate resolution.
- Observed and held-out actual points share real timestamps. The model retains
  its existing normalized relative steps because no calibrated mapping from
  decoder step to wall-clock time exists.
- The product does not add a heat score, popularity rank, artificial smoothing,
  inferred timestamps, or a second axis without source data.

## API And Data Flow

`GET /api/v1/propagation/model-event-predict/cached` and the existing POST
prediction route accept `timeline_range=active|24h|7d|all` and optional paired
`timeline_start`/`timeline_end` parameters. Their response adds a `timeline`
projection descriptor containing the selected range, bucket unit, and
timestamped observed and realized cumulative points.

The model cache remains keyed by the observation prefix and snapshot
fingerprint. Range-specific timeline projection is calculated from timestamped
event evidence after a cached model result is read; it never changes model
inputs, final-size output, risk scores, or next-hop ranking. Missing or invalid
timestamps are excluded and reported as coverage metadata rather than being
invented.

## UI

The model tab has one compact time-range control above the real-time backtest
chart. It opens at the active period. Quick commands and ECharts zoom update
the range without blocking the path view. Symbols are suppressed for dense
series, restored when the range is narrow, and tooltips expose exact timestamp
and cumulative count.

The current model-relative prediction chart remains separate from the real-time
backtest chart. It keeps labels such as `Model relative step 1`; it must not be
laid over real timestamps. The backtest chart continues to show observed input
and held-out historical actuals as distinct unsmoothed series.

## Error Handling

- No timestamped records: retain the existing unavailable state and do not
  render a synthetic series.
- No active window: fall back to the valid full timestamp range and identify
  the returned selection as `full_history`.
- No realized records: hide the retrospective series/card while leaving the
  observed and relative-prediction views usable.
- Invalid range request: return a validation error rather than silently
  swapping its bounds.

## Acceptance Tests

1. A sparse old record cannot force the default view away from the densest
   active period.
2. A short selected range returns finer points than the full-history range.
3. Quick ranges, slider zoom, and inside zoom preserve exact timestamp order.
4. Model steps remain labelled as relative steps and never acquire fabricated
   dates.
5. Observed and realized series remain partitioned at the same observation
   boundary and the holdout never enters inference.
6. Existing cached prediction behavior, model result contract, and propagation
   path rendering remain compatible.

## Non-Goals

- No model retraining, calibration claim, or new forecast horizon.
- No manipulation of imported event timestamps in this change. Timestamp
  quality remains separately auditable.
- No rank/heat metric or borrowed visual semantics from third-party products.
