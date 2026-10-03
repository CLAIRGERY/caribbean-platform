import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import {
  fetchDetections,
  fetchDrift,
  fetchMarineAlerts,
  fetchIngestionStatus,
  API_BASE_URL,
} from '../lib/api'
import type { FeatureCollection, IngestionStatus } from '../types/geo'

/**
 * Render free dynos sleep; responses can 503 or hang.
 * Policy: auto retry with 2s / 5s / 10s gaps, then surface a manual retry state.
 * No infinite auto-retry loop.
 */
export const COLD_START_DELAYS_MS = [2_000, 5_000, 10_000] as const

export async function withColdStartRetry<T>(fn: () => Promise<T>): Promise<T> {
  let lastErr: unknown
  for (let i = 0; i <= COLD_START_DELAYS_MS.length; i++) {
    try {
      return await fn()
    } catch (err) {
      lastErr = err
      if (i === COLD_START_DELAYS_MS.length) break
      const status = (err as { status?: number })?.status
      // Retry only transport/availability issues; hard 4xx will not heal.
      if (status !== undefined && status !== 429 && status < 500) throw err
      await new Promise((r) => setTimeout(r, COLD_START_DELAYS_MS[i]))
    }
  }
  throw lastErr
}

type FC = FeatureCollection<Record<string, unknown>>

export function useDetections(): UseQueryResult<FC> {
  return useQuery<FC>({
    queryKey: ['detections'],
    queryFn: () => withColdStartRetry(fetchDetections),
    staleTime: 10 * 60_000,
    refetchInterval: 10 * 60_000,
    refetchOnWindowFocus: false,
  })
}

export function useDrift(): UseQueryResult<FC> {
  return useQuery<FC>({
    queryKey: ['drift'],
    queryFn: () => withColdStartRetry(fetchDrift),
    staleTime: 10 * 60_000,
    refetchInterval: 10 * 60_000,
    refetchOnWindowFocus: false,
  })
}

export function useMarineAlerts(): UseQueryResult<FC> {
  return useQuery<FC>({
    queryKey: ['marine'],
    queryFn: () => withColdStartRetry(fetchMarineAlerts),
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
    refetchOnWindowFocus: false,
  })
}

export function useIngestionStatus(): UseQueryResult<IngestionStatus> {
  return useQuery<IngestionStatus>({
    queryKey: ['ingestion-status'],
    queryFn: () => withColdStartRetry(fetchIngestionStatus),
    staleTime: 3 * 60_000,
    refetchInterval: 3 * 60_000,
    refetchOnWindowFocus: false,
  })
}

export { API_BASE_URL }
