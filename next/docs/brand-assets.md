# SaKgaZé — Brand assets

Only ONE genuine brand asset was recoverable from the repository (plus git history):

## logo-sakgaze.png
- **Source path (repo)**: `frontend/assets/logo-sakgaze.png`
- **Git history**: present since the first appearances of `frontend/assets/` (no earlier versions, no other logo images found — `git log --all --name-only` shows only this single image across all 25 commits / all branches)
- **Type**: PNG image data, 2055 × 1533 px, 8-bit/color RGBA, non-interlaced, 4.5 MB
- **Usage in legacy app**: favicon (`<link rel="icon">`), loading overlay hero image, sidebar + header avatar (CSS `border-radius: 50%` / `rounded-full` class → logo reads as a circle within a square-ish canvas; keep as-is rather than re-cropping)
- **Copies made for frontend-next**:
  - `workspace/frontend-next/src/assets/brand/logo-sakgaze.png` (bundle import + OG/favicon source)
  - `workspace/frontend-next/public/logo-sakgaze.png` (favicon / direct `/logo-sakgaze.png` path references)
- **Original preserved**: yes, untouched in the repo clone at `workspace/caribbean-platform/frontend/assets/logo-sakgaze.png` (branch `feature/sakgaze-next`, no repo files modified)

## No other assets exist
- No `.svg`, `.webp`, `.ico`, `.jpg` variants
- No favicon.ico in repo history
- No fonts bundled (all future fonts must be either system-stack or self-hosted under `frontend-next/public/fonts/`)

## Usage rules for the new frontend
- Do NOT invent a replacement logo. Use `logo-sakgaze.png` for favicon, header mark, loading state.
- Do NOT modify the source PNG (no re-compression that loses alpha, no color shift).
- Display intent: circular crop (rounded-full) matches legacy presentation; pair with the new neutral/midnight glass surfaces.
