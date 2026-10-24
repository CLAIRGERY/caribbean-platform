#!/usr/bin/env node
/**
 * SaKgaZé Next — static smoke test against a running server.
 * Verifies: #root markup, JS + CSS bundles resolve with real content, logo present.
 * Usage: node scripts/smoke.mjs [baseURL]   (default http://localhost:5173/)
 * Exit 0 only when every check passes.
 */
const baseURL = process.argv[2] || 'http://localhost:5173/'
let failures = 0

function check(name, ok, detail) {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` (${detail})` : ''}`)
  if (!ok) failures++
}

const htmlResp = await fetch(baseURL)
const html = await htmlResp.text()
check('index reachable', htmlResp.ok, String(htmlResp.status))
check('contains #root', html.includes('<div id="root"></div>'))

const jsTag = html.match(/src="([^"]+\.js)"/)
if (jsTag) {
  const jsResp = await fetch(new URL(jsTag[1], baseURL))
  const jsBody = await jsResp.text()
  check('JS bundle', jsResp.ok && jsBody.length > 1000, `${jsResp.status} ${jsBody.length}b`)
} else {
  check('JS bundle tag', false, 'missing')
}

const cssTag = html.match(/href="([^"]+\.css)"/)
if (cssTag) {
  const cssResp = await fetch(new URL(cssTag[1], baseURL))
  const cssBody = await cssResp.text()
  check('CSS', cssResp.ok && cssBody.length > 100, `${cssResp.status} ${cssBody.length}b`)
} else {
  check('CSS tag', false, 'missing')
}

const logoResp = await fetch(new URL('/logo-sakgaze.png', baseURL))
check('logo', logoResp.ok, String(logoResp.status))

console.log(failures === 0 ? 'SMOKE OK' : `SMOKE FAIL (${failures})`)
process.exit(failures === 0 ? 0 : 1)
