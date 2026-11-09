// Render a scene to numbered JPEG frames at exact times.
//
//   node tools/render.mjs <url> <outdir> [fps=60] [end=10] [hold=0] [w=1920] [h=1080] [stageId=stage]
//
// Screen-recording a browser drops frames and catches whatever else is on the screen. This opens the
// scene in headless Chromium and calls briefStages.seek(stageId, t) before each capture, so frame n
// is t = n / fps and nothing else. The last `hold` seconds repeat the final frame.
//
// A frame already on disk is skipped, so a render killed halfway resumes where it stopped.
//
//   --loop          write exactly end * fps frames and no hold: in a looping scene the frame at
//                   `end` is frame zero, and writing it too stutters the seam by one frame
//   --preroll <s>   step the clock from -s up to 0 first, so CSS transitions wound to t have
//                   settled before frame zero
//
// Frames n of a long film can be split across processes with tools/slices.mjs.
// Then:  ffmpeg -framerate <fps> -i <outdir>/f%05d.jpg -c:v libx264 -pix_fmt yuv420p -crf 16 out.mp4

import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { open, report } from './cdp.mjs';
import { checkRenderSpace } from './render_budget.mjs';

const argv = process.argv.slice(2);
const loop = argv.includes('--loop');
const preIdx = argv.indexOf('--preroll');
const preroll = preIdx < 0 ? 0 : +argv[preIdx + 1];
// preIdx is -1 when --preroll is absent, and -1 + 1 is 0: guard it, or the URL itself is dropped
const positional = argv.filter((a, i) => a !== '--loop' && (preIdx < 0 || (i !== preIdx && i !== preIdx + 1)));
const [url, outdir = 'frames', fps = '60', end = '10', hold = '0', w = '1920', h = '1080', stageId = 'stage'] = positional;
if (!url) {
  console.error('usage: node tools/render.mjs <url> <outdir> [fps] [end] [hold] [w] [h] [stageId]');
  report({ ok: false, problems: ['no url given'] });
  process.exit(2);
}

let b;
try {
  mkdirSync(outdir, { recursive: true });
  checkRenderSpace(outdir);
  b = await open({ w, h });
  if (!(await b.goto(url, 'document.readyState === "complete" && !!window.briefStages')))
    throw new Error('the scene never exposed window.briefStages (see protocol/contract.md)');
  const seek = (t) => b.js(`briefStages.seek(${JSON.stringify(stageId)}, ${t})`);
  for (let t = -preroll; t < 0; t += 1 / +fps) await seek(t);
  const n = loop ? Math.round(+end * +fps) - 1 : Math.round((+end + +hold) * +fps);
  let skipped = 0;
  for (let i = 0; i <= n; i++) {
    const path = join(outdir, `f${String(i).padStart(5, '0')}.jpg`);
    if (existsSync(path)) { skipped++; continue; }
    const t = Math.min(i / +fps, +end);
    if (!(await seek(t))) throw new Error(`seek refused at t=${t}`);
    writeFileSync(path, await b.shot());
    if (i % 240 === 0) console.error(`frame ${i}/${n}  t=${t.toFixed(2)}s`);
  }
  report({ wrote: [outdir], frames: n + 1, skipped });
} catch (e) {
  report({ ok: false, problems: [String(e.message || e)] });
  process.exitCode = 1;
} finally {
  if (b) await b.close();
}
