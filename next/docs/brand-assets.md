# SaKgaZé — Brand assets

Only ONE genuine brand asset was recoverable from the repository (plus git history).

## logo-sakgaze.png (source of truth)

- **Source path (repo)**: `frontend/assets/logo-sakgaze.png` (branch `feature/sakgaze-next`)
- **Git history**: present since the first appearance of `frontend/assets/`; no earlier
  versions and no other logo image across all commits/branches.
- **Type**: PNG, 2055 × 1533 px, 8-bit RGBA, non-interlaced, 4 551 404 bytes.
- **Legacy usage**: favicon, loading-overlay hero, sidebar/header avatar
  (`rounded-full` → the mark reads as a circle inside a square canvas; keep it as-is,
  do not re-crop).
- **Preserved original**: `workspace/archives/brand/logo-sakgaze-original-2055x1533.png`
  (byte-identical copy, never re-encoded) and the untouched repo file above.

## Optimized derivatives (2026-10-24)

A 4.5 MB logo shipped on every page load was the single largest front-end asset —
larger than React, MapLibre and the app bundle combined. Derivatives were generated
with macOS `sips` (Lanczos resize, alpha preserved, no colour shift):

| file | size | dimensions | used for |
|---|---|---|---|
| `frontend-next/src/assets/brand/logo-sakgaze-512.png` | 314 KB | 512 px | header mark, About dialog, intro |
| `frontend-next/src/assets/brand/logo-sakgaze-128.png` | 24 KB | 128 px | compact contexts |
| `frontend-next/public/logo-sakgaze.png` | 24 KB | 128 px | `apple-touch-icon` |
| `frontend-next/public/favicon-96.png` | 14 KB | 96 px | `<link rel="icon">` |

Effect measured on the production build: the imported brand asset dropped from
**4 551 KB to 314 KB** (−93 %) in `dist/assets/`.

## No other assets exist

- No `.svg`, `.webp`, `.ico` or `.jpg` brand variants, no `favicon.ico` in history.
- No bundled fonts: the UI uses Google Fonts (Space Grotesk + Inter) with a system
  fallback stack; self-host under `public/fonts/` if offline use matters.

## Usage rules

- Do NOT invent or redraw a logo: the recovered PNG is the only authentic mark.
- Do NOT re-encode the source PNG (no lossy recompression, no colour shift).
- Circular crop (`rounded-full`) matches the legacy presentation; pair it with the
  midnight-glass surfaces and a thin cyan ring (`ring-cyan-200/25`).
- Any new derivative must be documented in this table with its purpose.
