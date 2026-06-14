import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import * as authApi from "../api/auth";
import type { User } from "../api/auth";
import { onLogout } from "../api/client";
import { tokens } from "../api/tokens";

type Status = "loading" | "anonymous" | "authenticated";

interface AuthValue {
  user: User | null;
  status: Status;
  login: (email: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthValue | null>(null);
export const useAuth = () => {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used within AuthProvider");
  return v;
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  function applyUser(u: User) { setUser(u); setStatus("authenticated"); }
  function goAnon() { setUser(null); setStatus("anonymous"); }

  useEffect(() => {
    const unsubscribe = onLogout(() => { tokens.clear(); goAnon(); });
    if (tokens.access) authApi.me().then(applyUser).catch(goAnon);
    else goAnon();
    return unsubscribe;
  }, []);

  const value: AuthValue = {
    user,
    status,
    login: async (e, p) => applyUser(await authApi.login(e, p)),
    register: async (u, e, p) => applyUser(await authApi.register(u, e, p)),
    loginWithGoogle: async (t) => applyUser(await authApi.googleLogin(t)),
    logout: () => { authApi.logout(); goAnon(); },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
