// Find a Chromium-family browser to drive headless. $CHROME wins; then the usual names on PATH.
import { execFileSync } from 'node:child_process';

export function findBrowser() {
  if (process.env.CHROME) return process.env.CHROME;
  for (const name of ['chromium', 'chromium-browser', 'google-chrome-stable', 'google-chrome']) {
    try { return execFileSync('sh', ['-c', `command -v ${name}`], { encoding: 'utf8' }).trim(); } catch {}
  }
  throw new Error('no Chromium or Chrome found: install one, or set CHROME to its path');
}
