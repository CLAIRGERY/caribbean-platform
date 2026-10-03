/**
 * Connection state machine for the SaKgaZé backend.
 * States: CONNECTING → WAKING (retrying after Render cold sleep) → LIVE | DEGRADED | OFFLINE
 */
export type ConnState = 'connecting' | 'waking' | 'live' | 'degraded' | 'offline'

import type { UseQueryResult } from '@tanstack/react-query'

export function deriveConnState(
  queries: Pick<UseQueryResult<unknown>, 'isPending'>[],
  successCount: number,
  errorCount: number,
): ConnState {
  const total = queries.length
  if (errorCount === total) return 'offline'
  if (errorCount > 0) return 'degraded'
  if (successCount === total) return 'live'
  return 'connecting'
}

export function stateAttemptLabel(attempt: number): ConnState {
  return attempt === 0 ? 'connecting' : 'waking'
}
