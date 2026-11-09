// tty.js: TTY, a real terminal capture drawn cell for cell in a scene's window, on the film's clock.
//
// A capture (tools/tty_capture.py) is what a program actually drew: frames of rows, each row a list of runs
// [col, text, fg, bg, flags], with the terminal's palette at every moment.
//
//   TTY.draw(q, x, y, w, h, cap, ct, o)   the capture at capture-second ct, fitted to the box; o.face (the film's
//                                         monospace face, from its look), o.cursor (default true), o.palette (a
//                                         terminal palette to draw it in instead of the capture's own)
//   TTY.at(map, t)                        film second -> capture second, through [[film, capture], ...] keyframes
//   TTY.speed(map, t)                     how many capture seconds pass per film second there (to label a time-lapse)
//   TTY.mark(cap, name)                   the capture second of a mark the session named
//
// Colours: a run's fg/bg is "default" (the palette's fg/bg), an ANSI name (pyte's: red, brown, brightblue...; a slot
// of the palette) or a hex colour (truecolor). Flags: 1 bold, 2 italic, 4 underline, 8 reverse. Every run carries its
// own column, so wide characters stay aligned. Each glyph is drawn in its own cell: a run drawn as one string drifts
// wherever a glyph's advance is not exactly one cell.
(function () {
  'use strict';
  const ANSI = { black: 0, red: 1, green: 2, brown: 3, yellow: 3, blue: 4, magenta: 5, cyan: 6, white: 7 };
  const ADV = 0.6;   // a typical monospace advance, in ems; pass o.adv for the face the look chose

  function frameAt(cap, ct) {
    const F = cap.frames; let lo = 0, hi = F.length - 1;
    if (ct <= F[0][0]) return F[0];
    while (lo < hi) { const m = (lo + hi + 1) >> 1; if (F[m][0] <= ct) lo = m; else hi = m - 1; }
    return F[lo];
  }
  function paletteAt(cap, ct) {
    const L = cap.palettes || [[0, '', cap.palette]]; let p = L[0][2];
    for (const [t, , pal] of L) if (t <= ct) p = pal;
    return p;
  }
  function colour(c, pal, fallback) {
    if (!c || c === 'default') return fallback;
    if (/^[0-9a-f]{6}$/i.test(c)) return '#' + c;
    let name = c.toLowerCase(), bright = 0;
    if (name.startsWith('bright')) { bright = 8; name = name.slice(6); }
    const k = ANSI[name];
    return k == null ? fallback : pal.colors[k + bright];
  }

  // o.palette draws the capture in another terminal palette: honest only for a program that draws in the terminal's
  // ANSI slots (as a shell does), which a theme switch recolours live; truecolor cells keep their colour
  function draw(q, x, y, w, h, cap, ct, o = {}) {
    const pal = o.palette || paletteAt(cap, ct), fr = frameAt(cap, ct);
    const FACE = o.face || 'monospace', cw = w / cap.cols, ch = h / cap.rows, fs = Math.min(cw / (o.adv || ADV), ch * 0.92);
    q.save();
    q.beginPath(); q.rect(x, y, w, h); q.clip();
    q.fillStyle = pal.bg; q.fillRect(x, y, w, h);
    q.textBaseline = 'middle';
    // backgrounds first, then text, so a glyph's overhang is never painted over by the next cell's ground
    for (let r = 0; r < cap.rows; r++) {
      for (const [col, text, fg, bg, fl] of cap.table[fr[1][r]]) {
        const rev = fl & 8, b = rev ? colour(fg, pal, pal.fg) : colour(bg, pal, null);
        if (!b) continue;
        q.fillStyle = b; q.fillRect(Math.floor(x + col * cw), Math.floor(y + r * ch), Math.ceil(text.length * cw) + 1, Math.ceil(ch) + 1);
      }
    }
    for (let r = 0; r < cap.rows; r++) {
      const cy = y + (r + 0.5) * ch;
      for (const [col, text, fg, bg, fl] of cap.table[fr[1][r]]) {
        if (!text.trim()) continue;
        const rev = fl & 8;
        q.fillStyle = rev ? colour(bg, pal, pal.bg) : colour(fg, pal, pal.fg);
        q.font = `${fl & 2 ? 'italic ' : ''}${fl & 1 ? 700 : 400} ${fs.toFixed(2)}px ${FACE}`;
        // one glyph per cell: a run drawn as a string would drift where a glyph's advance is not exactly one cell
        let k = 0;
        for (const g of text) {
          if (g !== ' ') q.fillText(g, x + (col + k) * cw, cy);
          k += 1;
        }
        if (fl & 4) { q.fillRect(x + col * cw, y + (r + 1) * ch - Math.max(1, ch * 0.08), k * cw, Math.max(1, ch * 0.06)); }
      }
    }
    // the program's cursor, where it left it showing
    if (o.cursor !== false && fr[4] && (o.blink === false || (ct * 1.6) % 1 < 0.62)) {
      q.globalAlpha = 0.85; q.fillStyle = pal.cursor || pal.fg;
      q.fillRect(x + fr[2] * cw, y + fr[3] * ch + ch * 0.08, Math.max(2, cw * 0.95), ch * 0.84);
    }
    q.restore();
  }

  function at(map, t) {
    if (t <= map[0][0]) return map[0][1];
    for (let k = 0; k < map.length - 1; k++) {
      const [a, ca] = map[k], [b, cb] = map[k + 1];
      if (t < b) return ca + (cb - ca) * (t - a) / (b - a);
    }
    return map[map.length - 1][1];
  }
  function speed(map, t) {
    for (let k = 0; k < map.length - 1; k++) { const [a, ca] = map[k], [b, cb] = map[k + 1]; if (t >= a && t < b) return (cb - ca) / (b - a); }
    return 0;
  }
  function mark(cap, name) {
    const m = (cap.marks || []).find((x) => x[1] === name);
    if (!m) throw new Error(`capture has no mark "${name}"`);
    return m[0];
  }
  window.TTY = { draw, at, speed, mark, frameAt };
})();
