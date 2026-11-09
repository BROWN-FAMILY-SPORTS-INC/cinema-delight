// camera.js — two tracks for every shot: which second of the story to draw, and which part of the
// frame the viewer sees. A film is planned as story points (what happens, and how fast) and flyby
// points (where the camera punches in, slows right down, pulls out and moves).
//
//   const cam = makeCamera(shots, format, views);   // format {w, h}; views: named framings
//   cam.total                      // film seconds
//   cam.at(t) → {story, speed, crop: {x, y, w, h}, zoom, shot, off}
//
// A shot:
//   dur      film seconds
//   story    [[off, s], ...]  story second s at film offset off, linear between keys;
//            [s0, s1] runs s0 → s1 across the shot; a single number freezes the story on that second.
//            1.2 story seconds over an 8 s shot plays at 0.15x: that is slow motion.
//   camera   [[off, view], ...], or a single view held for the shot. A view is one of
//              "wide"                 the whole frame
//              {x, y, w}              a crop in frame pixels; h follows from the frame's aspect
//              {at: [cx, cy], zoom}   a punch zoom centred on a point, kept inside the frame
//              "prev"                 where the previous shot's camera ended (a move across a cut)
//              "<name>"               a framing named once in `views` (e.g. "screen")
//            Any view may carry `on: "the door"`, saying what it is for; the storyboard shows it.
//            Between two keys the camera eases in and out (centre linear, width in log space, so a
//            zoom feels even); two keys at the same offset are a cut, i.e. a punch. A view may carry
//            `ease: "in"` (accelerates all the way), `"out"` (arrives fast and settles) or `"linear"`.
//
// In a scene:   window.briefStages.seek = (id, t) => { const s = cam.at(t); draw(s.story, t, s.crop); }
// From a shell: node tools/camera.js <shots.json> [step=0.25]   samples as JSON, for a storyboard
//               shots.json is {"format": {"w": 1920, "h": 1080}, "views": {...}, "shots": [...]}

(function (root) {
  const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);
  const ease = (p) => (p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
  const EASES = { in: (p) => p * p * p, out: (p) => 1 - Math.pow(1 - p, 3), linear: (p) => p };

  function view(v, W, H, prev, views) {
    const wide = { x: 0, y: 0, w: W, h: H };
    if (v === 'wide' || v == null) return wide;
    if (v === 'prev') return prev || wide;
    if (typeof v === 'string') { if (!views || !views[v]) throw new Error(`camera: no view named "${v}"`); v = views[v]; }
    let w, x, y;
    if (v.zoom) { w = W / v.zoom; x = v.at[0] - w / 2; y = v.at[1] - (w * H / W) / 2; }
    else { w = v.w; x = v.x; y = v.y; }
    w = clamp(w, 16, W);
    const h = w * H / W, out = { x: clamp(x, 0, W - w), y: clamp(y, 0, H - h), w, h };
    if (v.ease) { if (!EASES[v.ease]) throw new Error(`camera: no ease named "${v.ease}"`); out.ease = v.ease; }
    return out;
  }

  function storyKeys(v, dur) {
    if (typeof v === 'number') return [[0, v], [dur, v]];
    if (Array.isArray(v) && v.length === 2 && typeof v[0] === 'number') return [[0, v[0]], [dur, v[1]]];
    return v;
  }

  function makeCamera(shots, fmt, views) {
    const W = fmt.w, H = fmt.h;
    let t0 = 0, prev = null;
    const S = shots.map((s) => {
      const st = storyKeys(s.story, s.dur);
      const raw = Array.isArray(s.camera) && Array.isArray(s.camera[0]) ? s.camera : [[0, s.camera]];
      const ck = [];
      for (const [off, v] of raw) ck.push([off, view(v, W, H, ck.length ? ck[ck.length - 1][1] : prev, views)]);
      prev = ck[ck.length - 1][1];
      const o = { shot: s, t0, dur: s.dur, st, ck };
      t0 += s.dur;
      return o;
    });
    const total = t0;

    function find(t) {
      t = clamp(t, 0, total);
      for (const s of S) if (t < s.t0 + s.dur) return s;
      return S[S.length - 1];
    }
    function story(k, off) {
      if (off <= k[0][0]) return { v: k[0][1], speed: 0 };
      for (let i = 0; i < k.length - 1; i++) {
        const [a, va] = k[i], [b, vb] = k[i + 1];
        if (off < b) { if (b === a) return { v: vb, speed: 0 }; const f = (off - a) / (b - a); return { v: va + (vb - va) * f, speed: (vb - va) / (b - a) }; }
      }
      return { v: k[k.length - 1][1], speed: 0 };
    }
    function crop(k, off) {
      let A = k[0][1], B = A, f = 0;
      for (let i = 0; i < k.length; i++) if (off >= k[i][0]) { A = k[i][1]; B = A; f = 0; if (i + 1 < k.length && k[i + 1][0] > k[i][0]) { B = k[i + 1][1]; f = (EASES[B.ease] || ease)(clamp((off - k[i][0]) / (k[i + 1][0] - k[i][0]), 0, 1)); } }
      const cxA = A.x + A.w / 2, cyA = A.y + A.h / 2, cxB = B.x + B.w / 2, cyB = B.y + B.h / 2;
      const w = Math.exp(Math.log(A.w) + (Math.log(B.w) - Math.log(A.w)) * f), h = w * H / W;
      const cx = cxA + (cxB - cxA) * f, cy = cyA + (cyB - cyA) * f;
      return { x: clamp(cx - w / 2, 0, W - w), y: clamp(cy - h / 2, 0, H - h), w, h };
    }
    return {
      total, shots: S,
      at(t) {
        const s = find(t), off = clamp(t - s.t0, 0, s.dur), sv = story(s.st, off), c = crop(s.ck, off);
        return { story: sv.v, speed: sv.speed, crop: c, zoom: W / c.w, shot: s.shot, off };
      },
    };
  }
  root.makeCamera = makeCamera;

  // node tools/camera.js <shots.json> [step]
  if (typeof module !== 'undefined' && typeof require !== 'undefined' && require.main === module) {
    const plan = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
    const cam = makeCamera(plan.shots, plan.format, plan.views), out = [];
    // [step] samples the whole film; `--at 1.5,14,20` samples exactly those film seconds
    const ats = process.argv[3] === '--at' ? process.argv[4].split(',').map(Number) : null, step = +(process.argv[3] || .25);
    const times = ats || []; if (!ats) for (let t = 0; t <= cam.total + 1e-9; t += step) times.push(t);
    for (const t of times) {
      const s = cam.at(t);
      out.push({ t: +t.toFixed(3), story: +s.story.toFixed(3), speed: +s.speed.toFixed(3), zoom: +s.zoom.toFixed(3),
        crop: [s.crop.x, s.crop.y, s.crop.w, s.crop.h].map((v) => +v.toFixed(1)), shot: s.shot.id });
    }
    process.stdout.write(JSON.stringify({ total: cam.total, samples: out }));
  }
})(typeof window !== 'undefined' ? window : globalThis);
