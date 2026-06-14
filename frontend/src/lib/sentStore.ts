import type { Message } from "../api/messages";

/** Merge a server poll with locally-pending optimistic sends: the server is
 *  authoritative for ids it returns; pending sends it hasn't reported yet stay
 *  visible (so a poll that started before a send can't drop the new pigeon). */
export function mergeServer(
  pending: Message[],
  server: Message[]
): { pending: Message[]; all: Message[] } {
  const ids = new Set(server.map((m) => m.id));
  const stillPending = pending.filter((m) => !ids.has(m.id));
  return { pending: stillPending, all: [...stillPending, ...server] };
}

/** Prepend a message, de-duped by id. */
export function withOptimistic(current: Message[], m: Message): Message[] {
  return [m, ...current.filter((x) => x.id !== m.id)];
}
