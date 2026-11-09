// Render a scene to numbered JPEG frames at exact times.
//
//   node tools/render.mjs <url> <outdir> [fps=60] [end=10] [hold=0] [w=1920] [h=1080] [stageId=stage]
//
// Screen-recording a browser drops frames and catches whatever else is on the screen. This drives
// headless Chromium over its DevTools socket instead: it opens the scene, calls
// briefStages.seek(stageId, t) for each frame, and captures. Frame n is t = n / fps and nothing
// else. The last `hold` seconds repeat the final frame. Node's own WebSocket; no packages.
//
// A frame already on disk is skipped, so a render killed halfway resumes where it stopped.
//
//   --loop          write exactly end * fps frames and no hold: in a looping scene the frame at
//                   `end` is frame zero, and writing it too stutters the seam by one frame
//   --preroll <s>   step the clock from -s up to 0 first, so CSS transitions wound to t have
//                   settled before frame zero
//
// Then:  ffmpeg -framerate <fps> -i <outdir>/f%05d.jpg -c:v libx264 -pix_fmt yuv420p -crf 16 out.mp4
// Last line of output is JSON: {"ok", "wrote", "frames", "skipped", "problems"}.

import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { findBrowser } from './browser.mjs';

const argv = process.argv.slice(2);
const loop = argv.includes('--loop');
const preIdx = argv.indexOf('--preroll');
const preroll = preIdx < 0 ? 0 : +argv[preIdx + 1];
// preIdx is -1 when --preroll is absent, and -1 + 1 is 0: guard it, or the URL itself is dropped
const positional = argv.filter((a, i) => a !== '--loop' && (preIdx < 0 || (i !== preIdx && i !== preIdx + 1)));
const [url, outdir = 'frames', fps = '60', end = '10', hold = '0', w = '1920', h = '1080', stageId = 'stage'] = positional;
if (!url) {
  console.error('usage: node tools/render.mjs <url> <outdir> [fps] [end] [hold] [w] [h] [stageId]');
  console.log(JSON.stringify({ ok: false, wrote: [], problems: ['no url given'] }));
  process.exit(2);
}
const port = 9300 + Math.floor(Math.random() * 500);
const profile = mkdtempSync(join(tmpdir(), 'render-'));
mkdirSync(outdir, { recursive: true });

const chrome = spawn(findBrowser(), [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`, `--window-size=${w},${h}`, 'about:blank'], { stdio: 'ignore' });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function devtools(path, method = 'GET') {
  for (let i = 0; i < 100; i++) {
    try { return await (await fetch(`http://127.0.0.1:${port}${path}`, { method })).json(); }
    catch { await sleep(200); }
  }
  throw new Error('the browser never opened its DevTools port');
}

let code = 0;
try {
  const target = await devtools(`/json/new?${encodeURIComponent('about:blank')}`, 'PUT');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  const pending = new Map();
  let seq = 0;
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  const send = (method, params = {}) => new Promise((res, rej) => {
    const id = ++seq;
    pending.set(id, (m) => (m.error ? rej(new Error(`${method}: ${m.error.message}`)) : res(m.result)));
    ws.send(JSON.stringify({ id, method, params }));
  });
  const js = async (expr) => (await send('Runtime.evaluate', { expression: expr, returnByValue: true })).result.value;

  await send('Emulation.setDeviceMetricsOverride', { width: +w, height: +h, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url });
  let ready = false;
  for (let i = 0; i < 100 && !(ready = await js(`document.readyState === 'complete' && !!window.briefStages`)); i++) await sleep(100);
  if (!ready) throw new Error('the scene never exposed window.briefStages (see protocol/contract.md)');
  await sleep(400); // inlined images decode

  for (let t = -preroll; t < 0; t += 1 / +fps) await js(`briefStages.seek(${JSON.stringify(stageId)}, ${t})`);
  const n = loop ? Math.round(+end * +fps) - 1 : Math.round((+end + +hold) * +fps);
  let skipped = 0;
  for (let i = 0; i <= n; i++) {
    const path = join(outdir, `f${String(i).padStart(5, '0')}.jpg`);
    if (existsSync(path)) { skipped++; continue; }
    const t = Math.min(i / +fps, +end);
    if (!(await js(`briefStages.seek(${JSON.stringify(stageId)}, ${t})`))) throw new Error(`seek refused at t=${t}`);
    const shot = await send('Page.captureScreenshot', { format: 'jpeg', quality: 95 });
    writeFileSync(path, Buffer.from(shot.data, 'base64'));
    if (i % 240 === 0) console.error(`frame ${i}/${n}  t=${t.toFixed(2)}s`);
  }
  ws.close();
  console.log(JSON.stringify({ ok: true, wrote: [outdir], frames: n + 1, skipped, problems: [] }));
} catch (e) {
  code = 1;
  console.log(JSON.stringify({ ok: false, wrote: [], problems: [String(e.message || e)] }));
} finally {
  chrome.kill();
  await sleep(300);
  rmSync(profile, { recursive: true, force: true });
}
process.exit(code);
