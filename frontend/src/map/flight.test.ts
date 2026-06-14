import { progress, interpolate } from "./flight";
import { project } from "./projection";

const sent = Date.UTC(2026, 5, 14, 0, 0, 0);
const arrive = Date.UTC(2026, 5, 14, 10, 0, 0); // 10h flight

test("progress clamps to [0,1]", () => {
  expect(progress(sent, arrive, sent)).toBe(0);
  expect(progress(sent, arrive, Date.UTC(2026, 5, 14, 5, 0, 0))).toBeCloseTo(0.5);
  expect(progress(sent, arrive, Date.UTC(2026, 5, 14, 20, 0, 0))).toBe(1);
});

test("interpolate midpoint of two near points", () => {
  const a = { x: 0.2, y: 0.4 };
  const b = { x: 0.4, y: 0.6 };
  const mid = interpolate(a, b, 0.5);
  expect(mid.x).toBeCloseTo(0.3); // floating-point: 0.30000000000000004
  expect(mid.y).toBeCloseTo(0.5);
});

test("antimeridian pair takes the short wrapped path (Tokyo -> San Francisco)", () => {
  const tokyo = project(35.6762, 139.6503);        // x ~0.89
  const sf = project(37.7749, -122.4194);          // x ~0.16
  const mid = interpolate(tokyo, sf, 0.5);
  // halfway should be NEAR the seam (x close to 0 or 1), not mid-map
  expect(mid.x < 0.1 || mid.x > 0.9).toBe(true);
});
