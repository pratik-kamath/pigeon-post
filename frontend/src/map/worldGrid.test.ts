import { GRID_COLS, GRID_ROWS, isLand } from "./worldGrid";

test("grid has sane dimensions", () => {
  expect(GRID_COLS).toBeGreaterThan(20);
  expect(GRID_ROWS).toBeGreaterThan(10);
});

test("isLand returns a boolean and the poles/oceans are sea", () => {
  expect(typeof isLand(0, 0)).toBe("boolean");
  // far south-pacific cell (bottom-left-ish) is ocean
  expect(isLand(1, GRID_ROWS - 1)).toBe(false);
});

test("there is some land and some sea", () => {
  let land = 0, sea = 0;
  for (let r = 0; r < GRID_ROWS; r++)
    for (let c = 0; c < GRID_COLS; c++) (isLand(c, r) ? land++ : sea++);
  expect(land).toBeGreaterThan(0);
  expect(sea).toBeGreaterThan(0);
});
