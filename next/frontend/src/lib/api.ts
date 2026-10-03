/**
 * Central API layer. Every network call goes through here.
 * Base URL = VITE_API_BASE_URL (decoupled from infrastructure).
 */

import type { FeatureCollection, IngestionStatus } from '../types/geo'

const RAW_BASE = import.meta.env.VITE_API_BASE_URL as string | undefined
export const API_BASE_URL: string =
  RAW_BASE && RAW_BASE.trim().length > 0 ? RAW_BASE : 'https://sakgaze-api.onrender.com/api/v1'

export class ApiError extends Error {
  status?: number
  constructor(message: string, status?: number) {
    super(message)
    this.status = status
  }
}

function isFeatureCollection(v: unknown): v is FeatureCollection<Record<string, unknown>> {
  return (
    typeof v === 'object' &&
    v !== null &&
    (v as { type?: unknown }).type === 'FeatureCollection' &&
    Array.isArray((v as { features?: unknown }).features)
  )
}

async function request<T>(path: string, timeoutMs = 45_000): Promise<T> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const resp = await fetch(`${API_BASE_URL}${path}`, { signal: ctrl.signal })
    if (!resp.ok) throw new ApiError(`HTTP ${resp.status}`, resp.status)
    const data: unknown = await resp.json()
    return data as T
  } catch (err) {
    if (err instanceof ApiError) throw err
    // Abort / network failure
    throw new ApiError((err as Error)?.message || 'network-error')
  } finally {
    clearTimeout(timer)
  }
}

export function fetchHealth(): Promise<{ status?: string }> {
  return request<{ status?: string }>('/health', 20_000)
}

export async function fetchDetections(): Promise<FeatureCollection<Record<string, unknown>>> {
  const d = await request<FeatureCollection<Record<string, unknown>>>('/sakgaze/detections/latest')
  return isFeatureCollection(d) ? d : { type: 'FeatureCollection', features: [] }
}

export async function fetchDrift(): Promise<FeatureCollection<Record<string, unknown>>> {
  const d = await request<FeatureCollection<Record<string, unknown>>>('/sakgaze/drift-predictions/latest')
  return isFeatureCollection(d) ? d : { type: 'FeatureCollection', features: [] }
}

export async function fetchMarineAlerts(): Promise<FeatureCollection<Record<string, unknown>>> {
  const d = await request<FeatureCollection<Record<string, unknown>>>('/weathernext/marine-alerts/latest')
  return isFeatureCollection(d) ? d : { type: 'FeatureCollection', features: [] }
}

export function fetchIngestionStatus(): Promise<IngestionStatus> {
  return request<IngestionStatus>('/ingestion/status')
}
