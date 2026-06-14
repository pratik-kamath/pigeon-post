# Frontend Phase 3 — Google sign-in + e2e smoke + docs + polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the dashboard MVP — add "Sign in with Google", a Playwright end-to-end smoke that proves the map actually renders, project docs, and the remaining motion polish.

**Architecture:** A small `GoogleSignInButton` loads Google Identity Services and forwards the credential to the already-wired `loginWithGoogle` (`POST /auth/google`). A Playwright smoke mocks the API and asserts the rendered dashboard at desktop + mobile. Motion polish is CSS plus a tiny `useClock` so the status countdown stays live.

**Tech Stack:** Vite + React 19 + TS, Vitest + RTL (existing), **@playwright/test** (new, dev-only), Google Identity Services (loaded at runtime).

**Spec:** `docs/superpowers/specs/2026-06-14-frontend-dashboard-mvp-design.md` (this implements **Phase 3** of its Build order — the final phase).

**Conventions:** All commands from `frontend/`. `npm test` (Vitest), `npm run lint`, `npm run build` stay green at every commit. Commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Available from Phase 1/2:** `auth/useAuth.ts` exposes `loginWithGoogle(idToken)`; `auth/AuthContext.tsx` calls `authApi.googleLogin` → `POST /auth/google`; `api/client.ts` already skips refresh for `/auth/google`. `screens/{AuthScreen,Dashboard}.tsx`, `map/WorldMap.tsx`, `components/{PixelButton,DialogueBox,SendDialog}.tsx`, `lib/{format,time,usePolling}.ts` all exist.

---

## File Structure (this phase)

| File | Change | Responsibility |
|---|---|---|
| `src/components/GoogleSignInButton.tsx` | Create | Load GIS, render the button, forward the credential |
| `src/screens/AuthScreen.tsx` | Modify | Render the Google button + a Google credential handler |
| `src/lib/useClock.ts` | Create | A low-frequency clock so countdowns stay live |
| `src/screens/Dashboard.tsx` | Modify | Use `useClock` for the status line |
| `src/styles/theme.css` | Modify | Launch pop, hover/selected pulses, Google button spacing |
| `frontend/playwright.config.ts` | Create | Playwright config (build+preview webServer, desktop+mobile) |
| `frontend/e2e/dashboard.spec.ts` | Create | API-mocked smoke: map + sprite + send dialog |
| `frontend/package.json` | Modify | `test:e2e` script + `@playwright/test` dep |
| `README.md`, `CLAUDE.md` (repo root) | Modify | Frontend run/docs + gotchas |

**Phase-3 done = green when:** `npm test`, `npm run lint`, `npm run build` pass; the Playwright smoke passes (or is documented BLOCKED if browsers can't install); docs updated.

---

## Task 1: Google sign-in button

**Files:** Create `src/components/GoogleSignInButton.tsx`; Modify `src/screens/AuthScreen.tsx`, `src/styles/theme.css`; Test `src/components/GoogleSignInButton.test.tsx`, extend `src/screens/AuthScreen.test.tsx`.

- [ ] **Step 1: Failing test** — `src/components/GoogleSignInButton.test.tsx`:
```tsx
import { render } from "@testing-library/react";
import { GoogleSignInButton } from "./GoogleSignInButton";

interface MockId {
  initialize: (opts: { client_id: string; callback: (r: { credential: string }) => void }) => void;
  renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void;
}
declare global {
  // eslint-disable-next-line no-var
  var google: { accounts: { id: MockId } } | undefined;
}

afterEach(() => {
  globalThis.google = undefined;
  vi.unstubAllEnvs();
});

test("renders nothing when no client id is configured", () => {
  vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "");
  const { container } = render(<GoogleSignInButton onCredential={() => {}} />);
  expect(container.firstChild).toBeNull();
});

test("initializes GIS and forwards the credential", () => {
  vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "client-123");
  let captured: ((r: { credential: string }) => void) | null = null;
  globalThis.google = {
    accounts: { id: {
      initialize: (opts) => { captured = opts.callback; },
      renderButton: vi.fn(),
    } },
  };
  const onCredential = vi.fn();
  render(<GoogleSignInButton onCredential={onCredential} />);
  expect(typeof captured).toBe("function");
  captured!({ credential: "id-token-xyz" });
  expect(onCredential).toHaveBeenCalledWith("id-token-xyz");
});
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/components/GoogleSignInButton.tsx`:
```tsx
import { useEffect, useRef } from "react";

const GIS_SRC = "https://accounts.google.com/gsi/client";

interface GoogleId {
  initialize: (opts: { client_id: string; callback: (r: { credential: string }) => void }) => void;
  renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void;
}
declare global {
  interface Window { google?: { accounts: { id: GoogleId } }; }
}

export function GoogleSignInButton({ onCredential }: { onCredential: (idToken: string) => void }) {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const containerRef = useRef<HTMLDivElement>(null);
  const cbRef = useRef(onCredential);
  useEffect(() => { cbRef.current = onCredential; }, [onCredential]);

  useEffect(() => {
    if (!clientId) return;
    const el = containerRef.current;
    if (!el) return;

    function init() {
      const id = window.google?.accounts?.id;
      if (!id || !el) return;
      id.initialize({ client_id: clientId as string, callback: (r) => cbRef.current(r.credential) });
      el.replaceChildren(); // idempotent: avoid a doubled button under React StrictMode's double-invoke
      id.renderButton(el, { theme: "filled_black", size: "large", text: "continue_with" });
    }

    if (window.google?.accounts?.id) { init(); return; }
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", init);
      return () => existing.removeEventListener("load", init);
    }
    const s = document.createElement("script");
    s.src = GIS_SRC;
    s.async = true;
    s.defer = true;
    s.addEventListener("load", init);
    document.head.appendChild(s);
    return () => s.removeEventListener("load", init);
  }, [clientId]);

  if (!clientId) return null;
  return <div ref={containerRef} className="google-btn" />;
}
```

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Wire into AuthScreen** — in `src/screens/AuthScreen.tsx`: pull `loginWithGoogle` from `useAuth`, add a credential handler, and render the button under the form. Change the `useAuth` destructure to include it, add the handler before `return`, and insert the button after the `</form>` (before the toggle button):
```tsx
  const { login, register, loginWithGoogle } = useAuth();
```
```tsx
  async function onGoogleCredential(idToken: string) {
    setError(null);
    try {
      await loginWithGoogle(idToken);
    } catch {
      setError("Google sign-in failed.");
    }
  }
```
```tsx
        </form>
        <GoogleSignInButton onCredential={onGoogleCredential} />
        <button
```
Add the import: `import { GoogleSignInButton } from "../components/GoogleSignInButton";`.

- [ ] **Step 6: Extend AuthScreen test** — add to `src/screens/AuthScreen.test.tsx` (and an `afterEach` cleanup so the GIS globals/env don't leak):
```tsx
afterEach(() => {
  (globalThis as { google?: unknown }).google = undefined;
  vi.unstubAllEnvs();
});

test("a Google credential logs in via loginWithGoogle", async () => {
  vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "client-123");
  let captured: ((r: { credential: string }) => void) | null = null;
  (globalThis as { google?: unknown }).google = {
    accounts: { id: { initialize: (o: { callback: (r: { credential: string }) => void }) => { captured = o.callback; }, renderButton: () => {} } },
  };
  const loginWithGoogle = vi.fn().mockResolvedValue(undefined);
  mockAuth({ loginWithGoogle });
  render(<AuthScreen />);
  captured!({ credential: "tok" });
  await waitFor(() => expect(loginWithGoogle).toHaveBeenCalledWith("tok"));
});
```
(The existing AuthScreen tests don't set `VITE_GOOGLE_CLIENT_ID`, so `GoogleSignInButton` renders `null` there — they're unaffected.)

- [ ] **Step 7: CSS** — append to `src/styles/theme.css`:
```css
.google-btn { display: flex; justify-content: center; margin-top: 10px; min-height: 40px; }
```

- [ ] **Step 8: Run** `npm test` (all green), `npm run lint` (clean), `npm run build` (clean).

- [ ] **Step 9: Commit**
```bash
cd /Users/pratikkamath/Github-Projects/pigeon-post
git add frontend/src/components/GoogleSignInButton.tsx frontend/src/components/GoogleSignInButton.test.tsx frontend/src/screens/AuthScreen.tsx frontend/src/screens/AuthScreen.test.tsx frontend/src/styles/theme.css
git commit -m "feat: Google sign-in button (GIS) wired to loginWithGoogle

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: live countdown + motion polish

**Files:** Create `src/lib/useClock.ts`; Modify `src/screens/Dashboard.tsx`, `src/styles/theme.css`; Test `src/lib/useClock.test.ts`.

- [ ] **Step 1: Failing test** — `src/lib/useClock.test.ts`:
```ts
import { renderHook } from "@testing-library/react";
import { act } from "react";
import { useClock } from "./useClock";

afterEach(() => vi.useRealTimers());

test("advances on the interval and stops on unmount", () => {
  vi.useFakeTimers();
  const { result, rerender, unmount } = renderHook(() => useClock(1000));
  const t0 = result.current;
  act(() => { vi.advanceTimersByTime(1000); });
  rerender();
  expect(result.current).toBeGreaterThanOrEqual(t0);
  const before = result.current;
  unmount();
  act(() => { vi.advanceTimersByTime(5000); });
  expect(result.current).toBe(before); // no ticks after unmount
});
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/lib/useClock.ts`:
```ts
import { useEffect, useState } from "react";

/** A coarse clock that re-renders consumers every `intervalMs`, so derived
 *  text like countdowns stays live between data polls. */
export function useClock(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
```

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Use it in Dashboard** — in `src/screens/Dashboard.tsx`: import `useClock`, take a `now`, and thread it into `statusLine` so the countdown refreshes ~every 15s (independent of the 10s data poll). Change `statusLine` to accept `now`, and call `useClock` in the component:
```ts
import { useClock } from "../lib/useClock";
```
```ts
function statusLine(m: Message, now: number): string {
  const to = `#${m.id} → ${m.recipient} @ ${titleCaseCity(m.destination)}`;
  if (m.status === "delivered") return `${to} · delivered ✓`;
  if (m.status === "lost") return `${to} · lost ✗`;
  const left = parseServerUtc(m.arrival_at).getTime() - now;
  return `${to} · ${formatCountdown(left)} to arrival`;
}
```
In the component body add `const now = useClock(15_000);` and change the DialogueBox usage `selected ? statusLine(selected) : ...` to `selected ? statusLine(selected, now) : ...`.

- [ ] **Step 6: Motion polish CSS** — CSS `animation` doesn't merge across selectors, so **edit the two existing Phase-2 rules** and **append** the rest. Replace the existing `.pigeon--in_flight { animation: bob 1.2s ease-in-out infinite; }` with:
```css
.pigeon--in_flight { animation: pop 0.3s ease-out, bob 1.2s ease-in-out infinite 0.3s; }
```
Replace the existing `.pigeon--selected { outline: 2px solid var(--frame); outline-offset: 2px; }` with:
```css
.pigeon--selected { outline: 2px solid var(--frame); outline-offset: 2px; animation: pop 0.3s ease-out, pulse 0.9s ease-in-out infinite; }
```
Add `animation: pop 0.3s ease-out;` to the **existing early base `.pigeon { … }` rule** (the one with `position`/`clip-path`, declared BEFORE the modifiers). Do NOT add a second, late `.pigeon { animation: pop }` rule — equal specificity means source order decides, and a late base rule would clobber the `--in_flight`/`--selected` `animation` (killing the bob/pulse). Then append:
```css
/* A selected in-flight pigeon needs the combined class (specificity 0,2,0) for all three. */
.pigeon--in_flight.pigeon--selected { animation: pop 0.3s ease-out, bob 1.2s ease-in-out infinite 0.3s, pulse 0.9s ease-in-out infinite; }
.pigeon:hover { transform: translate(-50%, -50%) scale(1.35); z-index: 3; }
@keyframes pop { from { transform: translate(-50%, -50%) scale(0); } to { transform: translate(-50%, -50%) scale(1); } }
@keyframes pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(85, 102, 196, 0.6); } 50% { box-shadow: 0 0 0 4px rgba(85, 102, 196, 0); } }
```
> Ordering matters: the base `.pigeon` `pop` is declared first, so the later `--in_flight`/`--selected`/combined rules win for their elements — in-flight pop+bob, selected pop+pulse, both pop+bob+pulse, delivered/lost just pop. `bob` uses `margin-top` and `pulse` uses `box-shadow`, so neither fights the `:hover` `transform`. City markers are `pointer-events: none` (no city hover). The Phase-1 `prefers-reduced-motion` guard disables all of it.

- [ ] **Step 7: Run** `npm test` (all green), `npm run lint`, `npm run build` (clean).

- [ ] **Step 8: Commit**
```bash
git add frontend/src/lib/useClock.ts frontend/src/lib/useClock.test.ts frontend/src/screens/Dashboard.tsx frontend/src/styles/theme.css
git commit -m "feat: live countdown clock + launch/hover/selected motion polish

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Playwright e2e smoke

**Files:** Create `frontend/playwright.config.ts`, `frontend/e2e/dashboard.spec.ts`; Modify `frontend/package.json` (dep + script), `frontend/.gitignore`.

- [ ] **Step 1: Install Playwright**
```bash
cd /Users/pratikkamath/Github-Projects/pigeon-post/frontend
npm install -D @playwright/test
npx playwright install chromium
```
If the browser download is blocked by the sandbox/network, STOP and report **BLOCKED** (the smoke is real-browser; unit/RTL still cover the logic).

- [ ] **Step 2: Config** — create `frontend/playwright.config.ts`:
```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  webServer: {
    command: "npm run build && npm run preview -- --port 4173 --strictPort",
    url: "http://localhost:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  use: { baseURL: "http://localhost:4173" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
});
```

- [ ] **Step 3: Smoke test** — create `frontend/e2e/dashboard.spec.ts`:
```ts
import { test, expect } from "@playwright/test";

const user = { id: 1, username: "pratik", email: "p@x.com", created_at: "2026-06-14T00:00:00" };
const cities = [
  { name: "new york", lat: 40.7128, lon: -74.006 },
  { name: "tokyo", lat: 35.6762, lon: 139.6503 },
];
const sent = [{
  id: 1, sender: "pratik", recipient: "alex", body: "hi", origin: "new york",
  destination: "tokyo", distance_km: 6700, status: "in_flight",
  sent_at: "2026-06-14T00:00:00", arrival_at: "2999-01-01T00:00:00", resolved_at: null,
}];

test.beforeEach(async ({ page }) => {
  // Seed a session and mock the API by path (works regardless of API base URL).
  await page.addInitScript(() => {
    localStorage.setItem("pp_access", "test-access");
    localStorage.setItem("pp_refresh", "test-refresh");
  });
  const json = (body: unknown) => ({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  await page.route("**/auth/me", (r) => r.fulfill(json(user)));
  await page.route("**/cities", (r) => r.fulfill(json(cities)));
  await page.route("**/messages/sent", (r) => r.fulfill(json(sent)));
});

test("dashboard shows the map, a pigeon, and opens the send dialog", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("region", { name: /world map/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /pigeon to alex/i })).toBeVisible();
  await page.getByRole("button", { name: /^send$/i }).click();
  await expect(page.getByText(/send a pigeon/i)).toBeVisible();
});
```

- [ ] **Step 4: Script + ignore** — in `frontend/package.json` add to `scripts`: `"test:e2e": "playwright test"`. Append to `frontend/.gitignore`:
```
/test-results
/playwright-report
/playwright/.cache
```

- [ ] **Step 5: Keep Vitest out of `e2e/`, then run both suites.** Vitest's default `include` matches `e2e/*.spec.ts` and would try to run the Playwright file. In `frontend/vite.config.ts`, add an `exclude` to the `test` block so it reads:
```ts
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
```
Then `cd frontend && npm test` (still green, ignores `e2e/`) and `cd frontend && npm run test:e2e` (both desktop + mobile projects pass).

- [ ] **Step 6: Commit**
```bash
git add frontend/playwright.config.ts frontend/e2e frontend/package.json frontend/package-lock.json frontend/.gitignore frontend/vite.config.ts
git commit -m "test: Playwright e2e smoke (map renders, send dialog opens)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Documentation

**Files:** Modify `README.md`, `CLAUDE.md` (repo root).

- [ ] **Step 1: README — Frontend section** — in `README.md`, after the backend "Running the backend" / "Running tests" content (before "## Project layout"), add:
```markdown
### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # set VITE_API_BASE_URL (default http://localhost:8000)
                       # and VITE_GOOGLE_CLIENT_ID (optional, enables Google sign-in)
npm run dev            # Vite dev server, http://localhost:5173
```

The dev server expects the backend running with CORS allowing the frontend origin:

```bash
cd backend
CORS_ORIGINS=http://localhost:5173 FAST_FORWARD=5000 uvicorn app.main:app --reload
```

Frontend tests: `npm test` (Vitest) · lint: `npm run lint` · build: `npm run build` · e2e smoke: `npm run test:e2e` (Playwright — first run once: `npx playwright install chromium`).

The dashboard is a Pokémon-style pixel world map: log in (password or Google), send a pigeon, and watch it fly between cities in real time.
```

- [ ] **Step 2: README — env + endpoints** — confirm the "API at a glance" still lists `GET /cities` (added in Phase 1). If not present, add:
```markdown
- `GET /cities` — the city catalog `[{name, lat, lon}]` (public; used by the map and send form)
```
And note the new env vars near the existing `GOOGLE_CLIENT_ID` line: `CORS_ORIGINS` (backend, comma-separated allowed origins) and the frontend `VITE_*` vars.

Also fix roadmap/status drift in `README.md` (keep edits factual and minimal): the Phase 1 line that says "in progress" → Phase 1 is complete (auth + account-tied messaging + the live pixel-map dashboard shipped); remove "Map view" from the Phase 3 *future* list (the world map exists now); and change the Node prerequisite wording from "for the frontend, when Phase 1 reaches the frontend milestones" to plainly "Node 20+ (for the frontend)". Update the project-layout note if it still calls `frontend/` a later milestone.

- [ ] **Step 3: CLAUDE.md** — update the intro, the Architecture section, commands, and gotchas. First, under "## Architecture", replace the bullet `Frontend (React/Vite/TS) doesn't exist yet (later milestone).` with:
```
Frontend in `frontend/` — React + Vite + TS pixel-RPG dashboard (auth screens + live world map + send); Vitest/RTL tests, Playwright e2e smoke.
```
Then change the intro's "Still to come" to:
```
The frontend exists: a React/Vite/TS pixel-RPG dashboard (`frontend/`) with a live world map.
```
Under "## Commands", add a frontend block:
```markdown
Frontend (from `frontend/`):

```bash
npm install
npm run dev    # :5173 (needs backend running with CORS_ORIGINS=http://localhost:5173)
npm test       # Vitest; npm run lint; npm run build; npm run test:e2e (Playwright)
```
```
Under "## Gotchas", add:
```markdown
- The frontend calls the backend cross-origin: run the backend with `CORS_ORIGINS=http://localhost:5173` or requests are blocked.
- Frontend tokens live in `localStorage`; the API client refreshes via a single shared promise (concurrent 401s must not each replay the rotating refresh token).
- The map projects city lat/lon equirectangularly and animates pigeons from message timestamps (parsed as UTC via `parseServerUtc`); Google sign-in needs `VITE_GOOGLE_CLIENT_ID` set and the origin authorized in the Google console.
```

- [ ] **Step 4: Commit** (from repo root)
```bash
git add README.md CLAUDE.md
git commit -m "docs: frontend run instructions + gotchas

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification (Phase 3 → MVP complete)

- [ ] `cd frontend && npm test` (all green), `npm run lint` (clean), `npm run build` (clean).
- [ ] `cd frontend && npm run test:e2e` → passes (or documented BLOCKED if browsers can't install here).
- [ ] `cd backend && .venv/bin/python -m pytest -q` → 129+ (the `/cities` + CORS tests; backend untouched this phase).
- [ ] Manual: with `VITE_GOOGLE_CLIENT_ID` set + backend `GOOGLE_CLIENT_ID` set, the Google button signs in; password flow still works; pigeons pop in, bob, and the countdown ticks.
- [ ] Hand off via `superpowers:finishing-a-development-branch` — this completes the dashboard MVP (Phases 1-3); merge `feat/frontend-dashboard-mvp` → main.
