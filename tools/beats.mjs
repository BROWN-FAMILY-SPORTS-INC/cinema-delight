// Check a beat sheet, or print it as a table.
//
//   node tools/beats.mjs check <beats.json> [facts.json]
//   node tools/beats.mjs sheet <beats.json>
//
// Checks shape, not taste: every part has an id and a length; every beat has a unique id, a known
// kind, and a second inside its part; a title has text and ends after it starts and inside the part;
// beats are in order; a beat that names a fact names one that exists in facts.json; `visible` (which
// the sync check measures) is never typed by hand before there are frames to measure it from.
// Film time is the parts laid end to end: a beat at t in the second part plays at the first part's
// length plus t. Last line of output is JSON.

import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';

const KINDS = new Set(['title', 'action', 'answer', 'emotion']);
const EMOTIONS = new Set(['open', 'setup', 'hang', 'breath', 'turn', 'hit', 'fall', 'summit', 'coda', 'tie-back']);
const [cmd, file, factsArg] = process.argv.slice(2);
if (!['check', 'sheet'].includes(cmd) || !file) {
  console.error('usage: node tools/beats.mjs check|sheet <beats.json> [facts.json]');
  console.log(JSON.stringify({ ok: false, wrote: [], problems: ['usage'] }));
  process.exit(2);
}

export function filmBeats(sheet) {
  const out = []; let offset = 0;
  for (const p of sheet.parts || []) {
    for (const b of p.beats || []) out.push({ ...b, part: p.id, film_t: +(offset + b.t).toFixed(3) });
    offset += p.dur;
  }
  return { beats: out, total: offset };
}

const problems = [];
let sheet;
try { sheet = JSON.parse(readFileSync(file, 'utf8')); } catch (e) { problems.push(`not JSON: ${e.message}`); }
if (sheet) {
  if (sheet.format !== 'beats/1') problems.push('format must be "beats/1"');
  if (!Array.isArray(sheet.parts) || !sheet.parts.length) problems.push('no parts');
  const factsFile = factsArg || join(dirname(file), 'facts.json');
  const facts = existsSync(factsFile) ? new Set((JSON.parse(readFileSync(factsFile, 'utf8')).facts || []).map((f) => f.id)) : null;
  const ids = new Set();
  for (const p of sheet.parts || []) {
    if (!p.id) problems.push('a part has no id');
    if (!(p.dur > 0)) problems.push(`part ${p.id}: dur must be a positive number of seconds`);
    let last = -Infinity;
    for (const b of p.beats || []) {
      const where = `${p.id}/${b.id ?? '?'}`;
      if (!b.id) problems.push(`${where}: no id`);
      else if (ids.has(b.id)) problems.push(`${where}: id used twice`);
      ids.add(b.id);
      if (!KINDS.has(b.kind)) problems.push(`${where}: kind must be one of ${[...KINDS].join(', ')}`);
      if (typeof b.t !== 'number' || b.t < 0 || b.t > p.dur) problems.push(`${where}: t must be inside the part (0 to ${p.dur})`);
      if (b.t < last) problems.push(`${where}: beats out of order`);
      last = b.t;
      if (b.kind === 'title') {
        if (!b.text) problems.push(`${where}: a title needs text`);
        if (!(b.until > b.t) || b.until > p.dur) problems.push(`${where}: until must be after t and inside the part`);
      }
      if (b.kind === 'emotion' && !EMOTIONS.has(b.emotion)) problems.push(`${where}: emotion must be one of ${[...EMOTIONS].join(', ')}`);
      if (b.fact && facts && !facts.has(b.fact)) problems.push(`${where}: fact "${b.fact}" is not in ${factsFile}`);
      if (b.fact && !facts) problems.push(`${where}: names a fact but there is no facts.json beside it`);
      if ('visible' in b && !sheet.measured) problems.push(`${where}: visible is measured by the sync check, never typed`);
    }
  }
}

if (cmd === 'sheet' && sheet && !problems.length) {
  const { beats } = filmBeats(sheet);
  for (const b of beats) console.error(`${b.film_t.toFixed(2).padStart(7)}  ${b.part.padEnd(10)} ${b.kind.padEnd(8)} ${b.text || b.emotion || ''}  ${b.what || ''}`);
}
const total = sheet ? (sheet.parts || []).reduce((a, p) => a + (p.dur || 0), 0) : null;
console.log(JSON.stringify({ ok: !problems.length, wrote: [], total, problems }));
process.exitCode = problems.length ? 1 : 0;
