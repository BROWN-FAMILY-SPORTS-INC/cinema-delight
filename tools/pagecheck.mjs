// Load a page headless, wait until it is ready, evaluate one expression in it, print the answer.
//
//   node tools/pagecheck.mjs <url> <expression | @file.js> [timeout seconds=90] [width=1920] [height=1080]
//
// Ready means `window.PRINTED === true` or `window.briefStages` exists; PAGECHECK_READY=<expression>
// replaces that test. The expression is awaited, so it may be async: `(async () => { ... })()`.
// PAGECHECK_USER_GESTURE=1 evaluates it as a user action, for checks that play media.
// Use it to ask a page what it knows: whether its fonts loaded, how long a frame takes to draw,
// whether a word fits its box.

import { readFileSync } from 'node:fs';
import { open, report } from './cdp.mjs';

const [url, exprArg, limit = '90', width = '1920', height = '1080'] = process.argv.slice(2);
if (!url || !exprArg) {
  console.error('usage: node tools/pagecheck.mjs <url> <expression | @file.js> [timeout] [width] [height]');
  report({ ok: false, problems: ['missing arguments'] });
  process.exit(2);
}
const expr = exprArg.startsWith('@') ? readFileSync(exprArg.slice(1), 'utf8') : exprArg;
const b = await open({ w: width, h: height, gesture: process.env.PAGECHECK_USER_GESTURE === '1' });
try {
  const t0 = Date.now();
  const ready = await b.goto(url, process.env.PAGECHECK_READY || 'window.PRINTED === true || !!window.briefStages', +limit);
  const pageError = await b.js('document.documentElement.dataset.error || null').catch(() => null);
  const value = ready ? await b.js(`(async () => (${expr}))()`) : null;
  report({ ok: ready && !pageError, ready, seconds: +((Date.now() - t0) / 1000).toFixed(1), pageError, value,
    problems: ready ? (pageError ? [pageError] : []) : ['the page never became ready'] });
} catch (e) {
  report({ ok: false, problems: [String(e.message || e)] });
  process.exitCode = 1;
} finally {
  await b.close();
}
