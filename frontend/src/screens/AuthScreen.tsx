import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/useAuth";
import { PixelButton } from "../components/PixelButton";
import { GoogleSignInButton } from "../components/GoogleSignInButton";

type Mode = "login" | "register";

export function AuthScreen() {
  const { login, register, loginWithGoogle } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password.trim() || (mode === "register" && !username.trim())) {
      setError("Please fill in all fields.");
      return;
    }
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(username, email, password);
    } catch {
      setError(mode === "login" ? "Couldn't log in — check your details." : "Couldn't register — that handle or email may be taken.");
    } finally {
      setBusy(false);
    }
  }

  async function onGoogleCredential(idToken: string) {
    setError(null);
    setBusy(true);
    try {
      await loginWithGoogle(idToken);
    } catch {
      setError("Google sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="pk-screen auth-card scanlines">
        <h1 className="auth-title">PIGEON&nbsp;POST</h1>
        <form className="pk-box auth-form" onSubmit={onSubmit}>
          {mode === "register" && (
            <label>Username
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
            </label>
          )}
          <label>Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </label>
          <label>Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          {error && <p className="auth-error" role="alert">{error}</p>}
          <PixelButton type="submit" disabled={busy}>
            {mode === "login" ? "LOG IN" : "REGISTER"}
          </PixelButton>
        </form>
        <GoogleSignInButton onCredential={onGoogleCredential} />
        <button
          type="button"
          className="auth-toggle"
          onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}
        >
          {mode === "login" ? "Create account" : "Have an account? Log in"}
        </button>
      </div>
    </div>
  );
}
