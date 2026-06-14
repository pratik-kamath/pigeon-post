# Frontend Phase 1 — Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lay the foundation for the pixel-RPG frontend — the two backend additions it needs (CORS, `GET /cities`), the Vite/React/TS scaffold with Vitest, the pixel visual system, the pure map/time libraries, the auth-aware API client (with the refresh mutex), and the auth context — all tested and green.

**Architecture:** A new `frontend/` (Vite + React + TS, Vitest + React Testing Library). Backend gains a public `GET /cities` and `CORSMiddleware`. The frontend's correctness-critical logic lives in small pure modules (`projection`, `flight`, `time`) and an API client whose `401 → refresh → retry` uses a single shared promise so concurrent requests can't trip the backend's refresh-token reuse detection.

**Tech Stack:** Backend: FastAPI/SQLAlchemy/pytest (existing). Frontend: Vite, React 18, TypeScript, Vitest, @testing-library/react, jsdom, @fontsource/{press-start-2p,vt323}.

**Spec:** `docs/superpowers/specs/2026-06-14-frontend-dashboard-mvp-design.md` (this plan implements **Phase 1** of its Build order). Phases 2–3 get their own plans.

**Conventions:** Run backend tests with `cd backend && .venv/bin/python -m pytest -q`. Run frontend commands from `frontend/` with `npm`. End every commit message with the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.

---

## File Structure (this phase)

| File | Change | Responsibility |
|---|---|---|
| `backend/app/schemas.py` | Modify | Add `CityOut`. |
| `backend/app/main.py` | Modify | `GET /cities` route; `CORSMiddleware` from `CORS_ORIGINS`. |
| `backend/tests/test_cities_api.py` | Create | `GET /cities` contract. |
| `backend/tests/test_cors.py` | Create | CORS origin reflected. |
| `frontend/` (scaffold) | Create | Vite React-TS app + Vitest config + scripts. |
| `frontend/src/styles/theme.css` | Create | Palette vars, fonts, scanlines. |
| `frontend/src/components/PixelButton.tsx` + `DialogueBox.tsx` | Create | Pixel UI primitives. |
| `frontend/src/lib/time.ts` | Create | `parseServerUtc`. |
| `frontend/src/map/projection.ts` | Create | lat/lon → normalized x/y. |
| `frontend/src/map/flight.ts` | Create | `progress` + `interpolate` (antimeridian wrap). |
| `frontend/src/api/client.ts` | Create | fetch wrapper + refresh mutex. |
| `frontend/src/api/auth.ts` | Create | login/register/google/refresh/me calls. |
| `frontend/src/auth/AuthContext.tsx` | Create | token storage + auth state. |
| `frontend/src/App.tsx` | Modify | minimal auth-gated shell (placeholder until Phase 2). |

**Phase-1 done = green when:** backend pytest passes with the two new tests; `npm test` (Vitest) passes; `npm run build` succeeds; `npm run dev` boots to a placeholder that reflects logged-out state.

---

## Task 1: Backend `GET /cities`

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cities_api.py`

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_cities_api.py`:

```python
def test_cities_returns_full_catalog(client):
    resp = client.get("/cities")
    assert resp.status_code == 200
    cities = resp.json()
    assert len(cities) == 20
    names = [c["name"] for c in cities]
    assert names == sorted(names)           # sorted by name
    assert all(n == n.lower() for n in names)  # lowercase catalog keys
    tokyo = next(c for c in cities if c["name"] == "tokyo")
    assert tokyo["lat"] == 35.6762 and tokyo["lon"] == 139.6503
    assert set(cities[0]) == {"name", "lat", "lon"}


def test_cities_is_public(client):
    # no Authorization header needed
    assert client.get("/cities").status_code == 200
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_cities_api.py -q`
Expected: FAIL — 404 (route not defined).

- [ ] **Step 3: Add `CityOut`** to `backend/app/schemas.py` (after the imports / near the other `*Out` models):

```python
class CityOut(BaseModel):
    name: str
    lat: float
    lon: float
```

- [ ] **Step 4: Add the route** in `backend/app/main.py`. Add imports at the top:

```python
from app.cities import CITIES
from app.schemas import CityOut
```

Inside `create_app()`, next to the `health` route, add:

```python
    @app.get("/cities", response_model=list[CityOut], tags=["meta"])
    def cities() -> list[CityOut]:
        return [
            CityOut(name=name, lat=lat, lon=lon)
            for name, (lat, lon) in sorted(CITIES.items())
        ]
```

- [ ] **Step 5: Run it — expect PASS**, then the full suite.

Run: `cd backend && .venv/bin/python -m pytest tests/test_cities_api.py -q` → PASS
Run: `cd backend && .venv/bin/python -m pytest -q` → all green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/main.py backend/tests/test_cities_api.py
git commit -m "feat: public GET /cities catalog endpoint

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Backend CORS

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cors.py`

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_cors.py`:

```python
def test_cors_reflects_configured_origin(client):
    resp = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_omits_unknown_origin(client):
    resp = client.get("/health", headers={"Origin": "http://evil.example"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") != "http://evil.example"
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_cors.py -q`
Expected: FAIL — no `access-control-allow-origin` header.

- [ ] **Step 3: Add the middleware** in `backend/app/main.py`. Add imports:

```python
import os
from fastapi.middleware.cors import CORSMiddleware
```

Inside `create_app()`, after `app = FastAPI(...)` and before the routes, add:

```python
    origins = [
        o.strip()
        for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
```

- [ ] **Step 4: Run it — expect PASS**, then the full suite.

Run: `cd backend && .venv/bin/python -m pytest tests/test_cors.py -q` → PASS
Run: `cd backend && .venv/bin/python -m pytest -q` → all green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_cors.py
git commit -m "feat: CORS middleware (origins from CORS_ORIGINS)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Scaffold the frontend

**Files:**
- Create: `frontend/` (Vite React-TS scaffold) + Vitest config.

- [ ] **Step 1: Scaffold Vite (non-interactive)**

```bash
cd /Users/pratikkamath/Github-Projects/pigeon-post
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
```

- [ ] **Step 2: Add test + font deps**

```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
npm install @fontsource/press-start-2p @fontsource/vt323
```

- [ ] **Step 3: Configure Vitest** — replace `frontend/vite.config.ts` with:

```ts
/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
  },
});
```

- [ ] **Step 4: Test setup file + TS globals** — create `frontend/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

Then make `tsc -b` (used by `npm run build`) recognize the Vitest globals (`test`/`expect`/`vi`/`beforeEach`) used in the `*.test.tsx` files, which live under `src`. In `frontend/tsconfig.app.json`, merge `"vitest/globals"` into `compilerOptions.types` (keep all the template's other options; create the `types` array if it's absent):

```jsonc
{
  "compilerOptions": {
    // ...existing template options...
    "types": ["vitest/globals"]
  }
}
```

- [ ] **Step 5: Add scripts** — in `frontend/package.json`, ensure the `scripts` block contains:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 6: Replace the sample app with a smoke test target** — overwrite `frontend/src/App.tsx`:

```tsx
export default function App() {
  return <div>Pigeon Post</div>;
}
```

Create `frontend/src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders the app name", () => {
  render(<App />);
  expect(screen.getByText("Pigeon Post")).toBeInTheDocument();
});
```

- [ ] **Step 7: Verify** — from `frontend/`:

```bash
npm test          # 1 passing
npm run build     # type-checks + builds clean
```

Expected: test passes; build succeeds.

- [ ] **Step 8: Commit** (Vite's template adds `frontend/.gitignore` covering `node_modules` and `dist`)

```bash
cd /Users/pratikkamath/Github-Projects/pigeon-post
git add frontend
git commit -m "build: scaffold Vite + React + TS frontend with Vitest

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Pixel visual system

**Files:**
- Create: `frontend/src/styles/theme.css`
- Create: `frontend/src/components/PixelButton.tsx`, `frontend/src/components/DialogueBox.tsx`
- Modify: `frontend/src/main.tsx` (import fonts + theme)
- Test: `frontend/src/components/PixelButton.test.tsx`, `frontend/src/components/DialogueBox.test.tsx`

- [ ] **Step 1: Write failing component tests** — create `frontend/src/components/PixelButton.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PixelButton } from "./PixelButton";

test("renders label and fires onClick", async () => {
  const onClick = vi.fn();
  render(<PixelButton onClick={onClick}>SEND</PixelButton>);
  await userEvent.click(screen.getByRole("button", { name: "SEND" }));
  expect(onClick).toHaveBeenCalledOnce();
});

test("respects disabled", async () => {
  const onClick = vi.fn();
  render(<PixelButton onClick={onClick} disabled>SEND</PixelButton>);
  await userEvent.click(screen.getByRole("button", { name: "SEND" }));
  expect(onClick).not.toHaveBeenCalled();
});
```

Create `frontend/src/components/DialogueBox.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { DialogueBox } from "./DialogueBox";

test("renders children inside a status region", () => {
  render(<DialogueBox>41h to arrival</DialogueBox>);
  expect(screen.getByText("41h to arrival")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run — expect FAIL** (`Cannot find module './PixelButton'`).

Run: `cd frontend && npm test`

- [ ] **Step 3: Theme** — create `frontend/src/styles/theme.css`:

```css
:root {
  --sea: #5aa9e6;
  --land: #7bc24a;
  --land-edge: #3d7a2e;
  --city: #f4d06a;
  --ink: #0a0a0a;
  --screen: #0e1830;
  --paper: #f8f8f8;
  --frame: #5566c4;
  --accent: #d83a34;
  --font-head: "Press Start 2P", monospace;
  --font-body: "VT323", ui-monospace, monospace;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: #101015;
  color: var(--paper);
  font-family: var(--font-body);
  font-size: 20px;
  image-rendering: pixelated;
}

.pk-box {
  background: var(--paper);
  color: var(--ink);
  border: 3px solid var(--ink);
  border-radius: 7px;
  box-shadow: inset 0 0 0 3px var(--paper), inset 0 0 0 5px var(--frame);
  padding: 10px 12px;
}

.pk-button {
  font-family: var(--font-head);
  font-size: 11px;
  letter-spacing: 1px;
  color: #fff;
  background: var(--accent);
  border: 3px solid var(--ink);
  border-radius: 5px;
  padding: 9px 12px;
  cursor: pointer;
}
.pk-button:disabled { opacity: 0.5; cursor: default; }

.scanlines::after {
  content: "";
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(transparent 0 2px, rgba(0,0,0,.06) 2px 3px);
  pointer-events: none;
}
```

- [ ] **Step 4: Components** — create `frontend/src/components/PixelButton.tsx`:

```tsx
import type { ButtonHTMLAttributes } from "react";

export function PixelButton(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  const { className = "", ...rest } = props;
  return <button className={`pk-button ${className}`} {...rest} />;
}
```

Create `frontend/src/components/DialogueBox.tsx`:

```tsx
import type { ReactNode } from "react";

export function DialogueBox({ children }: { children: ReactNode }) {
  return (
    <div className="pk-box" role="status" aria-live="polite">
      {children}
    </div>
  );
}
```

- [ ] **Step 5: Wire fonts + theme** — overwrite `frontend/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/press-start-2p";
import "@fontsource/vt323";
import "./styles/theme.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

Delete the Vite sample CSS imports if any remain (remove `frontend/src/index.css` import and `frontend/src/App.css` import; the files may stay but must not be imported).

- [ ] **Step 6: Run — expect PASS**, then build.

Run: `cd frontend && npm test` → all pass
Run: `cd frontend && npm run build` → clean

- [ ] **Step 7: Commit**

```bash
cd /Users/pratikkamath/Github-Projects/pigeon-post
git add frontend/src frontend/package.json frontend/package-lock.json
git commit -m "feat: pixel visual system (theme, PixelButton, DialogueBox)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `parseServerUtc`

**Files:**
- Create: `frontend/src/lib/time.ts`
- Test: `frontend/src/lib/time.test.ts`

- [ ] **Step 1: Failing test** — create `frontend/src/lib/time.test.ts`:

```ts
import { parseServerUtc } from "./time";

test("treats a timezone-less server string as UTC", () => {
  // Backend emits naive UTC like this (no offset). It must NOT be read as local.
  const d = parseServerUtc("2026-06-14T10:00:00");
  expect(d.getTime()).toBe(Date.UTC(2026, 5, 14, 10, 0, 0));
});

test("respects an explicit Z", () => {
  const d = parseServerUtc("2026-06-14T10:00:00Z");
  expect(d.getTime()).toBe(Date.UTC(2026, 5, 14, 10, 0, 0));
});

test("respects fractional seconds without offset", () => {
  const d = parseServerUtc("2026-06-14T10:00:00.500000");
  expect(d.getTime()).toBe(Date.UTC(2026, 5, 14, 10, 0, 0, 500));
});
```

- [ ] **Step 2: Run — expect FAIL** (`cd frontend && npm test`).

- [ ] **Step 3: Implement** — create `frontend/src/lib/time.ts`:

```ts
/** Parse a backend datetime. The backend emits naive UTC (no offset); JS would
 *  otherwise read such a string as local time, so we append `Z` when there's
 *  no timezone designator. */
export function parseServerUtc(s: string): Date {
  const hasTz = /[zZ]$|[+-]\d\d:?\d\d$/.test(s);
  return new Date(hasTz ? s : s + "Z");
}
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/time.ts frontend/src/lib/time.test.ts
git commit -m "feat: parseServerUtc for naive-UTC server timestamps

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Map projection

**Files:**
- Create: `frontend/src/map/projection.ts`
- Test: `frontend/src/map/projection.test.ts`

- [ ] **Step 1: Failing test** — create `frontend/src/map/projection.test.ts`:

```ts
import { project } from "./projection";

test("lon 0 / lat 0 maps to the center", () => {
  expect(project(0, 0)).toEqual({ x: 0.5, y: 0.5 });
});

test("corners map to the unit box", () => {
  expect(project(90, -180)).toEqual({ x: 0, y: 0 });   // NW
  expect(project(-90, 180)).toEqual({ x: 1, y: 1 });   // SE
});

test("a known city projects sensibly (Tokyo: east + northern)", () => {
  const { x, y } = project(35.6762, 139.6503);
  expect(x).toBeGreaterThan(0.5);
  expect(y).toBeLessThan(0.5);
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** — create `frontend/src/map/projection.ts`:

```ts
export interface Point { x: number; y: number; }

/** Equirectangular projection to a normalized [0,1] box.
 *  x: lon -180..180 -> 0..1 ; y: lat 90..-90 -> 0..1 (north at top). */
export function project(lat: number, lon: number): Point {
  return { x: (lon + 180) / 360, y: (90 - lat) / 180 };
}
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/map/projection.ts frontend/src/map/projection.test.ts
git commit -m "feat: equirectangular map projection

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Flight progress + interpolation (antimeridian wrap)

**Files:**
- Create: `frontend/src/map/flight.ts`
- Test: `frontend/src/map/flight.test.ts`

- [ ] **Step 1: Failing test** — create `frontend/src/map/flight.test.ts`:

```ts
import { progress, interpolate } from "./flight";
import { project } from "./projection";

const sent = Date.UTC(2026, 5, 14, 0, 0, 0);
const arrive = Date.UTC(2026, 5, 14, 10, 0, 0); // 10h flight

test("progress clamps to [0,1]", () => {
  expect(progress(sent, arrive, sent)).toBe(0);
  expect(progress(sent, arrive, Date.UTC(2026, 5, 14, 5, 0, 0))).toBeCloseTo(0.5);
  expect(progress(sent, arrive, Date.UTC(2026, 5, 14, 20, 0, 0))).toBe(1);
});

test("interpolate midpoint of two near points", () => {
  const a = { x: 0.2, y: 0.4 };
  const b = { x: 0.4, y: 0.6 };
  expect(interpolate(a, b, 0.5)).toEqual({ x: 0.3, y: 0.5 });
});

test("antimeridian pair takes the short wrapped path (Tokyo -> San Francisco)", () => {
  const tokyo = project(35.6762, 139.6503);        // x ~0.89
  const sf = project(37.7749, -122.4194);          // x ~0.16
  // halfway should be NEAR the seam (x close to 0 or 1), not in the middle of the map
  const mid = interpolate(tokyo, sf, 0.5);
  expect(mid.x < 0.1 || mid.x > 0.9).toBe(true);
});
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** — create `frontend/src/map/flight.ts`:

```ts
import type { Point } from "./projection";

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Fraction 0..1 of the journey elapsed (ms epochs). */
export function progress(sentMs: number, arriveMs: number, nowMs: number): number {
  if (arriveMs <= sentMs) return 1;
  return clamp((nowMs - sentMs) / (arriveMs - sentMs), 0, 1);
}

/** Linear interpolation in normalized space, wrapping the SHORTER way in x so
 *  routes across the antimeridian don't traverse the whole map. Result x is
 *  wrapped back into [0,1). */
export function interpolate(a: Point, b: Point, t: number): Point {
  let dx = b.x - a.x;
  if (dx > 0.5) dx -= 1;
  else if (dx < -0.5) dx += 1;
  let x = a.x + dx * t;
  x = ((x % 1) + 1) % 1;
  return { x, y: a.y + (b.y - a.y) * t };
}
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/map/flight.ts frontend/src/map/flight.test.ts
git commit -m "feat: flight progress + antimeridian-wrapped interpolation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: API client with refresh mutex

**Files:**
- Create: `frontend/src/api/tokens.ts` (localStorage get/set/clear)
- Create: `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

- [ ] **Step 1: Token storage** — create `frontend/src/api/tokens.ts`:

```ts
const ACCESS = "pp_access";
const REFRESH = "pp_refresh";

export const tokens = {
  get access() { return localStorage.getItem(ACCESS); },
  get refresh() { return localStorage.getItem(REFRESH); },
  set(pair: { access_token: string; refresh_token: string }) {
    localStorage.setItem(ACCESS, pair.access_token);
    localStorage.setItem(REFRESH, pair.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};
```

Also declare the custom env vars so `import.meta.env.VITE_API_BASE_URL` type-checks. Append to `frontend/src/vite-env.d.ts` (which already has `/// <reference types="vite/client" />`):

```ts
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_GOOGLE_CLIENT_ID?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

And create `frontend/.env.example`:

```
VITE_API_BASE_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=
```

- [ ] **Step 2: Failing test** — create `frontend/src/api/client.test.ts`:

```ts
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
  expect((init.headers as Record<string, string>).Authorization).toBe("Bearer acc");
});

test("401 -> refresh -> retry once with the new token", async () => {
  tokens.set({ access_token: "old", refresh_token: "ref" });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    const u = String(url);
    if (u.endsWith("/auth/refresh")) {
      return jsonResponse({ access_token: "new", refresh_token: "ref2" });
    }
    const auth = (init?.headers as Record<string, string>)?.Authorization;
    return auth === "Bearer new" ? jsonResponse({ ok: true }) : jsonResponse({}, 401);
  });
  const res = await apiFetch("/messages/sent");
  expect(res).toEqual({ ok: true });
  expect(tokens.access).toBe("new");
  // protected call (401) + refresh + retry = 3 fetches
  expect(fetchMock).toHaveBeenCalledTimes(3);
});

test("concurrent 401s share ONE refresh", async () => {
  tokens.set({ access_token: "old", refresh_token: "ref" });
  let refreshCalls = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    const u = String(url);
    if (u.endsWith("/auth/refresh")) {
      refreshCalls += 1;
      return jsonResponse({ access_token: "new", refresh_token: "ref2" });
    }
    const auth = (init?.headers as Record<string, string>)?.Authorization;
    return auth === "Bearer new" ? jsonResponse({ ok: true }) : jsonResponse({}, 401);
  });
  await Promise.all([apiFetch("/messages/sent"), apiFetch("/messages/inbox")]);
  expect(refreshCalls).toBe(1);
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
```

- [ ] **Step 3: Run — expect FAIL** (`Cannot find module './client'`).

- [ ] **Step 4: Implement** — create `frontend/src/api/client.ts`:

```ts
import { tokens } from "./tokens";

const AUTH_PATHS = ["/auth/login", "/auth/register", "/auth/google", "/auth/refresh"];

let logoutHandler: () => void = () => {};
export function onLogout(fn: () => void) { logoutHandler = fn; }

let refreshPromise: Promise<boolean> | null = null;

function base() { return import.meta.env.VITE_API_BASE_URL ?? ""; }

export class ApiError extends Error {
  constructor(public status: number, public body: unknown) {
    super(`API ${status}`);
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
  let resp = await rawFetch(path, init);
  const isAuthPath = AUTH_PATHS.some((p) => path.startsWith(p));
  if (resp.status === 401 && !isAuthPath) {
    const ok = await refresh();
    if (!ok) {
      tokens.clear();
      logoutHandler();
      throw new ApiError(401, await safeBody(resp));
    }
    resp = await rawFetch(path, init); // retry once with new token
  }
  if (!resp.ok) throw new ApiError(resp.status, await safeBody(resp));
  return resp.status === 204 ? (undefined as T) : ((await resp.json()) as T);
}

async function safeBody(resp: Response): Promise<unknown> {
  try { return await resp.json(); } catch { return null; }
}
```

- [ ] **Step 5: Run — expect PASS**, then build.

Run: `cd frontend && npm test` → all pass
Run: `cd frontend && npm run build` → clean

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api frontend/src/vite-env.d.ts frontend/.env.example
git commit -m "feat: API client with shared refresh-token mutex

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Auth API + AuthContext

**Files:**
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/auth/AuthContext.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/auth/AuthContext.test.tsx`

- [ ] **Step 1: Auth API calls** — create `frontend/src/api/auth.ts`:

```ts
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
```

- [ ] **Step 2: Failing test** — create `frontend/src/auth/AuthContext.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider, useAuth } from "./AuthContext";
import * as authApi from "../api/auth";

function Harness() {
  const { user, status, login } = useAuth();
  return (
    <div>
      <span>status:{status}</span>
      <span>user:{user?.username ?? "none"}</span>
      <button onClick={() => login("a@b.com", "pw")}>login</button>
    </div>
  );
}

test("starts logged out and logs in", async () => {
  vi.spyOn(authApi, "me").mockRejectedValue(new Error("401")); // no session on boot
  vi.spyOn(authApi, "login").mockResolvedValue({
    id: 1, username: "pratik", email: "a@b.com", created_at: "2026-06-14T00:00:00",
  });
  render(<AuthProvider><Harness /></AuthProvider>);
  await waitFor(() => expect(screen.getByText("status:anonymous")).toBeInTheDocument());
  await userEvent.click(screen.getByText("login"));
  await waitFor(() => expect(screen.getByText("user:pratik")).toBeInTheDocument());
});
```

- [ ] **Step 3: Run — expect FAIL.**

- [ ] **Step 4: Implement** — create `frontend/src/auth/AuthContext.tsx`:

```tsx
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
    onLogout(() => { tokens.clear(); goAnon(); });
    if (!tokens.access) { goAnon(); return; }
    authApi.me().then(applyUser).catch(goAnon);
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
```

- [ ] **Step 5: Wire the shell** — overwrite `frontend/src/App.tsx`:

```tsx
import { AuthProvider, useAuth } from "./auth/AuthContext";

function Shell() {
  const { status, user } = useAuth();
  if (status === "loading") return <div>Loading…</div>;
  if (status === "anonymous") return <div>Pigeon Post — please log in (coming in Phase 2)</div>;
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

Update `frontend/src/App.test.tsx` (the shell no longer renders a bare "Pigeon Post" once authenticated; assert the logged-out copy with a mocked anonymous boot):

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import * as authApi from "./api/auth";

test("shows the logged-out shell when there is no session", async () => {
  vi.spyOn(authApi, "me").mockRejectedValue(new Error("401"));
  render(<App />);
  await waitFor(() => expect(screen.getByText(/please log in/i)).toBeInTheDocument());
});
```

- [ ] **Step 6: Run — expect PASS**, then build.

Run: `cd frontend && npm test` → all pass
Run: `cd frontend && npm run build` → clean

- [ ] **Step 7: Manual boot check (optional)**

Run backend (`cd backend && CORS_ORIGINS=http://localhost:5173 .venv/bin/uvicorn app.main:app`) and `cd frontend && npm run dev`; open the dev URL — it should show the logged-out shell without console/CORS errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat: auth API + AuthContext with logged-out shell

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification (Phase 1)

- [ ] `cd backend && .venv/bin/python -m pytest -q` → all green (includes cities + cors).
- [ ] `cd frontend && npm test` → all green.
- [ ] `cd frontend && npm run build` → clean.
- [ ] `git log --oneline` shows the Phase-1 commits on `feat/frontend-dashboard-mvp`.
- [ ] Next: write **Phase 2 (auth UI + dashboard + map + send)** plan, then Phase 3.
