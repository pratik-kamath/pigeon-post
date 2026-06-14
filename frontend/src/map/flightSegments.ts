import type { Point } from "./projection";

export interface Segment { x1: number; y1: number; x2: number; y2: number; }

/** One or two line segments (normalized space) for the dotted path a→b, taking
 *  the shorter direction and splitting across the antimeridian seam when it wraps. */
export function flightSegments(a: Point, b: Point): Segment[] {
  let dx = b.x - a.x;
  if (dx > 0.5) dx -= 1;
  else if (dx < -0.5) dx += 1;
  const endX = a.x + dx;
  if (endX >= 0 && endX <= 1) {
    return [{ x1: a.x, y1: a.y, x2: b.x, y2: b.y }];
  }
  const edge = endX > 1 ? 1 : 0;
  const tEdge = (edge - a.x) / dx;
  const yEdge = a.y + (b.y - a.y) * tEdge;
  return [
    { x1: a.x, y1: a.y, x2: edge, y2: yEdge },
    { x1: edge === 1 ? 0 : 1, y1: yEdge, x2: b.x, y2: b.y },
  ];
}
