import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type LayerKey = 'sargassum' | 'drift' | 'marine'
export type ToggleKey = LayerKey | 'satelliteBasemap' | 'oceanFlow'

interface LayersState {
  sargassum: boolean
  drift: boolean
  marine: boolean
  satelliteBasemap: boolean
  oceanFlow: boolean
  toggle: (key: ToggleKey) => void
}

export const useLayers = create<LayersState>()(
  persist(
    (set) => ({
      sargassum: true,
      drift: true,
      marine: true,
      satelliteBasemap: true,
      oceanFlow: false,
      toggle: (key) =>
        set((s) => {
          switch (key) {
            case 'sargassum':
              return { sargassum: !s.sargassum }
            case 'drift':
              return { drift: !s.drift }
            case 'marine':
              return { marine: !s.marine }
            case 'satelliteBasemap':
              return { satelliteBasemap: !s.satelliteBasemap }
            case 'oceanFlow':
              return { oceanFlow: !s.oceanFlow }
          }
        }),
    }),
    { name: 'sakgaze.layers' },
  ),
)

export type Selection = {
  kind: LayerKey
  id: string
  props: Record<string, unknown>
}

interface SelectionState {
  selection: Selection | null
  select: (s: Selection) => void
  clear: () => void
}

export const useSelection = create<SelectionState>((set) => ({
  selection: null,
  select: (selection) => set({ selection }),
  clear: () => set({ selection: null }),
}))

export interface TimelineRange {
  /** Real epoch ms; from/to null = no filter */
  from: number | null
  to: number | null
}

interface TimelineState {
  range: TimelineRange
  setRange: (r: TimelineRange) => void
  reset: () => void
}

export const useTimeline = create<TimelineState>((set) => ({
  range: { from: null, to: null },
  setRange: (range) => set({ range }),
  reset: () => set({ range: { from: null, to: null } }),
}))

interface UIState {
  mobileMenuOpen: boolean
  setMobileMenuOpen: (v: boolean) => void
}

export const useUI = create<UIState>((set) => ({
  mobileMenuOpen: false,
  setMobileMenuOpen: (v) => set({ mobileMenuOpen: v }),
}))
