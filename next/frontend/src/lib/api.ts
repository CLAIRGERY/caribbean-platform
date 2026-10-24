/**
 * Central API layer. Every network call goes through here.
 * Base URL = VITE_API_BASE_URL (decoupled from infrastructure).
 */

import type { FeatureCollection, IngestionStatus } from '../types/geo'

const RAW_BASE = import.meta.env.VITE_API_BASE_URL as string | undefined
export const API_BASE_URL: string =
  RAW_BASE && RAW_BASE.trim().length > 0 ? RAW_BASE : 'https://sakgaze-api.onrender.com/api/v1'

/**
 * TEST FIXTURES are EXPLICITLY OPT-IN via VITE_USE_TEST_FIXTURES=true.
 * When false (production default), no fixture is ever loaded; requests always
 * go to API_BASE_URL.
 */
export const USE_TEST_FIXTURES: boolean =
  String(import.meta.env.VITE_USE_TEST_FIXTURES ?? 'false').toLowerCase() === 'true'


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
  if (USE_TEST_FIXTURES) {
    const fixture = await loadFixture(path)
    if (fixture !== null) return fixture as T
  }
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

/** Dev only (VITE_USE_TEST_FIXTURES). Returns null when no fixture matches. */
async function loadFixture(path: string): Promise<{ type: 'FeatureCollection'; features: unknown[]; [x: string]: unknown } | { [x: string]: unknown } | null> {
  const map: Record<string, string> = {
    '/sakgaze/detections/latest': 'detections.json',
    '/sakgaze/drift-predictions/latest': 'drift.json',
    '/weathernext/marine-alerts/latest': 'marine.json',
    '/ingestion/status': 'status.json',
  }
  const file = map[path]
  if (!file) return { status: 'fixture' }
  // served via /scripts/fixtures/<file> from the dev/static server
  const r = await fetch(`/scripts/fixtures/${file}`)
  if (!r.ok) return null
  return (await r.json()) as { [x: string]: unknown }
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
