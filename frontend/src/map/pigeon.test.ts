import { pigeonPosition } from "./pigeon";
import type { City } from "../api/cities";
import type { Message } from "../api/messages";

const cities = new Map<string, City>([
  ["new york", { name: "new york", lat: 40.7128, lon: -74.006 }],
  ["tokyo", { name: "tokyo", lat: 35.6762, lon: 139.6503 }],
]);

function msg(over: Partial<Message>): Message {
  return {
    id: 1, sender: "me", recipient: "you", body: "hi",
    origin: "new york", destination: "tokyo", distance_km: 1, status: "in_flight",
    sent_at: "2026-06-14T00:00:00", arrival_at: "2026-06-14T10:00:00", resolved_at: null,
    ...over,
  };
}

test("returns null when a city is unknown", () => {
  expect(pigeonPosition(msg({ origin: "atlantis" }), cities, Date.UTC(2026, 5, 14, 5))).toBeNull();
});

test("in-flight position is along the path (between endpoints in y)", () => {
  const p = pigeonPosition(msg({}), cities, Date.UTC(2026, 5, 14, 5, 0, 0))!;
  expect(p).not.toBeNull();
  expect(p.y).toBeGreaterThan(0);
  expect(p.y).toBeLessThan(1);
});

test("delivered and lost rest at the destination", () => {
  const dest = pigeonPosition(msg({ status: "delivered" }), cities, 0)!;
  const lost = pigeonPosition(msg({ status: "lost" }), cities, 0)!;
  // destination is tokyo; both equal the projected destination
  expect(dest).toEqual(lost);
  expect(dest.x).toBeGreaterThan(0.5); // tokyo is east
});
