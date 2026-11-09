# The scene contract

A scene is one HTML page that draws a 1920×1080 frame as **a pure function of one clock `t`**, in seconds. That is the whole trick. A pure function can be played live, frozen at any moment for a still, and rendered one exact frame at a time, and all three agree. Screen-recording a browser can do none of that reliably.

## Rules

- **Self-contained.** No outside URL, CDN, web font, fetch or import. Inline images as data URIs, downscaled first (`ffmpeg -i in.png -vf scale=1920:-1 -q:v 4 out.jpg`, then base64). A font is one on the machine, or one you embed.
- **One clock.** No `setTimeout` or `setInterval` choreography, and no CSS animation running on its own clock. If you use CSS animations, pause them and wind each one to `t` with a negative `animation-delay`.
- **Seeded randomness only**, so frame `n` is the same picture on every render.
- **The seek API:**

  ```js
  window.briefStages = { seek: (id, t) => { frozen = true; render(t); return true; } };
  ```

  `seek` must draw synchronously and return `true`; a scene may ignore `id`. `?t=9.2` in the URL freezes the scene at that second; with no query it plays live in a loop; a click pauses it.
- **Draw at 1920×1080** and scale to fit when watched. A different size is a decision recorded in the film's `spec.md`.
- **Every number on screen comes from `facts.json`.** If a number was not measured, it is not shown.

## Tools that read the contract

```
node tools/render.mjs <url> <frames> <fps> <end> [hold] [w] [h]
```
```
node tools/slices.mjs <url> <frames> <fps> <end> <from> <to>
```
```
node tools/stills.mjs <url> <dir> <s1> <s2> ...
```
```
tools/still.sh <url> <t> <out.png>
```
```
node tools/state-probe.mjs <url> <s1> <s2> ...
```

A scene opened from `file://` works for all of them. Use `tools/serve.sh <dir> <port>` only to watch one live in a browser, and stop the server when you are done.

## When the camera moves

A film planned as shots runs on film time: the scene's seek hands each film second to `tools/camera.js`, which answers the story second to draw and the crop to show. Slow motion is a short span of story over a long shot; a punch-in is two camera keys at the same second. The format is in the comment at the top of `tools/camera.js`.

## WebGL

WebGL runs headless on the browser's software renderer. Give the scene a 2D fallback (`?gl=0`) in case a future browser drops it, and check both draw.
