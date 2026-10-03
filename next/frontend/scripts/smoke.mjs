#!/usr/bin/env node
/**
 * Static sanity check of the built SaKgaZe frontend.
 * Verifies: #root markup, referenced JS/CSS bundles resolve, logo present.
 * Usage: node scripts/smoke.mjs http://localhost:5173/
 */
const url = process.argv[2] || 'http://localhost:5173/'

const html = await (await fetch(url)).text()
if (!html.includes('<div id="root"></div>')) {
  console.error('FAIL: missing #root mount point')
  process.exit(1)
}
console.log('HTML: OK, contains #root')

const js = html.match(/src="([^"]+\.js)"/)
if (!js) {
  console.error('FAIL: no bundle script tag')
  process.exit(1)
}
const jsResp = await fetch(new URL(js[1], url))
console.log('JS bundle:', jsResp.status, jsResp.headers.get('content-length'), 'bytes')
if (!jsResp.ok) process.exit(1)

const css = html.match(/href="([^"]+\.css)"/)
if (css) {
  const cssResp = await fetch(new URL(css[1], url))
  console.log('CSS:', cssResp.status, cssResp.headers.get('content-length'), 'bytes')
  if (!cssResp.ok) process.exit(1)
}

const logoResp = await fetch(new URL('/logo-sakgaze.png', url))
console.log('Logo:', logoResp.status, logoResp.headers.get('content-length'), 'bytes')
if (!logoResp.ok) process.exit(1)

console.log('SMOKE OK (static layer)')
