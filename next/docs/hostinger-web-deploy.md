# Hostinger Web Hosting — Deploy (frontend-next)

Static deployment only. NO Node.js required on Hostinger (shared hosting, not VPS).

## 1. Build locally

```bash
cd ~/Projects/SaKgaZe-Next/workspace/frontend-next
npm install           # once
npm run build         # -> dist/
```

A ready-made copy of the last good build lives at
`~/Projects/SaKgaZe-Next/builds/frontend-next-dist/` — deploy from there if the
workspace is not at hand.

## 2. Upload contents (NOT the folder itself)

Hostinger → hPanel → File Manager (or FTP/SFTP client):

1. Navigate to `public_html/`
2. Remove the legacy static files it currently serve (old `index.html`, `app.js`,
   `style.css`, `assets/`) — keep any server-side redirects you added on purpose
   (`.htaccess` with custom rules is NOT part of the frontend build).
3. Upload the CONTENTS of `dist/` (the `assets/` folder, `index.html`,
   `logo-sakgaze.png`, ...) directly into `public_html/`.

The final production layout must be:

```
public_html/
├── index.html
├── logo-sakgaze.png
└── assets/
    └── ... (hashed JS/CSS chunks + logo copy)
```

Never ship a `.env` file. The API base URL is baked at build time from
`VITE_API_BASE_URL`, so no runtime configuration is needed on the server.

## 3. Cache control (recommended)

Add to (or create) `public_html/.htaccess`:

```apache
# Long cache for hashed assets — they change name when content changes.
<IfModule mod_expires.c>
  ExpiresActive On
  <FilesMatch "\.assets/.*\.">
  ExpiresDefault "access plus 1 year"
</FilesMatch>
</IfModule>
```

Simpler correct variant if you prefer:

```apache
<IfModule mod_headers.c>
  <FilesMatch "\.(js|css|png|woff2)$">
    Header set Cache-Control "public, max-age=31536000, immutable"
  </FilesMatch>
</IfModule>
```

`index.html` itself must NOT be long-cached (it references new hashed filenames).

## 4. Verify after upload

- Open https://sakgaze.com — the map renders fullscreen.
- Header shows the real SaKgaZé logo; FR is default; EN switch works live (no reload).
- DevTools console shows no fatal errors; network shows requests going to
  `VITE_API_BASE_URL` (currently the legacy `https://sakgaze-api.onrender.com/api/v1`).
- If the backend is asleep, the UI shows "Connecting to data… / Le service se
  réveille…" and a manual "Réessayer / Retry" button after the auto-retry window.

## 5. Rollback

`public_html/` is overwritten in place. Keep a zip of the previously deployed
build in `workspace/archives/` before a new upload (e.g. `dist-2026-10-03.zip`).

## 6. Future backend migration

Uploading a new dist with a different `VITE_API_BASE_URL` (new Render backend +
new Supabase) is the ONLY change required, provided the API contract stays
compatible. See `backend-migration-next.md`.
