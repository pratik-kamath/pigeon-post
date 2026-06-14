import { project } from "./projection";

test("lon 0 / lat 0 maps to the center", () => {
  expect(project(0, 0)).toEqual({ x: 0.5, y: 0.5 });
});

test("corners map to the unit box", () => {
  expect(project(90, -180)).toEqual({ x: 0, y: 0 });   // NW
  expect(project(-90, 180)).toEqual({ x: 1, y: 1 });   // SE
});

test("a known city projects sensibly (Tokyo: east + northern)", () => {
  const { x, y } = project(35.6762, 139.6503);
  expect(x).toBeGreaterThan(0.5);
  expect(y).toBeLessThan(0.5);
});
