"""One self-contained review page with a note box on every item and a Copy notes button.

    from notespage import page
    html = page(title, lede, items, film=None, heading=None)

Every page a person reads (the storyboard, a draft's review, the sound options) is built here, so
they all take notes the same way. An item is {"id", "label", "t" (optional film second), "img" or
"audio" or "video" (a path relative to the page), "text" (optional)}. Copy notes turns whatever the
person typed into plain text, one note per line, each tagged with its item's id and second:

    NOTES · <heading>
    [<id> @ <t>s] <their words>
    [page] <a note on the whole page>

The person pastes that back to their agent, which saves it verbatim (tools/moments.py --save).
Nothing is loaded from outside, and the page works opened from disk. It has layout and no styling of
its own: the browser's colours and fonts. A page is a place to judge the film, not part of its look.
"""
from __future__ import annotations

import html
import json

CSS = """
:root{color-scheme:light dark}body{margin:0;font:15px/1.5 sans-serif}main{max-width:1100px;margin:0 auto;padding:20px 16px 100px}
.item{border:1px solid;border-radius:6px;padding:12px;margin:0 0 14px}.item h2{font-size:15px;margin:0 0 8px}.t{margin-left:8px;cursor:pointer}
.item img,.item video{display:block;width:100%;height:auto}.item audio{width:100%}textarea{width:100%;box-sizing:border-box;min-height:48px;margin-top:8px;font:inherit}
.bar{position:fixed;left:0;right:0;bottom:0;padding:10px 16px;display:flex;gap:12px;align-items:center;background:Canvas;border-top:1px solid}
#out{position:absolute;left:-9999px}
"""

JS = """
const heading = %s;
function notes() {
  const lines = ['NOTES · ' + heading];
  for (const box of document.querySelectorAll('textarea[data-id]')) {
    const v = box.value.trim(); if (!v) continue;
    const t = box.dataset.t ? ' @ ' + box.dataset.t + 's' : '';
    for (const line of v.split(/\\n+/)) lines.push('[' + box.dataset.id + t + '] ' + line.trim());
  }
  return lines.join('\\n');
}
function count() { return [...document.querySelectorAll('textarea[data-id]')].filter((b) => b.value.trim()).length; }
document.addEventListener('input', () => { document.getElementById('status').textContent = count() + ' notes'; });
document.getElementById('copy').addEventListener('click', async () => {
  const text = notes(), status = document.getElementById('status');
  try { await navigator.clipboard.writeText(text); status.textContent = 'copied: paste it to your agent'; }
  catch { const out = document.getElementById('out'); out.value = text; out.select(); document.execCommand('copy');
          status.textContent = 'copied: paste it to your agent'; }
});
for (const v of document.querySelectorAll('[data-seek]')) v.addEventListener('click', () => {
  const film = document.querySelector('video.film'); if (film) { film.currentTime = +v.dataset.seek; film.play(); }
});
window.PRINTED = true;
"""


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def media(it: dict) -> str:
    if it.get("img"):
        return f'<img src="{esc(it["img"])}" alt="{esc(it.get("label", ""))}" loading="lazy">'
    if it.get("audio"):
        return f'<audio controls preload="metadata" src="{esc(it["audio"])}"></audio>'
    if it.get("video"):
        return f'<video controls preload="metadata" src="{esc(it["video"])}"></video>'
    return ""


def page(title: str, lede: str, items: list[dict], film: str | None = None, heading: str | None = None) -> str:
    parts = [f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{esc(title)}</title>",
             f"<meta name=viewport content='width=device-width,initial-scale=1'><style>{CSS}</style></head><body><main>",
             f"<h1>{esc(title)}</h1><p class=lede>{esc(lede)}</p>"]
    if film:
        parts.append(f'<div class=item><video class=film controls preload=metadata src="{esc(film)}"></video>'
                     '<textarea data-id="film" placeholder="A note on the whole film"></textarea></div>')
    for it in items:
        t = it.get("t")
        tlabel = f'<span class=t data-seek="{t}">{t:.2f} s</span>' if isinstance(t, (int, float)) else ""
        body = f'<p>{esc(it["text"])}</p>' if it.get("text") else ""
        tattr = f' data-t="{t:.2f}"' if isinstance(t, (int, float)) else ""
        parts.append(f'<section class=item id="{esc(it["id"])}"><h2>{esc(it.get("label", it["id"]))}{tlabel}</h2>'
                     f'{media(it)}{body}<textarea data-id="{esc(it["id"])}"{tattr} placeholder="A note"></textarea></section>')
    parts.append('<section class=item><h2>Anything else</h2><textarea data-id="page" placeholder="A note on the whole page"></textarea></section>')
    parts.append('</main><div class=bar><button id=copy type=button>Copy notes</button><span id=status>0 notes</span></div>'
                 f'<textarea id=out aria-hidden=true></textarea><script>{JS % json.dumps(heading or title)}</script></body></html>')
    return "".join(parts)
