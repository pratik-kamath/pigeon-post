import type { Point } from "./projection";

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Fraction 0..1 of the journey elapsed (ms epochs). */
export function progress(sentMs: number, arriveMs: number, nowMs: number): number {
  if (arriveMs <= sentMs) return 1;
  return clamp((nowMs - sentMs) / (arriveMs - sentMs), 0, 1);
}

/** Linear interpolation in normalized space, wrapping the SHORTER way in x so
 *  routes across the antimeridian don't traverse the whole map. Result x is
 *  wrapped back into [0,1). */
export function interpolate(a: Point, b: Point, t: number): Point {
  let dx = b.x - a.x;
  if (dx > 0.5) dx -= 1;
  else if (dx < -0.5) dx += 1;
  let x = a.x + dx * t;
  if (x < 0) x += 1;
  else if (x >= 1) x -= 1;
  return { x, y: a.y + (b.y - a.y) * t };
}
