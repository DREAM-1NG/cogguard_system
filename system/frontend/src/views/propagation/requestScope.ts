export type PropagationAnalysisRequestScope = {
  eventId: string
  platform: string
  nodeLimit: number
  fullViewRequested: boolean
}

export type PropagationAlertsRequestScope = {
  eventId: string
  platform: string
}

export type PropagationAnalysisScopeInput = {
  eventId: string
  platform: string
  diffusionNodeLimit: number
  diffusionFullViewRequested: boolean
  defaultNodeLimit: number
}

export type PropagationAnalysisRequestParams = {
  event_id?: string
  platform?: string
  node_limit: number
  first_layer_limit?: number
  second_layer_limit?: number
}

export type PropagationAlertsRequestParams = {
  event_id: string
  platform?: string
}

type SameScope<TScope> = (left: TScope, right: TScope) => boolean

export function createPropagationAnalysisScope(input: PropagationAnalysisScopeInput): PropagationAnalysisRequestScope {
  const nodeLimit = input.diffusionFullViewRequested
    ? 0
    : Math.max(1, Math.floor(Number(input.diffusionNodeLimit) || input.defaultNodeLimit))
  return {
    eventId: input.eventId.trim(),
    platform: input.platform.trim(),
    nodeLimit,
    fullViewRequested: input.diffusionFullViewRequested,
  }
}

export function createPropagationAlertsScope(input: PropagationAlertsRequestScope): PropagationAlertsRequestScope {
  return {
    eventId: input.eventId.trim(),
    platform: input.platform.trim(),
  }
}

export function analysisRequestParamsFromScope(scope: PropagationAnalysisRequestScope): PropagationAnalysisRequestParams {
  const params: PropagationAnalysisRequestParams = {
    node_limit: scope.nodeLimit,
  }
  if (scope.eventId) {
    params.event_id = scope.eventId
  }
  if (scope.platform) {
    params.platform = scope.platform
  }
  if (!scope.fullViewRequested) {
    params.first_layer_limit = 40
    params.second_layer_limit = 80
  }
  return params
}

export function alertsRequestParamsFromScope(scope: PropagationAlertsRequestScope): PropagationAlertsRequestParams {
  return {
    event_id: scope.eventId,
    platform: scope.platform || undefined,
  }
}

export function samePropagationAnalysisScope(
  left: PropagationAnalysisRequestScope,
  right: PropagationAnalysisRequestScope,
): boolean {
  return left.eventId === right.eventId
    && left.platform === right.platform
    && left.nodeLimit === right.nodeLimit
    && left.fullViewRequested === right.fullViewRequested
}

export function samePropagationAlertsScope(
  left: PropagationAlertsRequestScope,
  right: PropagationAlertsRequestScope,
): boolean {
  return left.eventId === right.eventId
    && left.platform === right.platform
}

export function acceptPropagationScopedResponse<TScope>(input: {
  requestGeneration: number
  currentGeneration: number
  requestedScope: TScope
  currentScope: TScope
  sameScope: SameScope<TScope>
}): boolean {
  return input.requestGeneration === input.currentGeneration
    && input.sameScope(input.requestedScope, input.currentScope)
}
