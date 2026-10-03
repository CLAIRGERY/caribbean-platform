# SaKgaZé Next — Frontend

Next-generation geospatial intelligence frontend for the SaKgaZé Caribbean sargassum platform.

## Stack
Vite + React 18 + TypeScript (strict) · MapLibre GL JS · Tailwind CSS · Zustand · TanStack Query · Framer Motion · i18next (FR default / EN) · optional lazy Three.js "Ocean Flow" mode.

## Run

```bash
npm install
cp .env.example .env     # then set VITE_API_BASE_URL
npm run dev              # http://localhost:5173
npm run build            # -> dist/
```

## Environment

| Variable             | Purpose                                    | Default                                   |
|----------------------|--------------------------------------------|-------------------------------------------|
| `VITE_API_BASE_URL`  | Backend API base (no URL hardcoded in UI)  | `https://sakgaze-api.onrender.com/api/v1` |

## Architecture

```
src/
  app/            App shell (floating UI over the map)
  components/     Header, LayerControl, Timeline, Inspector, StatusBanner...
  map/            MapLibre engine, layer recipes, inspector bridge
  three/          Optional lazy "Ocean Flow" particle mode
  hooks/          TanStack Query layer hooks (independent retry policies)
  stores/         Zustand (layers, selection, timeline, UI)
  lib/            Central API client (VITE_API_BASE_URL)
  i18n/           fr.json / en.json + init
  styles/         Glass design system + base styles
  types/          GeoJSON / backend contract types
  assets/brand/   REAL SaKgaZé logo (recovered from repo)
```

## Product rules honored
- Map-first: floating UI, never a permanent sidebar squeeze; zero-height-map bug guarded.
- Sargassum / Drift / Marine layers are fully independent (load / fail / retry / empty / toggle).
- Only real timestamps; timeline + inspector show real values only, never fabricated fields.
- Cold start: auto retry 2s/5s/10s on Render 5xx + manual Retry button afterwards.
- Empty database mode: map stays visible with an explanatory empty state.
- FR default, EN toggle, persisted in localStorage; html lang updated live.
- Three.js is optional and lazy; when WebGL fails, app continues normally.
