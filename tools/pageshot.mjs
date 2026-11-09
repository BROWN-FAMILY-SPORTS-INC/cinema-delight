// Screenshot a whole page, or one element of it, in real time, the way a person's browser runs it.
//
//   node tools/pageshot.mjs <url> <out.png> [width=1200] [element id] [timeout seconds=120]
//
// tools/still.sh is for scenes: one draw at ?t= under the browser's virtual time. A page that draws in
// turns, yielding between pictures, stalls under virtual time and gets photographed half drawn, and
// nothing says so. This waits in real time until the page sets `window.PRINTED = true` (or the
// timeout), reports what the page says about itself (an error in html[data-error], horizontal
// overflow, canvases), then captures. Use it to look at review pages before a person does.

import { writeFileSync } from 'node:fs';
import { open, report } from './cdp.mjs';

const [url, out, width = '1200', elementId = '', limit = '120'] = process.argv.slice(2);
if (!url || !out) {
  console.error('usage: node tools/pageshot.mjs <url> <out.png> [width] [element id] [timeout seconds]');
  report({ ok: false, problems: ['missing arguments'] });
  process.exit(2);
}
const b = await open({ w: width, h: 1200, timeoutMs: 120000 });
try {
  const t0 = Date.now();
  const printed = await b.goto(url, 'window.PRINTED === true', +limit);
  const state = await b.js(`({ error: document.documentElement.dataset.error || null,
    canvases: document.querySelectorAll('canvas').length,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth })`);
  let clip;
  if (elementId) {
    const r = await b.js(`(() => { const e = document.getElementById(${JSON.stringify(elementId)}); if (!e) return null;
      const r = e.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height }; })()`);
    if (!r) throw new Error(`no element with id ${elementId}`);
    clip = { x: Math.max(0, r.x - 8), y: Math.max(0, r.y - 8), width: r.w + 16, height: r.h + 16, scale: 1 };
  } else {
    clip = { x: 0, y: 0, width: +width, height: await b.js('document.documentElement.scrollHeight'), scale: 1 };
  }
  writeFileSync(out, await b.shot({ format: 'png', clip, captureBeyondViewport: true }));
  const problems = [];
  if (!printed) problems.push('the page never set window.PRINTED; the picture may be half drawn');
  if (state.error) problems.push(`the page reported: ${state.error}`);
  if (state.overflow) problems.push('the page is wider than the window');
  report({ ok: !problems.length, wrote: [out], seconds: +((Date.now() - t0) / 1000).toFixed(1), ...state, problems });
} catch (e) {
  report({ ok: false, problems: [String(e.message || e)] });
  process.exitCode = 1;
} finally {
  await b.close();
}
