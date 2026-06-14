# Frontend Phase 2 — Auth screens + living map + Send — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Phase 1 foundation into the playable dashboard — log in / register, then watch your sent pigeons fly across a pixel world map in real time, tap one for its status, and send new ones.

**Architecture:** Thin React screens over the Phase-1 primitives. Map math stays in pure, tested modules (`map/pigeon.ts` on top of `projection`/`flight`/`time`); React components (`WorldMap`, `PigeonSprite`, `CityMarker`, `Dashboard`, `SendDialog`, `AuthScreen`) are thin shells. Live updates = poll `GET /messages/sent` (~10s) + `requestAnimationFrame` re-render from timestamps; new sends insert optimistically. Pokémon pixel-RPG craft (wing-flap, boot reveal, launch flourish) via CSS, all behind the `prefers-reduced-motion` guard.

**Tech Stack:** Vite + React 19 + TS, Vitest + React Testing Library (existing). No new deps.

**Spec:** `docs/superpowers/specs/2026-06-14-frontend-dashboard-mvp-design.md` (this implements **Phase 2** of its Build order; Google sign-in + Playwright smoke + docs are Phase 3).

**Conventions:** All commands from `frontend/`. `npm test` (Vitest), `npm run lint`, `npm run build` must each stay green at every commit. End commit messages with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Phase-1 primitives available:** `api/client.ts` (`apiFetch`, `ApiError`), `api/tokens.ts`, `api/auth.ts`, `auth/AuthContext.tsx` (`AuthProvider`), `auth/useAuth.ts` (`useAuth`), `components/{PixelButton,DialogueBox}.tsx`, `lib/time.ts` (`parseServerUtc`), `map/projection.ts` (`project`, `Point`), `map/flight.ts` (`progress`, `interpolate`), `styles/theme.css` (`--sea/--land/--city/--ink/--screen/--paper/--frame/--accent`, `.pk-box/.pk-button/.pk-screen/.scanlines`, reduced-motion guard).

---

## File Structure (this phase)

| File | Change | Responsibility |
|---|---|---|
| `src/api/messages.ts` | Create | `Message` type, `listSent()`, `sendMessage()` |
| `src/api/cities.ts` | Create | `City` type, `fetchCities()` |
| `src/lib/format.ts` | Create | `titleCaseCity`, `formatCountdown` |
| `src/map/pigeon.ts` | Create | `pigeonPosition()` — pure normalized position for a message |
| `src/map/worldGrid.ts` | Create | Land/water bitmap + `isLand`, dims |
| `src/screens/AuthScreen.tsx` | Create | Login/register forms (toggle) |
| `src/components/CityMarker.tsx` | Create | A projected city dot + label |
| `src/components/PigeonSprite.tsx` | Create | A positioned pixel pigeon (flap, status, click) |
| `src/map/WorldMap.tsx` | Create | Tile grid + markers + sprites + rAF tick + select |
| `src/lib/usePolling.ts` | Create | Interval poll hook (immediate + cleanup) |
| `src/components/SendDialog.tsx` | Create | Send form (validation, POST, optimistic, errors) |
| `src/screens/Dashboard.tsx` | Create | Compose map + dialogue + send; cities/poll wiring |
| `src/App.tsx` | Modify | anonymous → AuthScreen; authenticated → Dashboard |
| `src/styles/theme.css` | Modify | `.pk-map`, sprite/marker/animation CSS |

**Phase-2 done = green when:** `npm test`, `npm run lint`, `npm run build` all pass; logging in shows the map with any sent pigeons animating; Send adds one.

---

## Task 1: API modules — messages + cities

**Files:** Create `src/api/messages.ts`, `src/api/cities.ts`; Test `src/api/messages.test.ts`, `src/api/cities.test.ts`.

- [ ] **Step 1: Failing tests** — `src/api/messages.test.ts`:
```ts
import * as client from "./client";
import { listSent, sendMessage } from "./messages";

beforeEach(() => vi.restoreAllMocks());

test("listSent GETs /messages/sent", async () => {
  const spy = vi.spyOn(client, "apiFetch").mockResolvedValue([] as unknown as never);
  await listSent();
  expect(spy).toHaveBeenCalledWith("/messages/sent");
});

test("sendMessage POSTs the payload to /messages", async () => {
  const spy = vi.spyOn(client, "apiFetch").mockResolvedValue({ id: 1 } as unknown as never);
  await sendMessage({ recipient: "alex", origin: "new york", destination: "tokyo", body: "hi" });
  expect(spy).toHaveBeenCalledWith(
    "/messages",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ recipient: "alex", origin: "new york", destination: "tokyo", body: "hi" }),
    })
  );
});
```
`src/api/cities.test.ts`:
```ts
import * as client from "./client";
import { fetchCities } from "./cities";

test("fetchCities GETs /cities", async () => {
  const spy = vi.spyOn(client, "apiFetch").mockResolvedValue([] as unknown as never);
  await fetchCities();
  expect(spy).toHaveBeenCalledWith("/cities");
});
```

- [ ] **Step 2: Run, expect FAIL** (`cd frontend && npm test`) — modules missing.

- [ ] **Step 3: Implement** — `src/api/messages.ts`:
```ts
import { apiFetch } from "./client";

export type MessageStatus = "in_flight" | "delivered" | "lost";

export interface Message {
  id: number;
  sender: string;
  recipient: string;
  body: string;
  origin: string;
  destination: string;
  distance_km: number;
  status: MessageStatus;
  sent_at: string;
  arrival_at: string;
  resolved_at: string | null;
}

export interface SendPayload {
  recipient: string;
  origin: string;
  destination: string;
  body: string;
}

export const listSent = () => apiFetch<Message[]>("/messages/sent");

export const sendMessage = (payload: SendPayload) =>
  apiFetch<Message>("/messages", { method: "POST", body: JSON.stringify(payload) });
```
`src/api/cities.ts`:
```ts
import { apiFetch } from "./client";

export interface City {
  name: string;
  lat: number;
  lon: number;
}

export const fetchCities = () => apiFetch<City[]>("/cities");
```

- [ ] **Step 4: Run, expect PASS.** Then `npm run lint` clean.

- [ ] **Step 5: Commit**
```bash
cd /Users/pratikkamath/Github-Projects/pigeon-post
git add frontend/src/api/messages.ts frontend/src/api/cities.ts frontend/src/api/messages.test.ts frontend/src/api/cities.test.ts
git commit -m "feat: messages + cities API modules

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: format helpers

**Files:** Create `src/lib/format.ts`; Test `src/lib/format.test.ts`.

- [ ] **Step 1: Failing test** — `src/lib/format.test.ts`:
```ts
import { titleCaseCity, formatCountdown } from "./format";

test("titleCaseCity capitalizes each word", () => {
  expect(titleCaseCity("san francisco")).toBe("San Francisco");
  expect(titleCaseCity("tokyo")).toBe("Tokyo");
});

test("formatCountdown formats hours+minutes, minutes-only, sub-minute, and arrival", () => {
  expect(formatCountdown(2 * 3600_000 + 5 * 60_000)).toBe("2h 5m");
  expect(formatCountdown(5 * 60_000)).toBe("5m");
  expect(formatCountdown(30_000)).toBe("<1m");
  expect(formatCountdown(0)).toBe("arriving");
  expect(formatCountdown(-1000)).toBe("arriving");
});
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/lib/format.ts`:
```ts
export function titleCaseCity(name: string): string {
  return name.replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatCountdown(ms: number): string {
  if (ms <= 0) return "arriving";
  if (ms < 60_000) return "<1m";
  const totalMin = Math.floor(ms / 60_000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
```

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Commit**
```bash
git add frontend/src/lib/format.ts frontend/src/lib/format.test.ts
git commit -m "feat: title-case + countdown formatters

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `pigeonPosition` (pure map math)

**Files:** Create `src/map/pigeon.ts`; Test `src/map/pigeon.test.ts`.

- [ ] **Step 1: Failing test** — `src/map/pigeon.test.ts`:
```ts
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
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/map/pigeon.ts`:
```ts
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
```

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Commit**
```bash
git add frontend/src/map/pigeon.ts frontend/src/map/pigeon.test.ts
git commit -m "feat: pigeonPosition (resolve + project + interpolate)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Auth screen (login + register) + app gate

**Files:** Create `src/screens/AuthScreen.tsx`; Modify `src/App.tsx`, `src/styles/theme.css`; Test `src/screens/AuthScreen.test.tsx`.

- [ ] **Step 1: Failing test** — `src/screens/AuthScreen.test.tsx`:
```ts
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthScreen } from "./AuthScreen";
import * as useAuthMod from "../auth/useAuth";

function mockAuth(over: Partial<ReturnType<typeof useAuthMod.useAuth>> = {}) {
  vi.spyOn(useAuthMod, "useAuth").mockReturnValue({
    user: null, status: "anonymous",
    login: vi.fn().mockResolvedValue(undefined),
    register: vi.fn().mockResolvedValue(undefined),
    loginWithGoogle: vi.fn(), logout: vi.fn(),
    ...over,
  });
}

beforeEach(() => vi.restoreAllMocks()); // isolate the useAuth spy between tests

test("logs in with entered credentials", async () => {
  const login = vi.fn().mockResolvedValue(undefined);
  mockAuth({ login });
  render(<AuthScreen />);
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
  await userEvent.type(screen.getByLabelText(/password/i), "password123");
  await userEvent.click(screen.getByRole("button", { name: /log in/i }));
  expect(login).toHaveBeenCalledWith("a@b.com", "password123");
});

test("shows an error when login is rejected", async () => {
  mockAuth({ login: vi.fn().mockRejectedValue(new Error("nope")) });
  render(<AuthScreen />);
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
  await userEvent.type(screen.getByLabelText(/password/i), "x");
  await userEvent.click(screen.getByRole("button", { name: /log in/i }));
  await waitFor(() => expect(screen.getByText(/couldn't log in/i)).toBeInTheDocument());
});

test("can switch to register and submit username+email+password", async () => {
  const register = vi.fn().mockResolvedValue(undefined);
  mockAuth({ register });
  render(<AuthScreen />);
  await userEvent.click(screen.getByRole("button", { name: /create account/i }));
  await userEvent.type(screen.getByLabelText(/username/i), "pratik");
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
  await userEvent.type(screen.getByLabelText(/password/i), "password123");
  await userEvent.click(screen.getByRole("button", { name: /^register$/i }));
  expect(register).toHaveBeenCalledWith("pratik", "a@b.com", "password123");
});
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/screens/AuthScreen.tsx`:
```tsx
import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/useAuth";
import { PixelButton } from "../components/PixelButton";

type Mode = "login" | "register";

export function AuthScreen() {
  const { login, register } = useAuth();
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
```
Append to `src/styles/theme.css`:
```css
.auth-screen { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px; }
.auth-card { width: min(360px, 92vw); }
.auth-title { font-family: var(--font-head); font-size: 16px; color: var(--paper); text-align: center; letter-spacing: 2px; margin: 4px 0 12px; text-shadow: 2px 2px 0 var(--ink); }
.auth-form { display: flex; flex-direction: column; gap: 10px; }
.auth-form label { display: flex; flex-direction: column; gap: 4px; font-size: 18px; }
.auth-form input { font-family: var(--font-body); font-size: 18px; padding: 6px 8px; border: 2px solid var(--ink); background: #fff; }
.auth-error { color: var(--accent); font-size: 16px; margin: 0; }
.auth-toggle { background: none; border: none; color: var(--paper); font-family: var(--font-body); font-size: 16px; margin-top: 10px; cursor: pointer; text-decoration: underline; width: 100%; }
```

- [ ] **Step 4: Wire the gate** — in `src/App.tsx`, replace the anonymous branch so it renders `<AuthScreen />` and the authenticated branch renders a temporary placeholder until Task 10 swaps in the Dashboard. Update `App.tsx`:
```tsx
import { AuthProvider } from "./auth/AuthContext";
import { useAuth } from "./auth/useAuth";
import { AuthScreen } from "./screens/AuthScreen";

function Shell() {
  const { status, user } = useAuth();
  if (status === "loading") return <div>Loading…</div>;
  if (status === "anonymous") return <AuthScreen />;
  return <div>Welcome, {user!.username}</div>;
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
```
Update `src/App.test.tsx`'s assertion: the logged-out shell now shows the auth screen, not the placeholder text. Change the stale-session test's final assertion to:
```tsx
await waitFor(() => expect(screen.getByText("PIGEON POST")).toBeInTheDocument());
```
(That non-breaking space matches the `PIGEON&nbsp;POST` title; alternatively assert `screen.getByRole("button", { name: /log in/i })`.)

- [ ] **Step 5: Run** `npm test` (PASS) + `npm run lint` + `npm run build` (clean).

- [ ] **Step 6: Commit**
```bash
git add frontend/src/screens/AuthScreen.tsx frontend/src/screens/AuthScreen.test.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/styles/theme.css
git commit -m "feat: pixel login/register auth screen + app gate

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: world grid (land/water bitmap)

**Files:** Create `src/map/worldGrid.ts`; Test `src/map/worldGrid.test.ts`.

- [ ] **Step 1: Failing test** — `src/map/worldGrid.test.ts`:
```ts
import { GRID_COLS, GRID_ROWS, isLand } from "./worldGrid";

test("grid has sane dimensions", () => {
  expect(GRID_COLS).toBeGreaterThan(20);
  expect(GRID_ROWS).toBeGreaterThan(10);
});

test("isLand returns a boolean and the poles/oceans are sea", () => {
  expect(typeof isLand(0, 0)).toBe("boolean");
  // far south-pacific cell (bottom-left-ish) is ocean
  expect(isLand(1, GRID_ROWS - 1)).toBe(false);
});

test("there is some land and some sea", () => {
  let land = 0, sea = 0;
  for (let r = 0; r < GRID_ROWS; r++) {
    for (let c = 0; c < GRID_COLS; c++) {
      if (isLand(c, r)) land++;
      else sea++;
    }
  }
  expect(land).toBeGreaterThan(0);
  expect(sea).toBeGreaterThan(0);
});
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/map/worldGrid.ts`. A coarse 36×18 equirectangular land mask (`#`=land, space=sea). It only needs to read as "continents," not be cartographically exact:
```ts
// Coarse equirectangular world (cols ≈ lon -180..180, rows ≈ lat 90..-90).
// '#' = land, ' ' = sea. Intentionally blocky — it's a pixel map. Rows are
// padded to equal width, so the art needn't be hand-counted to exact length.
const RAW = [
  "                                     ",
  "      ####        #####  #######     ",
  "   ###########   ###########  ##     ",
  "    ##########   ##########           ",
  "      ########   #########           ",
  "        #####     ####  ####          ",
  "         ###       ##########         ",
  "         ###        #########         ",
  "         ##          ########         ",
  "         ##           ######          ",
  "         ###          #####           ",
  "          ##           ###      ##    ",
  "          ##           ###      ##    ",
  "           #           ##             ",
  "                       #              ",
  "             ####                     ",
  "              ##                      ",
  "                                     ",
];
const WIDTH = Math.max(...RAW.map((r) => r.length));
const ROWS = RAW.map((r) => r.padEnd(WIDTH, " "));

export const GRID_ROWS = ROWS.length;
export const GRID_COLS = WIDTH;

export function isLand(col: number, row: number): boolean {
  if (row < 0 || row >= GRID_ROWS || col < 0 || col >= GRID_COLS) return false;
  return ROWS[row][col] === "#";
}
```
> The art is ASCII only (`#` and space). `padEnd` normalizes row widths, so a row that's a character short won't break the grid; just keep rows roughly the same length and ASCII.

- [ ] **Step 4: Run, expect PASS.** (If `GRID_COLS`/row-length assertion trips, pad rows to equal length.)

- [ ] **Step 5: Commit**
```bash
git add frontend/src/map/worldGrid.ts frontend/src/map/worldGrid.test.ts
git commit -m "feat: coarse pixel world land/water grid

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: CityMarker + PigeonSprite (presentational)

**Files:** Create `src/components/CityMarker.tsx`, `src/components/PigeonSprite.tsx`; Modify `src/styles/theme.css`; Test `src/components/PigeonSprite.test.tsx`.

- [ ] **Step 1: Failing test** — `src/components/PigeonSprite.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PigeonSprite } from "./PigeonSprite";
import type { Message } from "../api/messages";

const base: Message = {
  id: 7, sender: "me", recipient: "alex", body: "hi", origin: "new york",
  destination: "tokyo", distance_km: 1, status: "in_flight",
  sent_at: "2026-06-14T00:00:00", arrival_at: "2026-06-14T10:00:00", resolved_at: null,
};

test("renders at the given position and fires onSelect", async () => {
  const onSelect = vi.fn();
  render(<PigeonSprite message={base} xPct={50} yPct={25} selected={false} onSelect={onSelect} />);
  const btn = screen.getByRole("button", { name: /pigeon to alex/i });
  expect(btn).toHaveStyle({ left: "50%", top: "25%" });
  await userEvent.click(btn);
  expect(onSelect).toHaveBeenCalledWith(7);
});

test("lost pigeons get the lost modifier class", () => {
  render(<PigeonSprite message={{ ...base, status: "lost" }} xPct={10} yPct={10} selected={false} onSelect={() => {}} />);
  expect(screen.getByRole("button", { name: /pigeon to alex/i }).className).toMatch(/pigeon--lost/);
});
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/components/CityMarker.tsx`:
```tsx
import { titleCaseCity } from "../lib/format";

export function CityMarker({ name, xPct, yPct }: { name: string; xPct: number; yPct: number }) {
  return (
    <div className="city" style={{ left: `${xPct}%`, top: `${yPct}%` }}>
      <span className="city-dot" />
      <span className="city-label">{titleCaseCity(name)}</span>
    </div>
  );
}
```
`src/components/PigeonSprite.tsx`:
```tsx
import type { Message } from "../api/messages";

interface Props {
  message: Message;
  xPct: number;
  yPct: number;
  selected: boolean;
  onSelect: (id: number) => void;
}

export function PigeonSprite({ message, xPct, yPct, selected, onSelect }: Props) {
  const cls = [
    "pigeon",
    `pigeon--${message.status}`,
    selected ? "pigeon--selected" : "",
  ].join(" ").trim();
  return (
    <button
      type="button"
      className={cls}
      style={{ left: `${xPct}%`, top: `${yPct}%` }}
      onClick={() => onSelect(message.id)}
      aria-label={`Pigeon to ${message.recipient} (${message.status})`}
    >
      <span className="pigeon-wing" aria-hidden="true" />
    </button>
  );
}
```
Append to `src/styles/theme.css`:
```css
.city { position: absolute; transform: translate(-50%, -50%); pointer-events: none; }
.city-dot { display: block; width: 6px; height: 6px; background: var(--city); border: 2px solid var(--ink); }
.city-label { position: absolute; left: 8px; top: -2px; font-size: 12px; color: var(--ink); background: var(--paper); border: 1px solid var(--ink); padding: 0 2px; white-space: nowrap; }

.pigeon { position: absolute; transform: translate(-50%, -50%); width: 14px; height: 14px; padding: 0; border: 2px solid var(--accent); background: var(--paper); cursor: pointer; clip-path: polygon(0 50%, 45% 0, 55% 0, 100% 50%, 55% 100%, 45% 100%); }
.pigeon--delivered { border-color: var(--land-edge); }
.pigeon--lost { opacity: 0.45; border-color: var(--ink); }
.pigeon--selected { outline: 2px solid var(--frame); outline-offset: 2px; }
.pigeon-wing { position: absolute; inset: 3px 4px; background: var(--accent); animation: flap 0.4s steps(2) infinite; }
.pigeon--in_flight { animation: bob 1.2s ease-in-out infinite; }
@keyframes flap { from { transform: scaleY(1); } to { transform: scaleY(0.4); } }
@keyframes bob { 0%,100% { margin-top: 0; } 50% { margin-top: -2px; } }
```
(The `prefers-reduced-motion` guard from Phase 1 already disables `flap`/`bob`.)

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/CityMarker.tsx frontend/src/components/PigeonSprite.tsx frontend/src/components/PigeonSprite.test.tsx frontend/src/styles/theme.css
git commit -m "feat: CityMarker + PigeonSprite (flap, status, select)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: usePolling hook

**Files:** Create `src/lib/usePolling.ts`; Test `src/lib/usePolling.test.ts`.

- [ ] **Step 1: Failing test** — `src/lib/usePolling.test.ts`:
```ts
import { renderHook } from "@testing-library/react";
import { usePolling } from "./usePolling";

afterEach(() => vi.useRealTimers()); // restore even if an assertion above throws

test("calls immediately, then on each interval, and stops on unmount", () => {
  vi.useFakeTimers();
  const fn = vi.fn();
  const { unmount } = renderHook(() => usePolling(fn, 1000));
  expect(fn).toHaveBeenCalledTimes(1);      // immediate
  vi.advanceTimersByTime(2500);
  expect(fn).toHaveBeenCalledTimes(3);      // +2 ticks
  unmount();
  vi.advanceTimersByTime(5000);
  expect(fn).toHaveBeenCalledTimes(3);      // stopped
});

test("uses the latest fn without resetting the interval", () => {
  vi.useFakeTimers();
  const first = vi.fn();
  const second = vi.fn();
  const { rerender } = renderHook(({ fn }) => usePolling(fn, 1000), {
    initialProps: { fn: first },
  });
  expect(first).toHaveBeenCalledTimes(1);
  rerender({ fn: second });           // swapping fn must NOT restart the interval
  vi.advanceTimersByTime(1000);
  expect(second).toHaveBeenCalledTimes(1);
  expect(first).toHaveBeenCalledTimes(1); // old fn no longer called
});
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/lib/usePolling.ts`:
```ts
import { useEffect, useRef } from "react";

/** Run `fn` immediately and then every `intervalMs`. Always calls the latest
 *  `fn` without resetting the timer when it changes. */
export function usePolling(fn: () => void, intervalMs: number) {
  const saved = useRef(fn);
  // Update the ref in an effect, not during render (react-hooks/refs).
  useEffect(() => { saved.current = fn; }, [fn]);
  useEffect(() => {
    const run = () => saved.current();
    run();
    const id = setInterval(run, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
}
```

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Commit**
```bash
git add frontend/src/lib/usePolling.ts frontend/src/lib/usePolling.test.ts
git commit -m "feat: usePolling hook

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: WorldMap (tiles + markers + sprites + flight paths + rAF tick)

**Files:** Create `src/map/flightSegments.ts`, `src/map/WorldMap.tsx`; Modify `src/styles/theme.css`, `src/test/setup.ts`; Test `src/map/flightSegments.test.ts`, `src/map/WorldMap.test.tsx`.

- [ ] **Step 1: Stub `requestAnimationFrame`** — jsdom may not provide it and `WorldMap` calls it. Append to `frontend/src/test/setup.ts` (guarded, so a real impl wins):
```ts
if (!globalThis.requestAnimationFrame) {
  globalThis.requestAnimationFrame = ((cb: FrameRequestCallback) =>
    setTimeout(() => cb(Date.now()), 16) as unknown as number) as typeof requestAnimationFrame;
  globalThis.cancelAnimationFrame = ((id: number) =>
    clearTimeout(id as unknown as ReturnType<typeof setTimeout>)) as typeof cancelAnimationFrame;
}
```

- [ ] **Step 2: `flightSegments` failing test** — `src/map/flightSegments.test.ts`:
```ts
import { flightSegments } from "./flightSegments";

test("a non-wrapping route is a single segment", () => {
  const segs = flightSegments({ x: 0.2, y: 0.4 }, { x: 0.5, y: 0.6 });
  expect(segs).toHaveLength(1);
  expect(segs[0]).toEqual({ x1: 0.2, y1: 0.4, x2: 0.5, y2: 0.6 });
});

test("an antimeridian route splits into two seam-crossing segments", () => {
  const segs = flightSegments({ x: 0.9, y: 0.3 }, { x: 0.1, y: 0.5 });
  expect(segs).toHaveLength(2);
  expect(segs[0].x2).toBe(1); // first exits the right edge
  expect(segs[1].x1).toBe(0); // second enters from the left edge
  expect(segs[0].y2).toBeCloseTo(segs[1].y1); // y continuous across the seam
});
```

- [ ] **Step 3: Run, expect FAIL.** Then implement `src/map/flightSegments.ts`:
```ts
import type { Point } from "./projection";

export interface Segment { x1: number; y1: number; x2: number; y2: number; }

/** One or two line segments (normalized space) for the dotted path a→b, taking
 *  the shorter direction and splitting across the antimeridian seam when it wraps. */
export function flightSegments(a: Point, b: Point): Segment[] {
  let dx = b.x - a.x;
  if (dx > 0.5) dx -= 1;
  else if (dx < -0.5) dx += 1;
  const endX = a.x + dx;
  if (endX >= 0 && endX <= 1) {
    return [{ x1: a.x, y1: a.y, x2: b.x, y2: b.y }];
  }
  const edge = endX > 1 ? 1 : 0;
  const tEdge = (edge - a.x) / dx;
  const yEdge = a.y + (b.y - a.y) * tEdge;
  return [
    { x1: a.x, y1: a.y, x2: edge, y2: yEdge },
    { x1: edge === 1 ? 0 : 1, y1: yEdge, x2: b.x, y2: b.y },
  ];
}
```
Run `flightSegments.test.ts`, expect PASS.

- [ ] **Step 4: WorldMap failing test** — `src/map/WorldMap.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorldMap } from "./WorldMap";
import type { City } from "../api/cities";
import type { Message } from "../api/messages";

const cities: City[] = [
  { name: "new york", lat: 40.7128, lon: -74.006 },
  { name: "tokyo", lat: 35.6762, lon: 139.6503 },
];
const messages: Message[] = [
  { id: 1, sender: "me", recipient: "alex", body: "hi", origin: "new york",
    destination: "tokyo", distance_km: 1, status: "in_flight",
    sent_at: "2026-06-14T00:00:00", arrival_at: "2999-01-01T00:00:00", resolved_at: null },
];

test("renders city markers, a sprite, and a dotted flight path", () => {
  const { container } = render(
    <WorldMap cities={cities} messages={messages} selectedId={null} onSelect={() => {}} />
  );
  expect(screen.getByText("New York")).toBeInTheDocument();
  expect(screen.getByText("Tokyo")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /pigeon to alex/i })).toBeInTheDocument();
  expect(container.querySelectorAll(".flight-paths line").length).toBeGreaterThan(0);
});

test("clicking a pigeon selects it", async () => {
  const onSelect = vi.fn();
  render(<WorldMap cities={cities} messages={messages} selectedId={null} onSelect={onSelect} />);
  await userEvent.click(screen.getByRole("button", { name: /pigeon to alex/i }));
  expect(onSelect).toHaveBeenCalledWith(1);
});

test("skips pigeons whose cities are unknown", () => {
  const bad = [{ ...messages[0], id: 2, origin: "atlantis" }];
  render(<WorldMap cities={cities} messages={bad} selectedId={null} onSelect={() => {}} />);
  expect(screen.queryByRole("button", { name: /pigeon to alex/i })).toBeNull();
});
```

- [ ] **Step 5: Run, expect FAIL.** Then implement `src/map/WorldMap.tsx`:
```tsx
import { useEffect, useMemo, useRef, useState } from "react";
import type { City } from "../api/cities";
import type { Message } from "../api/messages";
import { project } from "./projection";
import { pigeonPosition } from "./pigeon";
import { flightSegments } from "./flightSegments";
import { GRID_COLS, GRID_ROWS, isLand } from "./worldGrid";
import { CityMarker } from "../components/CityMarker";
import { PigeonSprite } from "../components/PigeonSprite";

interface Props {
  cities: City[];
  messages: Message[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export function WorldMap({ cities, messages, selectedId, onSelect }: Props) {
  const [now, setNow] = useState(() => Date.now());

  // Animate in-flight pigeons by advancing `now` each frame.
  const hasInFlight = messages.some((m) => m.status === "in_flight");
  const raf = useRef(0);
  useEffect(() => {
    if (!hasInFlight) return;
    const tick = () => { setNow(Date.now()); raf.current = requestAnimationFrame(tick); };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [hasInFlight]);

  const cityByName = useMemo(() => new Map(cities.map((c) => [c.name, c])), [cities]);

  const tiles = useMemo(() => {
    const cells: { c: number; r: number }[] = [];
    for (let r = 0; r < GRID_ROWS; r++)
      for (let c = 0; c < GRID_COLS; c++) if (isLand(c, r)) cells.push({ c, r });
    return cells;
  }, []);

  return (
    <div className="pk-map scanlines" role="region" aria-label="World map of pigeons in flight">
      {tiles.map(({ c, r }) => (
        <span
          key={`${c}-${r}`}
          className="tile"
          style={{
            left: `${(c / GRID_COLS) * 100}%`,
            top: `${(r / GRID_ROWS) * 100}%`,
            width: `${100 / GRID_COLS}%`,
            height: `${100 / GRID_ROWS}%`,
          }}
        />
      ))}
      <svg className="flight-paths" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {messages.flatMap((m) => {
          if (m.status !== "in_flight") return [];
          const o = cityByName.get(m.origin);
          const d = cityByName.get(m.destination);
          if (!o || !d) return [];
          return flightSegments(project(o.lat, o.lon), project(d.lat, d.lon)).map((s, i) => (
            <line
              key={`${m.id}-${i}`}
              x1={s.x1 * 100} y1={s.y1 * 100} x2={s.x2 * 100} y2={s.y2 * 100}
              stroke="var(--paper)" strokeWidth={0.5} strokeDasharray="1.5 1.5"
            />
          ));
        })}
      </svg>
      {cities.map((city) => {
        const p = project(city.lat, city.lon);
        return <CityMarker key={city.name} name={city.name} xPct={p.x * 100} yPct={p.y * 100} />;
      })}
      {messages.map((m) => {
        const p = pigeonPosition(m, cityByName, now);
        if (!p) return null;
        return (
          <PigeonSprite
            key={m.id}
            message={m}
            xPct={p.x * 100}
            yPct={p.y * 100}
            selected={m.id === selectedId}
            onSelect={onSelect}
          />
        );
      })}
    </div>
  );
}
```
Append to `src/styles/theme.css`:
```css
.pk-map { position: relative; width: 100%; aspect-ratio: 2 / 1; background: var(--sea); border: 3px solid var(--ink); overflow: hidden; }
.tile { position: absolute; background: var(--land); }
.flight-paths { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
```
> Tiles + paths are positioned by percentage so the map scales responsively while staying blocky. `aspect-ratio: 2/1` matches the equirectangular projection. The SVG uses `preserveAspectRatio="none"` so its `0..100` coordinate space stretches to the map box.

- [ ] **Step 6: Run, expect PASS.** (jsdom now has the rAF stub from Step 1; the in-flight test uses a far-future `arrival_at` so the sprite sits near the origin and renders regardless of animation.)

- [ ] **Step 7: Commit**
```bash
git add frontend/src/map/flightSegments.ts frontend/src/map/flightSegments.test.ts frontend/src/map/WorldMap.tsx frontend/src/map/WorldMap.test.tsx frontend/src/styles/theme.css frontend/src/test/setup.ts
git commit -m "feat: WorldMap — tiles, markers, dotted flight paths, animated sprites

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: SendDialog

**Files:** Create `src/lib/errors.ts`, `src/components/SendDialog.tsx`; Modify `src/styles/theme.css`; Test `src/lib/errors.test.ts`, `src/components/SendDialog.test.tsx`.

- [ ] **Step 1: error helper** — `src/lib/errors.test.ts`:
```ts
import { ApiError } from "../api/client";
import { errorMessage } from "./errors";

test("string detail is returned", () => {
  expect(errorMessage(new ApiError(404, { detail: "recipient not found" }), "fb")).toBe("recipient not found");
});

test("Pydantic array detail returns the first msg (never an object)", () => {
  const err = new ApiError(422, { detail: [{ loc: ["body", "recipient"], msg: "must not be blank", type: "value_error" }] });
  expect(errorMessage(err, "fb")).toBe("must not be blank");
});

test("anything else returns the fallback", () => {
  expect(errorMessage(new Error("boom"), "fb")).toBe("fb");
});
```
Run (FAIL), then create `src/lib/errors.ts`:
```ts
import { ApiError } from "../api/client";

/** A user-facing string from a thrown API error. FastAPI/Pydantic 422s put an
 *  ARRAY of objects in `detail`; route errors put a string. Never returns a
 *  non-string (rendering one would crash React). */
export function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.body && typeof err.body === "object") {
    const detail = (err.body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: unknown } | undefined;
      if (first && typeof first.msg === "string") return first.msg;
    }
  }
  return fallback;
}
```
Run (PASS).

- [ ] **Step 2: SendDialog failing test** — `src/components/SendDialog.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SendDialog } from "./SendDialog";
import * as messagesApi from "../api/messages";
import { ApiError } from "../api/client";
import type { City } from "../api/cities";

const cities: City[] = [
  { name: "new york", lat: 40.7, lon: -74 },
  { name: "tokyo", lat: 35.6, lon: 139.6 },
];

beforeEach(() => vi.restoreAllMocks());

function fill(recipient = "alex") {
  return (async () => {
    await userEvent.type(screen.getByLabelText(/recipient/i), recipient);
    await userEvent.selectOptions(screen.getByLabelText(/from/i), "new york");
    await userEvent.selectOptions(screen.getByLabelText(/to/i), "tokyo");
    await userEvent.type(screen.getByLabelText(/message/i), "wish you were here");
  })();
}

test("blocks same origin and destination", async () => {
  render(<SendDialog cities={cities} onClose={() => {}} onSent={() => {}} />);
  await userEvent.type(screen.getByLabelText(/recipient/i), "alex");
  await userEvent.selectOptions(screen.getByLabelText(/from/i), "tokyo");
  await userEvent.selectOptions(screen.getByLabelText(/to/i), "tokyo");
  await userEvent.type(screen.getByLabelText(/message/i), "hi");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(screen.getByText(/must differ/i)).toBeInTheDocument();
});

test("sends and reports the created message", async () => {
  const created = { id: 99 } as messagesApi.Message;
  const spy = vi.spyOn(messagesApi, "sendMessage").mockResolvedValue(created);
  const onSent = vi.fn();
  render(<SendDialog cities={cities} onClose={() => {}} onSent={onSent} />);
  await fill();
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  await waitFor(() => expect(onSent).toHaveBeenCalledWith(created));
  expect(spy).toHaveBeenCalledWith({ recipient: "alex", origin: "new york", destination: "tokyo", body: "wish you were here" });
});

test("surfaces an unknown-recipient 404", async () => {
  vi.spyOn(messagesApi, "sendMessage").mockRejectedValue(new ApiError(404, { detail: "recipient not found" }));
  render(<SendDialog cities={cities} onClose={() => {}} onSent={() => {}} />);
  await fill("ghost");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  await waitFor(() => expect(screen.getByText(/recipient not found/i)).toBeInTheDocument());
});

test("blocks an empty recipient before calling the API", async () => {
  const spy = vi.spyOn(messagesApi, "sendMessage");
  render(<SendDialog cities={cities} onClose={() => {}} onSent={() => {}} />);
  await userEvent.selectOptions(screen.getByLabelText(/from/i), "new york");
  await userEvent.selectOptions(screen.getByLabelText(/to/i), "tokyo");
  await userEvent.type(screen.getByLabelText(/message/i), "hi");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(screen.getByText(/required/i)).toBeInTheDocument();
  expect(spy).not.toHaveBeenCalled();
});

test("a 422 with array detail shows a message without crashing", async () => {
  vi.spyOn(messagesApi, "sendMessage").mockRejectedValue(
    new ApiError(422, { detail: [{ loc: ["body", "body"], msg: "must not be blank", type: "value_error" }] })
  );
  render(<SendDialog cities={cities} onClose={() => {}} onSent={() => {}} />);
  await fill();
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  await waitFor(() => expect(screen.getByText(/must not be blank/i)).toBeInTheDocument());
});
```

- [ ] **Step 3: Run, expect FAIL.**

- [ ] **Step 4: Implement** — `src/components/SendDialog.tsx`:
```tsx
import { useState, type FormEvent } from "react";
import type { City } from "../api/cities";
import { sendMessage, type Message } from "../api/messages";
import { errorMessage } from "../lib/errors";
import { titleCaseCity } from "../lib/format";
import { PixelButton } from "./PixelButton";

interface Props {
  cities: City[];
  onClose: () => void;
  onSent: (m: Message) => void;
}

export function SendDialog({ cities, onClose, onSent }: Props) {
  const [recipient, setRecipient] = useState("");
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!recipient.trim() || !body.trim()) {
      setError("Recipient and message are required.");
      return;
    }
    if (!origin || !destination || origin === destination) {
      setError("Origin and destination must differ.");
      return;
    }
    setBusy(true);
    try {
      const msg = await sendMessage({ recipient: recipient.trim(), origin, destination, body });
      onSent(msg);
      onClose();
    } catch (err) {
      // errorMessage safely stringifies even a Pydantic array `detail`.
      setError(errorMessage(err, "Couldn't send the pigeon. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="pk-box send-dialog" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2 className="send-title">SEND A PIGEON</h2>
        <label>Recipient
          <input value={recipient} onChange={(e) => setRecipient(e.target.value)} />
        </label>
        <label>From
          <select value={origin} onChange={(e) => setOrigin(e.target.value)}>
            <option value="">—</option>
            {cities.map((c) => <option key={c.name} value={c.name}>{titleCaseCity(c.name)}</option>)}
          </select>
        </label>
        <label>To
          <select value={destination} onChange={(e) => setDestination(e.target.value)}>
            <option value="">—</option>
            {cities.map((c) => <option key={c.name} value={c.name}>{titleCaseCity(c.name)}</option>)}
          </select>
        </label>
        <label>Message
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} />
        </label>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <div className="send-actions">
          <PixelButton type="submit" disabled={busy}>SEND</PixelButton>
          <button type="button" className="auth-toggle" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </div>
  );
}
```
Append to `src/styles/theme.css`:
```css
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.55); display: flex; align-items: center; justify-content: center; padding: 16px; z-index: 10; }
.send-dialog { width: min(360px, 92vw); display: flex; flex-direction: column; gap: 8px; }
.send-title { font-family: var(--font-head); font-size: 12px; margin: 0 0 4px; }
.send-dialog label { display: flex; flex-direction: column; gap: 3px; font-size: 16px; }
.send-dialog input, .send-dialog select, .send-dialog textarea { font-family: var(--font-body); font-size: 16px; padding: 5px; border: 2px solid var(--ink); }
.send-actions { display: flex; align-items: center; gap: 12px; margin-top: 4px; }
```

- [ ] **Step 5: Run, expect PASS.**

- [ ] **Step 6: Commit**
```bash
git add frontend/src/lib/errors.ts frontend/src/lib/errors.test.ts frontend/src/components/SendDialog.tsx frontend/src/components/SendDialog.test.tsx frontend/src/styles/theme.css
git commit -m "feat: SendDialog (validation, POST, safe error surfacing)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Dashboard — compose it all + wire into App

**Files:** Create `src/lib/sentStore.ts`, `src/screens/Dashboard.tsx`; Modify `src/App.tsx`, `src/styles/theme.css`; Test `src/lib/sentStore.test.ts`, `src/screens/Dashboard.test.tsx`.

- [ ] **Step 1: sent-message merge store** — `src/lib/sentStore.test.ts`:
```ts
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
```
Run (FAIL), then create `src/lib/sentStore.ts`:
```ts
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
```
Run (PASS).

- [ ] **Step 2: Dashboard failing test** — `src/screens/Dashboard.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Dashboard } from "./Dashboard";
import * as citiesApi from "../api/cities";
import * as messagesApi from "../api/messages";
import * as useAuthMod from "../auth/useAuth";

const cities = [
  { name: "new york", lat: 40.7128, lon: -74.006 },
  { name: "tokyo", lat: 35.6762, lon: 139.6503 },
];
const sent = [{
  id: 1, sender: "me", recipient: "alex", body: "hi", origin: "new york",
  destination: "tokyo", distance_km: 1, status: "in_flight" as const,
  sent_at: "2026-06-14T00:00:00", arrival_at: "2999-01-01T00:00:00", resolved_at: null,
}];

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(citiesApi, "fetchCities").mockResolvedValue(cities);
  vi.spyOn(messagesApi, "listSent").mockResolvedValue(sent);
  vi.spyOn(useAuthMod, "useAuth").mockReturnValue({
    user: { id: 1, username: "pratik", email: "p@x.com", created_at: "2026-01-01T00:00:00" },
    status: "authenticated", login: vi.fn(), register: vi.fn(),
    loginWithGoogle: vi.fn(), logout: vi.fn(),
  });
});

test("loads cities + sent pigeons and shows a sprite", async () => {
  render(<Dashboard />);
  await waitFor(() => expect(screen.getByRole("button", { name: /pigeon to alex/i })).toBeInTheDocument());
});

test("selecting a pigeon shows its status in the dialogue box", async () => {
  render(<Dashboard />);
  const sprite = await screen.findByRole("button", { name: /pigeon to alex/i });
  await userEvent.click(sprite);
  expect(screen.getByRole("status")).toHaveTextContent(/alex/i);
  expect(screen.getByRole("status")).toHaveTextContent(/tokyo/i);
});

test("SEND opens the dialog", async () => {
  render(<Dashboard />);
  await screen.findByRole("button", { name: /pigeon to alex/i });
  await userEvent.click(screen.getByRole("button", { name: /^send$/i }));
  expect(screen.getByText(/send a pigeon/i)).toBeInTheDocument();
});
```

- [ ] **Step 3: Run, expect FAIL.**

- [ ] **Step 4: Implement** — `src/screens/Dashboard.tsx`:
```tsx
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/useAuth";
import { fetchCities, type City } from "../api/cities";
import { listSent, type Message } from "../api/messages";
import { mergeServer, withOptimistic } from "../lib/sentStore";
import { usePolling } from "../lib/usePolling";
import { WorldMap } from "../map/WorldMap";
import { DialogueBox } from "../components/DialogueBox";
import { SendDialog } from "../components/SendDialog";
import { PixelButton } from "../components/PixelButton";
import { titleCaseCity, formatCountdown } from "../lib/format";
import { parseServerUtc } from "../lib/time";

function statusLine(m: Message): string {
  const to = `#${m.id} → ${m.recipient} @ ${titleCaseCity(m.destination)}`;
  if (m.status === "delivered") return `${to} · delivered ✓`;
  if (m.status === "lost") return `${to} · lost ✗`;
  const left = parseServerUtc(m.arrival_at).getTime() - Date.now();
  return `${to} · ${formatCountdown(left)} to arrival`;
}

export function Dashboard() {
  const { user, logout } = useAuth();
  const [cities, setCities] = useState<City[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [sendOpen, setSendOpen] = useState(false);
  // Optimistic sends not yet returned by a poll (see sentStore): a poll that
  // started before a send can't make the new pigeon vanish.
  const pendingRef = useRef<Message[]>([]);

  function applyPoll(server: Message[]) {
    const { pending, all } = mergeServer(pendingRef.current, server);
    pendingRef.current = pending;
    setMessages(all);
  }
  function addOptimistic(m: Message) {
    pendingRef.current = withOptimistic(pendingRef.current, m);
    setMessages((prev) => withOptimistic(prev, m));
  }

  useEffect(() => { fetchCities().then(setCities).catch(() => {}); }, []);
  usePolling(() => { listSent().then(applyPoll).catch(() => {}); }, 10_000);

  const selected = messages.find((m) => m.id === selectedId) ?? null;

  return (
    <div className="dashboard">
      <div className="pk-screen dashboard-screen scanlines boot">
        <div className="dash-bar">
          <span className="dash-title">PIGEON POST</span>
          <span className="dash-user">{user?.username}</span>
          <PixelButton onClick={() => setSendOpen(true)}>SEND</PixelButton>
          <button type="button" className="auth-toggle dash-logout" onClick={logout}>log out</button>
        </div>
        <WorldMap cities={cities} messages={messages} selectedId={selectedId} onSelect={setSelectedId} />
        <DialogueBox>
          {selected ? statusLine(selected)
            : messages.length === 0 ? "No pigeons aloft. Press SEND to launch one!"
            : "▸ Tap a pigeon to track it."}
        </DialogueBox>
      </div>
      {sendOpen && (
        <SendDialog
          cities={cities}
          onClose={() => setSendOpen(false)}
          onSent={addOptimistic}
        />
      )}
    </div>
  );
}
```
> `onSent` (`addOptimistic`) inserts the created message immediately and records it as pending; `mergeServer` keeps it visible until a poll reports it, then de-dupes — so it never flickers out even if a poll lands right after the send.

- [ ] **Step 5: Wire into App** — in `src/App.tsx`, change the authenticated branch to render the Dashboard:
```tsx
import { AuthProvider } from "./auth/AuthContext";
import { useAuth } from "./auth/useAuth";
import { AuthScreen } from "./screens/AuthScreen";
import { Dashboard } from "./screens/Dashboard";

function Shell() {
  const { status } = useAuth();
  if (status === "loading") return <div>Loading…</div>;
  if (status === "anonymous") return <AuthScreen />;
  return <Dashboard />;
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
```
(`App.test.tsx` from Task 4 still passes — it only renders the anonymous path; the authenticated path now needs the api mocks, which `App.test.tsx` doesn't trigger.)

Append to `src/styles/theme.css`:
```css
.dashboard { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px; }
.dashboard-screen { width: min(820px, 96vw); display: flex; flex-direction: column; gap: 8px; }
.dash-bar { display: flex; align-items: center; gap: 10px; }
.dash-title { font-family: var(--font-head); font-size: 10px; color: var(--paper); letter-spacing: 1px; }
.dash-user { font-size: 16px; color: var(--paper); margin-left: auto; }
.dash-logout { width: auto; }
.boot { animation: boot-in 0.5s ease-out both; }
@keyframes boot-in { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: scale(1); } }
```

- [ ] **Step 6: Run** `npm test` (all green), `npm run lint`, `npm run build` (clean).

- [ ] **Step 7: Manual smoke (optional, needs backend)** — `cd backend && FAST_FORWARD=5000 CORS_ORIGINS=http://localhost:5173 .venv/bin/uvicorn app.main:app` and `cd frontend && npm run dev`; register, send a pigeon, watch it cross the map; reload to confirm it persists and keeps moving.

- [ ] **Step 8: Commit**
```bash
git add frontend/src/lib/sentStore.ts frontend/src/lib/sentStore.test.ts frontend/src/screens/Dashboard.tsx frontend/src/screens/Dashboard.test.tsx frontend/src/App.tsx frontend/src/styles/theme.css
git commit -m "feat: Dashboard — live map, status dialogue, send (Phase 2 payoff)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification (Phase 2)

- [ ] `cd frontend && npm test` → all green; `npm run lint` → clean; `npm run build` → clean.
- [ ] `cd backend && .venv/bin/python -m pytest -q` → still 129 (backend untouched this phase).
- [ ] Manual: log in → see the map → send a pigeon → it appears and animates.
- [ ] Next: **Phase 3** plan — Google sign-in button (GIS), Playwright e2e smoke, README/CLAUDE.md docs, visual polish (launch flourish, hover pulses).
