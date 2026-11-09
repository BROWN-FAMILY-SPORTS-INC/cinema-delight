// Render frames [from, to) of a scene, in a browser of its own, so a long film renders in parallel.
//
//   node tools/slices.mjs <url> <outdir> <fps> <end> <from> <to> [w=1920] [h=1080] [stageId=stage]
//
// Run several side by side, each with its own range of the same outdir. Frame n is t = n / fps,
// clamped to `end`. A frame already on disk is skipped, so a slice that dies can simply be run again.
// A browser error restarts the browser and retries the frame, twice. Long renders in one browser do
// crash, and a pipe into `tail` hides it; read this tool's JSON line rather than its log.
//
// CINEMA_FRAME_SCALE=0.5 keeps the scene's full layout but stores smaller frames, for a cheap timing
// check. Leave it unset for anything a person will judge.

import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { open, report } from './cdp.mjs';
import { checkRenderSpace } from './render_budget.mjs';

const [url, outdir, fps, end, from, to, w = '1920', h = '1080', stageId = 'stage'] = process.argv.slice(2);
if (!to) {
  console.error('usage: node tools/slices.mjs <url> <outdir> <fps> <end> <from> <to> [w] [h] [stageId]');
  report({ ok: false, problems: ['missing arguments'] });
  process.exit(2);
}
const scale = process.env.CINEMA_FRAME_SCALE === undefined ? 1 : Number(process.env.CINEMA_FRAME_SCALE);
if (!Number.isFinite(scale) || scale <= 0 || scale > 1) {
  report({ ok: false, problems: ['CINEMA_FRAME_SCALE must be above 0 and at most 1'] });
  process.exit(2);
}
const params = scale === 1 ? { format: 'jpeg', quality: 95 }
  : { format: 'jpeg', quality: 80, clip: { x: 0, y: 0, width: +w, height: +h, scale } };

async function session() {
  const b = await open({ w, h });
  if (!(await b.goto(url, 'document.readyState === "complete" && !!window.briefStages'))) {
    await b.close();
    throw new Error('the scene never exposed window.briefStages');
  }
  return b;
}

let b, wrote = 0;
try {
  mkdirSync(outdir, { recursive: true });
  checkRenderSpace(outdir);
  b = await session();
  for (let i = +from; i < +to; i++) {
    const f = join(outdir, `f${String(i).padStart(5, '0')}.jpg`);
    if (existsSync(f)) continue;
    const t = Math.min(i / +fps, +end);
    for (let attempt = 0; ; attempt++) {
      try {
        if (!(await b.js(`briefStages.seek(${JSON.stringify(stageId)}, ${t})`))) throw new Error(`seek refused at t=${t}`);
        writeFileSync(f, await b.shot(params));
        wrote++;
        break;
      } catch (err) {
        console.error(`frame ${i} t=${t.toFixed(3)} failed (${err.message}); restarting the browser`);
        await b.close();
        if (attempt >= 2) throw err;
        b = await session();
      }
    }
  }
  report({ wrote: [outdir], frames: wrote, range: [+from, +to] });
} catch (e) {
  report({ ok: false, problems: [String(e.message || e)], range: [+from, +to] });
  process.exitCode = 1;
} finally {
  if (b) await b.close();
}
