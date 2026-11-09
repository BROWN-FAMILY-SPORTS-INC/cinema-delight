// Seek a canvas scene to chosen seconds and report the drawing state each frame leaves behind.
//
//   node tools/state-probe.mjs <scene url> <s1> <s2> ... [--stage stage]
//
// A save() whose restore() never runs throws nothing. Its alpha, clip or transform stays on every later
// draw in the frame, and a renderer that seeks frame after frame in one page carries it into the next.
// The usual cause is small: a `//` comment at the end of a one-line loop body swallows the restore(),
// and everything drawn after it comes out nearly transparent while the scene reports no error.
//
// This counts save/restore depth on every 2D canvas while the scene draws one frame, and records any
// alpha set to 0 or outside 0..1. A clean frame leaves depth 0, alpha 1, source-over and the identity
// transform on every canvas. Exit 1 if any frame leaks.

import { open, report } from './cdp.mjs';

const argv = process.argv.slice(2);
const si = argv.indexOf('--stage');
const stageId = si < 0 ? 'stage' : argv.splice(si, 2)[1];
const [url, ...secs] = argv;
if (!url || !secs.length) {
  console.error('usage: node tools/state-probe.mjs <scene url> <s1> <s2> ... [--stage id]');
  report({ ok: false, problems: ['missing arguments'] });
  process.exit(2);
}
const b = await open();
const frames = [];
try {
  if (!(await b.goto(url, 'document.readyState === "complete" && !!window.briefStages')))
    throw new Error('the scene never exposed window.briefStages');
  await b.js(`(() => {
    const P = CanvasRenderingContext2D.prototype, save = P.save, restore = P.restore;
    const ga = Object.getOwnPropertyDescriptor(P, 'globalAlpha');
    window.__probe = { depth: new Map(), odd: [] };
    P.save = function () { __probe.depth.set(this, (__probe.depth.get(this) || 0) + 1); return save.call(this); };
    P.restore = function () { __probe.depth.set(this, (__probe.depth.get(this) || 0) - 1); return restore.call(this); };
    Object.defineProperty(P, 'globalAlpha', { configurable: true, get() { return ga.get.call(this); },
      set(v) { if (!(v > 0 && v <= 1)) __probe.odd.push(String(v)); ga.set.call(this, v); } });
  })()`);
  for (const s of secs) {
    const v = await b.js(`(() => {
      __probe.depth.clear(); __probe.odd.length = 0;
      let threw = null;
      try { briefStages.seek(${JSON.stringify(stageId)}, ${+s}); } catch (e) { threw = String(e && e.message || e); }
      const canvases = [...document.querySelectorAll('canvas')].map((el, i) => {
        const c = el.getContext('2d'); if (!c) return null;
        const m = c.getTransform();
        return { canvas: el.id || i, depth: __probe.depth.get(c) || 0, alpha: +c.globalAlpha.toFixed(4),
          op: c.globalCompositeOperation, identity: m.isIdentity };
      }).filter(Boolean);
      return { second: ${+s}, threw, oddAlphas: __probe.odd.slice(0, 5), canvases };
    })()`);
    v.leak = !!v.threw || v.canvases.some((c) => c.depth !== 0 || c.alpha !== 1 || c.op !== 'source-over' || !c.identity);
    frames.push(v);
    console.error(`${s}\t${v.leak ? 'LEAK' : 'clean'}`);
  }
  const leaks = frames.filter((f) => f.leak);
  report({ ok: !leaks.length, frames, problems: leaks.map((f) => `state leaks at ${f.second} s`) });
  process.exitCode = leaks.length ? 1 : 0;
} catch (e) {
  report({ ok: false, problems: [String(e.message || e)] });
  process.exitCode = 1;
} finally {
  await b.close();
}
