// Drive a headless Chromium over its DevTools socket. Every browser tool here is built on this.
//
//   import { open } from './cdp.mjs';
//   const b = await open({ w: 1920, h: 1080 });
//   await b.goto(url, 'document.readyState === "complete" && !!window.briefStages');
//   const v = await b.js('1 + 1');
//   const jpeg = await b.shot({ format: 'jpeg', quality: 95 });
//   await b.close();
//
// Node's own fetch and WebSocket; no packages. The browser is $CHROME, else the first of chromium,
// chromium-browser, google-chrome-stable, google-chrome on PATH. Each browser runs in its own process
// group with a throwaway profile, and both are removed when the tool exits, however it exits: a
// headless browser left behind keeps its memory and its profile until someone notices.

import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function findBrowser() {
  if (process.env.CHROME) return process.env.CHROME;
  for (const name of ['chromium', 'chromium-browser', 'google-chrome-stable', 'google-chrome']) {
    try { return execFileSync('sh', ['-c', `command -v ${name}`], { encoding: 'utf8' }).trim(); } catch {}
  }
  throw new Error('no Chromium or Chrome found: install one, or set CHROME to its path');
}

const live = new Map();
const reap = (child) => {
  try { process.kill(-child.pid, 'SIGKILL'); } catch {}
  try { rmSync(live.get(child), { recursive: true, force: true }); } catch {}
  live.delete(child);
};
process.on('exit', () => { for (const c of [...live.keys()]) reap(c); });
for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(sig, () => process.exit(1));

export async function open({ w = 1920, h = 1080, timeoutMs = 60000, gesture = false } = {}) {
  const port = 9300 + Math.floor(Math.random() * 600);
  const profile = mkdtempSync(join(tmpdir(), 'cdp-'));
  const child = spawn(findBrowser(), ['--headless=new', '--disable-gpu', '--disable-dev-shm-usage', '--hide-scrollbars', '--no-first-run',
    '--autoplay-policy=no-user-gesture-required', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    `--window-size=${w},${h}`, 'about:blank'], { stdio: 'ignore', detached: true });
  live.set(child, profile);
  let target;
  for (let i = 0; i < 100 && !target; i++) {
    try { target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json(); }
    catch { await sleep(200); }
  }
  if (!target) { reap(child); throw new Error('the browser never opened its DevTools port'); }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  const pending = new Map(); let seq = 0;
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  const send = (method, params = {}) => new Promise((res, rej) => {
    const id = ++seq;
    const timer = setTimeout(() => rej(new Error(`${method}: no answer in ${timeoutMs / 1000} s`)), timeoutMs);
    pending.set(id, (m) => { clearTimeout(timer); m.error ? rej(new Error(`${method}: ${m.error.message}`)) : res(m.result); });
    ws.send(JSON.stringify({ id, method, params }));
  });
  // Evaluate an expression; promises are awaited. A thrown error in the page is thrown here.
  const js = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true, userGesture: gesture });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  await send('Emulation.setDeviceMetricsOverride', { width: +w, height: +h, deviceScaleFactor: 1, mobile: false });
  return {
    send, js,
    // Navigate, then wait until `ready` is true (or `limitS` passes). Answers whether it got ready.
    async goto(url, ready = 'document.readyState === "complete"', limitS = 30) {
      await send('Page.navigate', { url });
      const t0 = Date.now();
      while (Date.now() - t0 < limitS * 1000) {
        if (await js(ready).catch(() => false)) { await sleep(300); return true; }
        await sleep(100);
      }
      return false;
    },
    async shot(params = { format: 'jpeg', quality: 95 }) {
      return Buffer.from((await send('Page.captureScreenshot', params)).data, 'base64');
    },
    async close() { try { ws.close(); } catch {} reap(child); },
  };
}

// The one line every tool ends with.
export function report(fields) { console.log(JSON.stringify({ ok: true, wrote: [], problems: [], ...fields })); }
