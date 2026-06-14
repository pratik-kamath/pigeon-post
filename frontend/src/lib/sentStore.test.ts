import { mergeServer, withOptimistic } from "./sentStore";
import type { Message } from "../api/messages";

const m = (id: number): Message => ({
  id, sender: "me", recipient: "x", body: "b", origin: "new york",
  destination: "tokyo", distance_km: 1, status: "in_flight",
  sent_at: "2026-06-14T00:00:00", arrival_at: "2999-01-01T00:00:00", resolved_at: null,
});

test("a poll that doesn't yet include an optimistic send keeps it visible", () => {
  const { pending, all } = mergeServer([m(42)], [m(1)]);
  expect(pending.map((x) => x.id)).toEqual([42]); // still pending
  expect(all.map((x) => x.id)).toEqual([42, 1]);   // shown
});

test("once the server reports the id, it drops from pending and isn't duplicated", () => {
  const { pending, all } = mergeServer([m(42)], [m(42), m(1)]);
  expect(pending).toEqual([]);
  expect(all.map((x) => x.id)).toEqual([42, 1]);
});

test("withOptimistic prepends and de-dupes by id", () => {
  expect(withOptimistic([m(1)], m(42)).map((x) => x.id)).toEqual([42, 1]);
  expect(withOptimistic([m(42), m(1)], m(42)).map((x) => x.id)).toEqual([42, 1]);
});
