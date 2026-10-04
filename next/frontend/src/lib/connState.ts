/**
 * Connection state machine for the SaKgaZé backend.
 * States: CONNECTING → WAKING (retrying after Render cold sleep) → LIVE | DEGRADED | OFFLINE
 */
export type ConnState = 'connecting' | 'waking' | 'live' | 'degraded' | 'offline'

export function deriveConnState(
  successCount: number,
  errorCount: number,
  total: number,
  healthOk: boolean | null = null,
): ConnState {
  if (healthOk === false && errorCount >= total) return 'offline'
  if (healthOk === false) return 'degraded'
  if (errorCount === total) return 'offline'
  if (healthOk === true && errorCount > 0) return 'degraded'
  if (errorCount > 0) return 'degraded'
  if (successCount === total) return 'live'
  return 'connecting'
}

export function stateAttemptLabel(attempt: number): ConnState {
  return attempt === 0 ? 'connecting' : 'waking'
}
