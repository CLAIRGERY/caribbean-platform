# ThreeUI Migration — Swap Points

> Real ThreeUI MCP is blocked by an OAuth/Pro entitlement (browser-only sign-in).
> This file records exactly where in-house stand-ins live so real catalog
> components can replace them one-for-one once a Pro token is available.

## Current internal system (src/components/premium.tsx + styles/index.css)

| In-house primitive | File | ThreeUI swap candidate concept |
|---|---|---|
| ThreeGlassPanel | `premium.tsx` | glass surface template |
| FlowBorder | `premium.tsx` | animated / luminous border |
| MarineStatusOrb | `premium.tsx` | animated status orb |
| OceanGlowButton | `premium.tsx` + `.sak-glow-btn` | premium magnetic / glow button |
| DataPulse | `premium.tsx` | data ribbon pulse |
| WaveSeparator | `premium.tsx` | animated separator / hairline |
| BiolumeBadge | `premium.tsx` | biolume badge |
| Instrument toggles | `LayerControl.tsx` + `.sak-toggle` | animated layer toggle |
| Timeline ribbon | `Timeline.tsx` + `.sak-timeline-slider` | scientific timeline ribbon |
| TelemetryStrip | `TelemetryStrip.tsx` | animated data ribbon |
| Minimap overview | `Minimap.tsx` | spatial spotlight / navigation orb |
| Intro scanline | `Intro.tsx` + `.sak-scanline` | spatial spotlight / shader loader |
| OceanFlowGate | `three/OceanFlowGate.tsx` | particle system / flow particles |
| ShaderLayers | `three/ShaderLayers.tsx` | shader backgrounds (OceanAtmosphere + CurrentFlow) |
| Atmosphere overlays | `styles/index.css` (.sak-atmo-*) | WebGL gradient / depth surfaces |
| Inspector panel | `Inspector.tsx` + `.sak-metric/-kicker/-meta` | depth panel / animated typography |
| StatusBanner | `StatusBanner.tsx` | glow card / animated ribbon |
| Satellite scan sweep | `MapStage.tsx` (.sak-scan-sweep) | radial sweep / spotlight |

## Swap procedure (once token available)

1. POST `https://threeui.com/api/mcp` JSON-RPC: `initialize` (protocol 2026-07-28),
   browser OAuth sign-in completes the flow. Tokens accepted only in Authorization header.
2. `tools/list` → discover `search_catalog`, `get_catalog_item`, `get_item_source`, `get_item_prompt`.
3. Pick real components matching each row above; keep prop names before swap:
   - `ThreeGlassPanel({ strong })` — treat as `surface/glass` variant selector
   - `MarineStatusOrb({ state })` — state enum is 5-value (`connecting/waking/live/degraded/offline`)
   - `OceanGlowButton({ glow, active })` — glow is hex token from `OCEAN`
4. Styles in `index.css` tagged `.sak-*` are the fallback; delete on swap.
5. Never stack two glowing surfaces on top of each other — threeui real shaders
   compose better when overlays are removed first.
