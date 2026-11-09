// Stills of a scene at chosen seconds, in one browser, then a labelled contact sheet.
//
//   node tools/stills.mjs <url> <outdir> <s1> <s2> ... [--cols 6] [--w 360] [--size 1920x1080]
//   node tools/stills.mjs <url> <outdir> --sweep <end> [--step 0.5]
//
// The contact sheet is how an agent watches a film: read the sheet first, then open at full size only
// the frames that look wrong. It catches a solid bar where a line was meant, a thing that runs off the
// frame, a title sitting on the subject, words over words.
//
// Writes <outdir>/s_<second>.jpg and <outdir>/sheet.jpg (ffmpeg tiles them, each labelled with its
// second). --sweep seeks every step to the end and reports any second whose draw throws, without
// writing pictures. One browser for every still: tools/still.sh fires before a scene that draws
// asynchronously has finished.

import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync, readdirSync, unlinkSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { open, report } from './cdp.mjs';

const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(k); if (i < 0) return d; const v = argv[i + 1]; argv.splice(i, 2); return v; };
const cols = +opt('--cols', 6), tw = +opt('--w', 360), sweep = opt('--sweep', null), step = +opt('--step', 0.5);
const stageId = opt('--stage', 'stage');
const [VW, VH] = opt('--size', '1920x1080').split('x').map(Number);
const [url, outdir, ...secs] = argv;
if (sweep != null) for (let s = 0; s < +sweep; s += step) secs.push(String(+s.toFixed(3)));
if (!url || !outdir || !secs.length) {
  console.error('usage: node tools/stills.mjs <url> <outdir> <s1> <s2> ... [--cols 6] [--w 360] [--size WxH]');
  report({ ok: false, problems: ['missing arguments'] });
  process.exit(2);
}
mkdirSync(outdir, { recursive: true });
for (const f of readdirSync(outdir)) if (f.startsWith('s_') || f === 'sheet.jpg') unlinkSync(join(outdir, f));

const b = await open({ w: VW, h: VH });
const shots = [], thrown = [];
try {
  if (!(await b.goto(url, 'document.readyState === "complete" && !!window.briefStages')))
    throw new Error('the scene never exposed window.briefStages');
  for (const s of secs) {
    try { await b.js(`briefStages.seek(${JSON.stringify(stageId)}, ${+s})`); }
    catch (e) { thrown.push({ second: +s, error: String(e.message).split('\n').slice(0, 2).join(' | ') }); }
    if (sweep != null) continue;
    const f = join(outdir, `s_${String((+s).toFixed(3)).padStart(9, '0')}.jpg`);
    writeFileSync(f, await b.shot({ format: 'jpeg', quality: 92 }));
    shots.push([f, s]);
  }
} catch (e) {
  await b.close();
  report({ ok: false, problems: [String(e.message || e)] });
  process.exit(1);
}
await b.close();
if (sweep != null) {
  report({ ok: !thrown.length, problems: thrown, checked: secs.length });
  process.exit(thrown.length ? 1 : 0);
}
const lab = join(outdir, 'lab'); mkdirSync(lab, { recursive: true });
shots.forEach(([f, s], i) => spawnSync('ffmpeg', ['-v', 'error', '-y', '-i', f, '-vf',
  `scale=${tw}:-1,drawtext=text='${s}':x=8:y=8:fontcolor=white:fontsize=20:box=1:boxcolor=black@0.6`,
  join(lab, `g_${String(i).padStart(3, '0')}.jpg`)]));
spawnSync('ffmpeg', ['-v', 'error', '-y', '-pattern_type', 'glob', '-i', join(lab, 'g_*.jpg'), '-vf',
  `tile=${Math.min(cols, shots.length)}x${Math.ceil(shots.length / cols)}:color=black`, join(outdir, 'sheet.jpg')]);
rmSync(lab, { recursive: true, force: true });
report({ ok: !thrown.length, wrote: [join(outdir, 'sheet.jpg'), ...shots.map(([f]) => f)], problems: thrown });
