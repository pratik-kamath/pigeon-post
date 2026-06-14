import { tokens } from "./tokens";

const AUTH_PATHS = ["/auth/login", "/auth/register", "/auth/google", "/auth/refresh"];

let logoutHandler: () => void = () => {};
export function onLogout(fn: () => void): () => void {
  logoutHandler = fn;
  return () => { if (logoutHandler === fn) logoutHandler = () => {}; };
}

let refreshPromise: Promise<boolean> | null = null;

function base() { return import.meta.env.VITE_API_BASE_URL ?? ""; }

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`API ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function rawFetch(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const access = tokens.access;
  if (access) headers.set("Authorization", `Bearer ${access}`);
  return fetch(base() + path, { ...init, headers });
}

/** Single shared refresh: concurrent 401s await the same promise. */
async function refresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const ref = tokens.refresh;
      if (!ref) return false;
      const resp = await fetch(base() + "/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: ref }),
      });
      if (!resp.ok) return false;
      tokens.set(await resp.json());
      return true;
    })().finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

/** fetch + JSON, with one auth-refresh retry on 401 (except auth endpoints). */
export async function apiFetch<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const accessUsed = tokens.access;
  let resp = await rawFetch(path, init);
  const isAuthPath = AUTH_PATHS.some((p) => path.startsWith(p));
  if (resp.status === 401 && !isAuthPath) {
    if (tokens.access && tokens.access !== accessUsed) {
      // Another in-flight request already refreshed — retry with the current
      // token instead of starting a second (wasteful) refresh.
      resp = await rawFetch(path, init);
    } else {
      const ok = await refresh();
      if (!ok) {
        tokens.clear();
        logoutHandler();
        throw new ApiError(401, await safeBody(resp));
      }
      resp = await rawFetch(path, init); // retry once with the new token
    }
  }
  if (!resp.ok) throw new ApiError(resp.status, await safeBody(resp));
  return resp.status === 204 ? (undefined as T) : ((await resp.json()) as T);
}

async function safeBody(resp: Response): Promise<unknown> {
  try { return await resp.json(); } catch { return null; }
}
