// @vitest-environment jsdom
import { apiFetch, onLogout } from "./client";
import { tokens } from "./tokens";

const BASE = "http://localhost:8000";
beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  vi.stubEnv("VITE_API_BASE_URL", BASE);
});

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("attaches the bearer token", async () => {
  tokens.set({ access_token: "acc", refresh_token: "ref" });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ ok: true }));
  await apiFetch("/messages/sent");
  const init = fetchMock.mock.calls[0][1]!;
  expect(new Headers(init.headers).get("Authorization")).toBe("Bearer acc");
});

test("401 -> refresh -> retry once with the new token", async () => {
  tokens.set({ access_token: "old", refresh_token: "ref" });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    const u = String(url);
    if (u.endsWith("/auth/refresh")) {
      return jsonResponse({ access_token: "new", refresh_token: "ref2" });
    }
    const auth = new Headers(init?.headers).get("Authorization");
    return auth === "Bearer new" ? jsonResponse({ ok: true }) : jsonResponse({}, 401);
  });
  const res = await apiFetch("/messages/sent");
  expect(res).toEqual({ ok: true });
  expect(tokens.access).toBe("new");
  // protected call (401) + refresh + retry = 3 fetches
  expect(fetchMock).toHaveBeenCalledTimes(3);
});

test("concurrent 401s share ONE refresh and both retry with the new token", async () => {
  tokens.set({ access_token: "old", refresh_token: "ref" });
  let refreshCalls = 0;
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    const u = String(url);
    if (u.endsWith("/auth/refresh")) {
      refreshCalls += 1;
      return jsonResponse({ access_token: "new", refresh_token: "ref2" });
    }
    const auth = new Headers(init?.headers).get("Authorization");
    return auth === "Bearer new" ? jsonResponse({ ok: true }) : jsonResponse({}, 401);
  });
  const [a, b] = await Promise.all([
    apiFetch("/messages/sent"),
    apiFetch("/messages/inbox"),
  ]);
  expect(refreshCalls).toBe(1);
  expect(a).toEqual({ ok: true });
  expect(b).toEqual({ ok: true });
  // 2 protected (401) + 1 shared refresh + 2 retries
  expect(fetchMock).toHaveBeenCalledTimes(5);
});

test("retries without refreshing if the token already changed mid-flight", async () => {
  tokens.set({ access_token: "old", refresh_token: "ref" });
  let refreshCalls = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    const u = String(url);
    if (u.endsWith("/auth/refresh")) {
      refreshCalls += 1;
      return jsonResponse({ access_token: "x", refresh_token: "y" });
    }
    const auth = new Headers(init?.headers).get("Authorization");
    if (auth === "Bearer new") return jsonResponse({ ok: true });
    // The first (old-token) request 401s; meanwhile "another request" rotated
    // the token, so apiFetch should retry with the new one, not refresh again.
    tokens.set({ access_token: "new", refresh_token: "ref2" });
    return jsonResponse({}, 401);
  });
  const res = await apiFetch("/messages/sent");
  expect(res).toEqual({ ok: true });
  expect(refreshCalls).toBe(0);
});

test("refresh failure clears tokens and signals logout, no loop", async () => {
  tokens.set({ access_token: "old", refresh_token: "ref" });
  const logout = vi.fn();
  onLogout(logout);
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    if (String(url).endsWith("/auth/refresh")) return jsonResponse({}, 401);
    return jsonResponse({}, 401);
  });
  await expect(apiFetch("/messages/sent")).rejects.toThrow();
  expect(tokens.access).toBeNull();
  expect(logout).toHaveBeenCalled();
  // protected(401) + refresh(401) only — no retry storm
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test("does not attempt refresh for auth endpoints", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({}, 401));
  await expect(apiFetch("/auth/login", { method: "POST", body: "{}" })).rejects.toThrow();
  expect(fetchMock).toHaveBeenCalledTimes(1); // no refresh
});
