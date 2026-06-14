export interface Point { x: number; y: number; }

/** Equirectangular projection to a normalized [0,1] box.
 *  x: lon -180..180 -> 0..1 ; y: lat 90..-90 -> 0..1 (north at top). */
export function project(lat: number, lon: number): Point {
  return { x: (lon + 180) / 360, y: (90 - lat) / 180 };
}
