import type { Point } from "./projection";
import { project } from "./projection";
import { progress, interpolate } from "./flight";
import { parseServerUtc } from "../lib/time";
import type { Message } from "../api/messages";
import type { City } from "../api/cities";

/** Normalized [0,1] map position for a message, or null if a city is unknown.
 *  in_flight → interpolated along the (antimeridian-wrapped) path;
 *  delivered/lost → the destination (the backend has no failure coordinate). */
export function pigeonPosition(
  msg: Message,
  cityByName: Map<string, City>,
  nowMs: number
): Point | null {
  const o = cityByName.get(msg.origin);
  const d = cityByName.get(msg.destination);
  if (!o || !d) return null;
  const a = project(o.lat, o.lon);
  const b = project(d.lat, d.lon);
  if (msg.status !== "in_flight") return b;
  const t = progress(
    parseServerUtc(msg.sent_at).getTime(),
    parseServerUtc(msg.arrival_at).getTime(),
    nowMs
  );
  return interpolate(a, b, t);
}
