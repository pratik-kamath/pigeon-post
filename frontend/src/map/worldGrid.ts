// Coarse equirectangular world (cols ≈ lon -180..180, rows ≈ lat 90..-90).
// '#' = land, ' ' = sea. Intentionally blocky — it's a pixel map. Rows are
// padded to equal width, so the art needn't be hand-counted to exact length.
const RAW = [
  "                                     ",
  "      ####        #####  #######     ",
  "   ###########   ###########  ##     ",
  "    ##########   ##########           ",
  "      ########   #########           ",
  "        #####     ####  ####          ",
  "         ###       ##########         ",
  "         ###        #########         ",
  "         ##          ########         ",
  "         ##           ######          ",
  "         ###          #####           ",
  "          ##           ###      ##    ",
  "          ##           ###      ##    ",
  "           #           ##             ",
  "                       #              ",
  "             ####                     ",
  "              ##                      ",
  "                                     ",
];
const WIDTH = Math.max(...RAW.map((r) => r.length));
const ROWS = RAW.map((r) => r.padEnd(WIDTH, " "));

export const GRID_ROWS = ROWS.length;
export const GRID_COLS = WIDTH;

export function isLand(col: number, row: number): boolean {
  if (row < 0 || row >= GRID_ROWS || col < 0 || col >= GRID_COLS) return false;
  return ROWS[row][col] === "#";
}
