import { GRID_COLS, GRID_ROWS, isLand } from "./worldGrid";

test("grid is the generated 120x60", () => {
  expect(GRID_COLS).toBe(120);
  expect(GRID_ROWS).toBe(60);
});

test("isLand returns a boolean and rejects out-of-bounds", () => {
  expect(typeof isLand(0, 0)).toBe("boolean");
  expect(isLand(-1, 0)).toBe(false);
  expect(isLand(0, GRID_ROWS)).toBe(false);
  expect(isLand(GRID_COLS, 0)).toBe(false);
});

test("land coverage is realistic (continents + oceans)", () => {
  let land = 0;
  for (let r = 0; r < GRID_ROWS; r++)
    for (let c = 0; c < GRID_COLS; c++) if (isLand(c, r)) land++;
  const frac = land / (GRID_COLS * GRID_ROWS);
  expect(frac).toBeGreaterThan(0.2); // Earth is ~29% land (+Antarctica here)
  expect(frac).toBeLessThan(0.45);
});
