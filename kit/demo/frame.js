// frame.js: DEMO, the mechanics of a product demo: where things go, and when keys, typing and the pointer happen.
//
// It decides layout and timing only. Every colour, face and size comes from the film's own look (look.md), passed in
// as L; nothing here has a default, so a demo built on it looks like the film and not like this file. The grammar is
// protocol/demo.md. Everything is a pure function of its arguments, so it renders frame-exact.
//
//   DEMO.layout(W, H, o)          {words, ui}: the words' column on the left, the program's window on the right.
//                                 o.split (share of the width for words, 0.4), o.margin (px, 96), o.gap (px, 64)
//   DEMO.chapter(t, chapters)     which chapter t is in: {i, id, local, p} (p is 0..1 through it), or null.
//                                 chapters: [{id, at, until}], in order
//   DEMO.typed(text, t, at, cps)  the part of text typed by second t, typing from `at` at cps characters a second
//   DEMO.typedDone(text, at, cps) the second the last character lands: put the program's answer after it
//   DEMO.press(t, at, down, up)   how far a key is pressed at t (0 up, 1 down) for a press at `at`
//   DEMO.drawKey(c, label, x, y, depth, L)              a keycap; L.keyFace, L.keyInk, L.keyEdge, L.face, L.keySize
//   DEMO.drawPointer(c, x, y, t, clickAt, L)            the pointer, and a ring growing from a click; L.pointer, L.ring
//   DEMO.drag(t, at, dur, from, to)                     where a dragged pointer is at t: [x, y], eased
//
// Put a key's press on the beat that answers it, and the program's answer a moment after (beats.json: an action, then
// its answer). Draw the program from a real capture (kit/demo/tty.js), never from a mock-up.
(function (root) {
  'use strict';
  const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);
  const ease = (p) => (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2);

  function need(L, keys) {
    for (const k of keys) if (L == null || L[k] == null) throw new Error(`DEMO: the look must give ${k} (see protocol/look.md)`);
  }

  function layout(W, H, o = {}) {
    const m = o.margin ?? 96, gap = o.gap ?? 64, split = o.split ?? 0.4;
    const ww = (W - 2 * m - gap) * split;
    return { words: { x: m, y: m, w: ww, h: H - 2 * m }, ui: { x: m + ww + gap, y: m, w: W - 2 * m - gap - ww, h: H - 2 * m } };
  }

  function chapter(t, chapters) {
    for (let i = 0; i < chapters.length; i++) {
      const c = chapters[i];
      if (t >= c.at && t < c.until) return { i, id: c.id, local: t - c.at, p: (t - c.at) / (c.until - c.at) };
    }
    return null;
  }

  const typed = (text, t, at, cps = 14) => text.slice(0, clamp(Math.floor((t - at) * cps), 0, text.length));
  const typedDone = (text, at, cps = 14) => at + text.length / cps;

  function press(t, at, down = 0.08, up = 0.14) {
    if (t < at - down || t > at + up) return 0;
    return t < at ? ease((t - (at - down)) / down) : 1 - ease((t - at) / up);
  }

  function roundRect(c, x, y, w, h, r) {
    c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
  }

  function drawKey(c, label, x, y, depth, L) {
    need(L, ['keyFace', 'keyInk', 'keyEdge', 'face', 'keySize']);
    const s = L.keySize, w = Math.max(s, s * 0.62 * label.length + s * 0.5), lift = s * 0.12 * (1 - depth);
    c.save();
    c.fillStyle = L.keyEdge; roundRect(c, x, y + s * 0.12, w, s, s * 0.18); c.fill();
    c.fillStyle = L.keyFace; roundRect(c, x, y + s * 0.12 - lift, w, s, s * 0.18); c.fill();
    c.fillStyle = L.keyInk; c.font = `${Math.round(s * 0.42)}px ${L.face}`; c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillText(label, x + w / 2, y + s * 0.12 - lift + s / 2);
    c.restore();
    return w;
  }

  function drawPointer(c, x, y, t, clickAt, L) {
    need(L, ['pointer', 'ring']);
    if (clickAt != null && t >= clickAt && t < clickAt + 0.45) {
      const p = (t - clickAt) / 0.45;
      c.save(); c.globalAlpha = 1 - p; c.strokeStyle = L.ring; c.lineWidth = 3;
      c.beginPath(); c.arc(x, y, 8 + 36 * ease(p), 0, Math.PI * 2); c.stroke(); c.restore();
    }
    c.save(); c.fillStyle = L.pointer; c.beginPath();
    c.moveTo(x, y); c.lineTo(x, y + 26); c.lineTo(x + 7, y + 20); c.lineTo(x + 12, y + 30); c.lineTo(x + 16, y + 28);
    c.lineTo(x + 11, y + 18); c.lineTo(x + 19, y + 18); c.closePath(); c.fill(); c.restore();
  }

  function drag(t, at, dur, from, to) {
    const p = ease(clamp((t - at) / dur, 0, 1));
    return [from[0] + (to[0] - from[0]) * p, from[1] + (to[1] - from[1]) * p];
  }

  root.DEMO = { layout, chapter, typed, typedDone, press, drawKey, drawPointer, drag };
})(typeof window !== 'undefined' ? window : globalThis);
