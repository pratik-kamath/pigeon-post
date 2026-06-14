import { project } from "./projection";
import { GRID_COLS, GRID_ROWS, isLand } from "./worldGrid";

// The backend catalog (app/cities.py). Kept here as a fixture to assert the
// generated land grid actually puts city markers on (or right beside) land.
const CITIES: ReadonlyArray<readonly [string, number, number]> = [
  ["amsterdam", 52.3676, 4.9041],
  ["berlin", 52.52, 13.405],
  ["cairo", 30.0444, 31.2357],
  ["cape town", -33.9249, 18.4241],
  ["chicago", 41.8781, -87.6298],
  ["dubai", 25.2048, 55.2708],
  ["hong kong", 22.3193, 114.1694],
  ["istanbul", 41.0082, 28.9784],
  ["london", 51.5074, -0.1278],
  ["los angeles", 34.0522, -118.2437],
  ["melbourne", -37.8136, 144.9631],
  ["mexico city", 19.4326, -99.1332],
  ["mumbai", 19.076, 72.8777],
  ["new york", 40.7128, -74.006],
  ["paris", 48.8566, 2.3522],
  ["rio de janeiro", -22.9068, -43.1729],
  ["san francisco", 37.7749, -122.4194],
  ["singapore", 1.3521, 103.8198],
  ["sydney", -33.8688, 151.2093],
  ["tokyo", 35.6762, 139.6503],
];

/** A city sits on land if its projected cell — or any 8-neighbour, to tolerate
 *  coastal cities at the grid's ~3° resolution — is land. */
function onOrBesideLand(lat: number, lon: number): boolean {
  const { x, y } = project(lat, lon);
  const col = Math.min(GRID_COLS - 1, Math.floor(x * GRID_COLS));
  const row = Math.min(GRID_ROWS - 1, Math.floor(y * GRID_ROWS));
  for (let dr = -1; dr <= 1; dr++)
    for (let dc = -1; dc <= 1; dc++) if (isLand(col + dc, row + dr)) return true;
  return false;
}

test.each(CITIES)("%s projects onto (or beside) land", (_name, lat, lon) => {
  expect(onOrBesideLand(lat, lon)).toBe(true);
});
