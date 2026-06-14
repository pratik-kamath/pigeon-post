import { apiFetch } from "./client";
import { tokens } from "./tokens";

interface TokenPair { access_token: string; refresh_token: string; }
export interface User { id: number; username: string; email: string; created_at: string; }

async function authed(path: string, payload: unknown): Promise<User> {
  const pair = await apiFetch<TokenPair>(path, { method: "POST", body: JSON.stringify(payload) });
  tokens.set(pair);
  return me();
}

export const me = () => apiFetch<User>("/auth/me");
export const login = (email: string, password: string) =>
  authed("/auth/login", { email, password });
export const register = (username: string, email: string, password: string) =>
  authed("/auth/register", { username, email, password });
export const googleLogin = (idToken: string) =>
  authed("/auth/google", { id_token: idToken });
export function logout() { tokens.clear(); }
