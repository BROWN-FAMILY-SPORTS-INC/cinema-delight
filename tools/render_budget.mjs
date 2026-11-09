// Refuse to start a render on a disk that cannot hold it.
//
//   import { checkRenderSpace } from './render_budget.mjs';
//   checkRenderSpace(outdir);   // throws with the free and required space
//
// A minute at 60 fps is 3,600 JPEGs, roughly 1 to 2 GB at 1920x1080. A render that fills the disk
// halfway writes truncated frames that encode as black. CINEMA_MIN_FREE_BYTES sets the floor
// (default 5 GiB). Note that /tmp is RAM on many Linux systems: write frames to a real disk.

import { existsSync, statfsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

export function checkRenderSpace(destination, minimum = Number(process.env.CINEMA_MIN_FREE_BYTES ?? 5 * 1024 ** 3)) {
  if (!Number.isSafeInteger(minimum) || minimum < 0) throw new Error('CINEMA_MIN_FREE_BYTES must be a nonnegative byte count');
  let path = resolve(destination);
  while (!existsSync(path)) path = dirname(path);
  const fs = statfsSync(path), free = fs.bavail * fs.bsize;
  if (free < minimum) throw new Error(`not enough space on ${path}: ${(free / 1024 ** 3).toFixed(1)} GiB free, ${(minimum / 1024 ** 3).toFixed(1)} GiB required`);
  return { path, free_bytes: free, minimum_bytes: minimum };
}
