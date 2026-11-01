export type AccountTarget = {
  platform: string
  accountId: string
}

export type AccountIdentity = {
  platform?: unknown
  account_id?: unknown
}

function normalizedValue(value: unknown): string {
  return String(value || '').trim()
}

export function accountSelectionKey(target: AccountTarget): string {
  return `${normalizedValue(target.platform).toLowerCase() || 'unknown'}::${normalizedValue(target.accountId)}`
}

export function accountTargetFromProfile(profile: AccountIdentity | null | undefined): AccountTarget | null {
  const platform = normalizedValue(profile?.platform).toLowerCase()
  const accountId = normalizedValue(profile?.account_id)
  return platform && accountId ? { platform, accountId } : null
}

export function sameAccountTarget(left: AccountTarget | null, right: AccountTarget | null): boolean {
  return Boolean(left && right && accountSelectionKey(left) === accountSelectionKey(right))
}

export function resolveAccountSelection<T extends AccountIdentity>(
  profiles: T[],
  requested: AccountTarget | null,
): AccountTarget | null {
  if (requested && profiles.some((profile) => sameAccountTarget(accountTargetFromProfile(profile), requested))) {
    return requested
  }
  return accountTargetFromProfile(profiles[0])
}

export function acceptAccountDetailResponse({
  requestGeneration,
  currentGeneration,
  requested,
  current,
}: {
  requestGeneration: number
  currentGeneration: number
  requested: AccountTarget
  current: AccountTarget | null
}): boolean {
  return requestGeneration === currentGeneration && sameAccountTarget(requested, current)
}
