# Pixel-RPG frontend — Dashboard MVP — design

- **Date:** 2026-06-14
- **Phase:** 1 (Core mechanic) — frontend
- **Status:** Approved, ready for implementation plan

## Context

The backend is complete for Phase 1: password + Google auth (`/auth/*`) and account-tied messaging (`POST /messages`, `GET /messages/inbox|sent|{id}`), with a delivery sweep that resolves in-flight pigeons to delivered/lost. Cities carry real lat/lon (`backend/app/cities.py`). There is no frontend yet.

This milestone builds the first frontend: a **Pokémon-style pixel-RPG web app** whose centerpiece is a **living world map** where the user watches their sent pigeons fly between real cities. It is the "Phase 1 — live progress dashboard" roadmap item, scoped to a dashboard-first MVP.

## Goals

- Authenticate (login, register, and Google sign-in) and gate the app behind it.
- A single **Dashboard** screen: a pixel world map showing the user's sent pigeons animating along their flight paths in real time; tapping a pigeon shows its status; a Send action launches new pigeons.
- A cohesive Pokémon pixel-RPG visual system (palette, pixel fonts, dialogue/menu boxes).
- Deliver the end-to-end "send a pigeon → watch it cross the map" payoff.

## Non-goals (out of scope for this milestone)

- Inbox / Sent list views and per-message detail/delivery-report screens (next frontend milestone).
- Real-time via WebSockets (Phase 3) — this MVP uses polling + client-side animation.
- Receiving-side experience beyond what the map shows (inbox is its own milestone).
- A handheld Game Boy device frame (explicitly rejected — screen-only).
- Production auth hardening (httpOnly-cookie tokens, CSP) — noted as future work.

## Decisions

| Area | Choice |
|---|---|
| Scope | Dashboard-first MVP (auth → one map screen + send) |
| Aesthetic | Pokémon pixel-RPG, screen-only; GBC/FireRed color palette; pixel fonts; white dialogue/menu boxes with chunky black borders; subtle scanlines |
| Layout | Map-dominant: large map, tap-pigeon → bottom dialogue box, SEND top-right |
| Auth | Login + register (email/password) **and** Google sign-in (GIS → `POST /auth/google`) |
| Map rendering | Code-drawn tile grid (hardcoded land/water bitmap); cities/pigeons are DOM sprites via equirectangular projection |
| Live updates | Poll `GET /messages/sent` (~10 s) + `requestAnimationFrame` interpolation from timestamps |
| Flight path | Straight dotted line between projected endpoints (not curved great-circle) — suits the pixel look |
| Tokens | `localStorage`, with a 401 → refresh → retry flow |
| Stack | Vite + React + TypeScript; Vitest + React Testing Library; minimal deps; hand-rolled pixel CSS |

## Detailed design

### Visual system (`src/styles/theme.css`)

CSS variables for the palette:

- `--sea: #5aa9e6`, `--land: #7bc24a`, `--land-edge: #3d7a2e`, `--city: #f4d06a`, `--ink: #0a0a0a` (outlines/text), `--screen: #0e1830` (bezel/bg), `--paper: #f8f8f8` (box fill), `--frame: #5566c4` (box inner frame), `--accent: #d83a34` (Send / pigeon trim / lost).

Fonts self-hosted via npm so there's no runtime network dependency and tests are deterministic: `@fontsource/press-start-2p` (headings, buttons, labels) and `@fontsource/vt323` (body/dialogue text).

Reusable classes/components:

- `.pk-box` / `DialogueBox` — white panel, `3px` black border, double-frame via inset box-shadow (`inset 0 0 0 3px var(--paper), inset 0 0 0 5px var(--frame)`).
- `PixelButton` — Press Start 2P, accent fill, black border (used for SEND and form submit).
- Screen wrapper — `--screen` bezel; optional scanline overlay (`repeating-linear-gradient`), `pointer-events:none`.
- Global `image-rendering: pixelated` where sprites/tiles scale.

### Backend additions (small, needed by the frontend)

1. **CORS** — in `backend/app/main.py` `create_app()`, add `CORSMiddleware`. Parse `CORS_ORIGINS` (comma-separated) at app-creation time, stripping blanks, default `http://localhost:5173`. Allow methods `GET, POST, OPTIONS` and headers `Authorization, Content-Type`; `allow_credentials=False` (we send a Bearer header, not cookies — so origins are specific, never `*`). Without CORS the browser blocks all API calls.
2. **`GET /cities`** (public, no auth) — returns the catalog as `[{name, lat, lon}]` sorted by name, using the **lowercase** catalog names (matching `cities.py` and what `MessageOut.origin/destination` carry, so lookups are exact); the frontend Title-cases for display. New `CityOut` schema; route reads `app.cities.CITIES`. The map needs coords to project city markers and each pigeon's origin/destination; the Send form needs the dropdown list. Exposing it once avoids duplicating the catalog in the frontend (and it's not sensitive — the catalog already appears in validation errors).

Both get backend tests (the project's TDD norm): `GET /cities` returns all 20 cities with coords; a preflight/simple request reflects the configured CORS origin.

### Auth & API client

- `api/client.ts`: a `request()` wrapper over `fetch` using `import.meta.env.VITE_API_BASE_URL`. Attaches `Authorization: Bearer <access>` when present. On `401` it refreshes via a **single shared `refreshPromise` mutex**: the first 401 starts one `POST /auth/refresh`; any concurrent 401s `await` that same promise instead of each submitting the (rotating) refresh token. After it resolves, each caller retries its original request **once** with the new access token, persisting the rotated pair. Refresh is **skipped for the auth endpoints** (`/auth/login`, `/auth/register`, `/auth/google`, `/auth/refresh`) — a 401 there is bad credentials, not an expired access token. If refresh fails, clear tokens and signal logout; never loop. (Why the mutex: the backend rotates refresh tokens and treats replay of a rotated token as theft, revoking the whole token family — two parallel refreshes with the same token would log the user out.)
- Token storage: `localStorage` keys `pp_access` / `pp_refresh`. **Security caveat:** localStorage is XSS-readable; acceptable for this dev learning app, with httpOnly-cookie storage noted as future hardening.
- `auth/AuthContext.tsx`: holds `user` (from `GET /auth/me`) + auth status; exposes `login(email,pw)`, `register(username,email,pw)`, `loginWithGoogle(idToken)`, `logout()`. Each auth call stores the returned token pair then loads `/auth/me`.
- Google: load the Google Identity Services script; configure with `VITE_GOOGLE_CLIENT_ID`; on the credential callback, call `loginWithGoogle(credential)` → `POST /auth/google {id_token}`. If `VITE_GOOGLE_CLIENT_ID` is unset, hide the Google button (password auth still works). **Operational note:** the Google OAuth *web* client must list the frontend origin (`http://localhost:5173` in dev, plus any deployed origin) under **Authorized JavaScript origins**, or GIS won't render / return a credential.
- `App.tsx`: auth gate — no valid session → `LoginScreen` (with a link to `RegisterScreen`); authenticated → `Dashboard`.

### Screens

- **LoginScreen / RegisterScreen** — Pokémon dialogue-box forms (email/password, plus username on register), a PixelButton submit, the Google button (when configured), and inline error text (e.g., 401 "invalid credentials", 409 "username or email taken"). Register auto-logs-in (backend returns a token pair).
- **Dashboard** — see below.

### Dashboard & map

- `map/worldGrid.ts` — a compact hardcoded land/water bitmap (~120×60 booleans) plus a helper to produce render cells. Rendered once into pixel tiles (sea vs land colors) inside the map box.
- `map/projection.ts` (pure) — `project(lat, lon) -> {x, y}` in **normalized** `[0,1]` space via equirectangular mapping: `x = (lon + 180)/360`, `y = (90 − lat)/180`. The map component multiplies by its pixel size. Resolution-independent → easy to unit-test against known cities.
- `lib/time.ts` (pure) — `parseServerUtc(s) -> Date`: the backend emits **naive UTC** ISO strings (no offset), which JS would otherwise parse as *local* time; this appends `Z` when no offset/`Z` is present so they're read as UTC. All server datetimes go through it.
- `map/flight.ts` (pure) — `progress(sentAt, arrivalAt, now) -> number` = `clamp((now−sentAt)/(arrivalAt−sentAt), 0, 1)`; `interpolate(a, b, t) -> {x,y}` linear in normalized space, with **longitudinal wrap**: if the endpoints are more than half the map apart in x, it interpolates the short way around the antimeridian (so Tokyo→San Francisco crosses the Pacific seam, not the whole map). Used for the sprite position and the dotted path.
- `WorldMap.tsx` — renders the tile grid, `CityMarker`s (projected, with small labels), and a `PigeonSprite` per sent pigeon. A `requestAnimationFrame` loop recomputes in-flight sprite positions from timestamps each frame (smooth motion without polling). States: `in_flight` animate along the (wrapped) path; `delivered` rest at the destination; `lost` render as a faded ✗ **at the destination** — the backend only knows a pigeon was lost at journey's end (it stores `resolved_at`, not a failure coordinate), so we don't invent a midpoint. A path crossing the antimeridian is drawn as two wrapped segments.
- Data: `lib/usePolling.ts` calls `GET /messages/sent` every ~10 s (plus once on mount) to pick up status changes and newly sent pigeons; `GET /cities` is fetched once and cached to resolve origin/destination names → coords.
- Interaction: clicking a `PigeonSprite` selects it → the bottom `DialogueBox` shows `#id → RECIPIENT @ DESTINATION · {Nh Mm to arrival | delivered | lost}`. Default/empty state: "No pigeons aloft. Press SEND to launch one!"
- **SendDialog** (`components/SendDialog.tsx`) — opened by the top-right SEND PixelButton. Fields: recipient username; origin + destination dropdowns (from `/cities`, client-side guard that they differ); body textarea. Submits `POST /messages`; on success it **inserts the returned message into the dashboard's pigeon list immediately** (optimistic — the pigeon shows at once, not up to 10 s later) and closes; the next poll reconciles. Surfaces server errors: 404 "recipient not found", 422 self-send / same city / blank body, 401 (re-auth).

### Data flow summary

`AuthContext` (tokens) → `client.ts` (auth + refresh) → `Dashboard` polls `/messages/sent` + reads cached `/cities` → `WorldMap` projects + animates via `projection`/`flight` → user clicks a pigeon (dialogue box) or SEND (`POST /messages`).

### Build order (phasing within the plan)

The plan sequences tasks so the core payoff lands before the extra auth variant (per reviewer guidance), keeping each stage shippable:

1. Backend CORS + `GET /cities`; Vite/React/TS scaffold; theme/visual system; the API client (with the refresh mutex).
2. Password auth (login/register) + the Dashboard + map engine + Send — the "send a pigeon and watch it fly" payoff, end-to-end.
3. Google sign-in button; the Playwright smoke; visual polish.

Google is still in this milestone — just built after the map works, so there's a working app at each step.

### Testing (Vitest + React Testing Library, jsdom; TDD)

- **Pure units (highest value):** `projection` (e.g. lon 0/lat 0 → {0.5, 0.5}; a known city → expected normalized point); `parseServerUtc` (a timezone-less server string is read as UTC, not local); `flight` (`progress` at t=sent → 0, midpoint → 0.5, past arrival → clamped 1; `interpolate` midpoint; an **antimeridian pair (Tokyo↔San Francisco) takes the short, wrapped path**).
- **API client:** request attaches bearer; `401` → refresh → retry returns the retried result; **concurrent 401s share one refresh** (only one `/auth/refresh` call) and both retry; refresh failure → tokens cleared + logout signaled with **no retry loop**; auth endpoints skip the refresh path (mocked `fetch`).
- **Components:** LoginScreen submit calls auth with field values + shows error on rejected login; Dashboard renders one sprite per pigeon from mocked `/messages/sent` + `/cities`, and clicking a sprite populates the DialogueBox; SendDialog blocks same origin/destination and POSTs valid input.
- **Backend:** `GET /cities` returns 20 cities with coords; CORS configured-origin is reflected.
- **Playwright e2e smoke** (a pixel map can render blank/clipped while unit tests stay green): with a mocked session, the dashboard loads, the map is visible, at least one pigeon sprite renders, and the Send dialog opens — checked at a desktop and a mobile viewport.

### Config & docs

- `frontend/.env.example`: `VITE_API_BASE_URL=http://localhost:8000`, `VITE_GOOGLE_CLIENT_ID=`.
- Backend env: `CORS_ORIGINS=http://localhost:5173` (documented; default baked in).
- README: a "Frontend" section (`cd frontend && npm install && npm run dev`, the env vars), and notes for the new `GET /cities` endpoint + CORS.
- CLAUDE.md: the frontend now exists; add its commands; gotchas (CORS origin via `CORS_ORIGINS`; Google button needs `VITE_GOOGLE_CLIENT_ID`; tokens live in `localStorage`; the pixel map projects lat/lon equirectangularly and animates from message timestamps).

## Risks / notes

- **Scope:** this is the largest single milestone so far (auth ×3, a custom map engine, send, and two backend additions). The implementation plan will decompose it into small TDD tasks; the visual polish is bounded by the agreed style.
- **Great-circle vs straight path:** the backend distance is great-circle, but the map draws a straight dotted line between projected endpoints (taking the shorter, antimeridian-wrapped direction). Acceptable and intentional for the pixel aesthetic; a curved path is possible future polish.
- **Animation vs polling:** position is computed continuously client-side from timestamps (rAF); polling only reconciles status/new pigeons, so motion stays smooth and API load stays low.
- **Security caveat:** `localStorage` tokens are XSS-readable; chosen for simplicity in a dev learning app, with httpOnly-cookie storage as future hardening. CORS is locked to the configured dev origin, not `*`.
- **Timestamps:** the backend emits naive UTC; the frontend parses via `parseServerUtc` (appends `Z`) so progress isn't shifted by the viewer's timezone. Clock skew uses the client clock against server UTC; small skew only nudges a pigeon slightly along its path — acceptable.
