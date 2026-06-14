import { flightSegments } from "./flightSegments";

test("a non-wrapping route is a single segment", () => {
  const segs = flightSegments({ x: 0.2, y: 0.4 }, { x: 0.5, y: 0.6 });
  expect(segs).toHaveLength(1);
  expect(segs[0]).toEqual({ x1: 0.2, y1: 0.4, x2: 0.5, y2: 0.6 });
});

test("an antimeridian route splits into two seam-crossing segments", () => {
  const segs = flightSegments({ x: 0.9, y: 0.3 }, { x: 0.1, y: 0.5 });
  expect(segs).toHaveLength(2);
  expect(segs[0].x2).toBe(1); // first exits the right edge
  expect(segs[1].x1).toBe(0); // second enters from the left edge
  expect(segs[0].y2).toBeCloseTo(segs[1].y1); // y continuous across the seam
});
