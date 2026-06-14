import { useEffect, useState, type ReactNode } from "react";
import * as authApi from "../api/auth";
import type { User } from "../api/auth";
import { onLogout } from "../api/client";
import { tokens } from "../api/tokens";
import { AuthContext, type AuthValue, type Status } from "./useAuth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // Initialize synchronously so we don't setState in the effect body for the
  // no-token path (satisfies react-hooks/set-state-in-effect).
  const [status, setStatus] = useState<Status>(tokens.access ? "loading" : "anonymous");

  function applyUser(u: User) { setUser(u); setStatus("authenticated"); }
  function goAnon() { setUser(null); setStatus("anonymous"); }

  useEffect(() => {
    let active = true; // guard against setState after unmount (StrictMode remount)
    const unsubscribe = onLogout(() => { tokens.clear(); if (active) goAnon(); });
    if (tokens.access) {
      authApi
        .me()
        .then((u) => { if (active) applyUser(u); })
        .catch(() => { if (active) goAnon(); });
    }
    return () => { active = false; unsubscribe(); };
  }, []);

  const value: AuthValue = {
    user,
    status,
    login: async (e, p) => applyUser(await authApi.login(e, p)),
    register: async (u, e, p) => applyUser(await authApi.register(u, e, p)),
    loginWithGoogle: async (t) => applyUser(await authApi.googleLogin(t)),
    logout: () => { authApi.logout(); goAnon(); },
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
