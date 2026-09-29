# NWIS Dashboard (frontend)

Role-aware operational dashboard for eRTMAC-NWIS (SIH26121), consuming the
existing FastAPI backend at `../api/`. This directory started from a
generic Emergent "farm-ts" starter shell (React 19 + Vite + Tailwind v4 +
shadcn/ui) and has been wired to the real 17-endpoint NWIS API — see
`src/api/backend-types.ts` and `src/api/backend.ts`.

## Layout

```
frontend/
  src/
    api/
      backend-types.ts   TS mirrors of every Pydantic response model
      backend.ts         Typed fetch wrappers for all 17 endpoints
      nwis.ts             (legacy) capability registry from the scaffold
      evidence.ts          (legacy) placeholder evidence shape, still used
                            as EvidenceDrawer's fallback when no real
                            alert/assessment is selected
      types.ts              (legacy) status-check types, unused by NWIS
    auth/
      AuthContext.tsx     Local-storage role switcher (DRILLING_ENGINEER
                            | SYSTEM_ADMIN) — see "Role model" below
      permissions.ts       Permission table per role
    hooks/
      useBackend.ts       One TanStack Query hook per backend endpoint
      useSystemStatus.ts   (legacy) generic status-check hooks, unused
    pages/
      EngineerDashboard.tsx  Wells · Nearby · Similar · Events · Risk ·
                               Alerts · AI query · Document search
      AdminDashboard.tsx     Real /health + /wells KPIs, honestly MOCK-
                               badged admin cards (users, audit, ingest)
      LoginPage.tsx / UnauthorizedPage.tsx / Home.tsx
    components/
      AppShell.tsx          Nav + role badge shell
      EvidenceDrawer.tsx     "Why this alert?" — real Alert/RiskAssessment
                              in, or a legacy placeholder fallback
      StatusBadge.tsx, ApiContractMatrix.tsx, EmptyCapability.tsx
      ui/                    shadcn primitives (Button, Card, Input, …)
```

## Role model

There is no backend auth yet. `AuthContext` persists a role
(`DRILLING_ENGINEER` | `SYSTEM_ADMIN`) to `localStorage`, and
`App.tsx`'s route guards render `UnauthorizedPage` for the wrong role.
This is a **UX-level** separation only — it does not restrict what the
FastAPI backend will answer. Swapping in real server-side auth is a
one-file change: replace `src/auth/authService.ts`'s local-storage
read/write with a real login call, keep the same `AuthUser` shape.

- `DRILLING_ENGINEER`: wells, nearby/similar wells, events, risk,
  alerts, documents, AI query.
- `SYSTEM_ADMIN`: system health (real), wells count (real), AI
  availability probe (real) — users/audit/ingestion are MOCK-badged
  because the backend doesn't expose those endpoints yet (see
  `TODO(backend)` comments in `AdminDashboard.tsx`).

## Running it

Two processes:

```bash
# 1. Backend (from the repo root, not frontend/)
cd ..
source venv/bin/activate
uvicorn api.app:app --reload --host 127.0.0.1 --port 8000

# 2. Frontend
cd frontend
node node_modules/vite/bin/vite.js --port 5173
# (see "Known environment issue" below for why not `npm run dev` directly)
```

Open `http://127.0.0.1:5173`. The Vite dev server proxies `/api/*` →
`http://127.0.0.1:8000/*` (see `vite.config.ts`), so frontend code always
calls relative paths like `apiGet("/wells")` → `/api/wells` → backend
`/wells`. No `VITE_API_BASE_URL` env var needed in dev.

## Known environment issue (already fixed here, documented for the record)

This scaffold's `node_modules` was built against unreleased/private
package versions (`vite@8.1.5`, `typescript@7.0.2`, `react@19.2.8`) shipped
by the Emergent platform (`assets.emergent.sh`), targeting their own Linux
pod. Copying it onto a different machine surfaced two issues, both fixed
in this checkout:

1. **`node_modules/.bin/vite` and `.bin/tsc` were flat file copies, not
   symlinks.** Their scripts use `import "../dist/node/cli.js"` — a path
   that's only correct when the `.bin` entry is a symlink into
   `node_modules/vite/bin/vite.js`. Fixed by recreating the symlinks:
   ```bash
   cd node_modules/.bin
   ln -sf ../vite/bin/vite.js vite
   ln -sf ../typescript/bin/tsc tsc
   ```
2. **Missing native binding for this machine's arch.** `vite@8.1.5` here
   is Rolldown-powered and needs a platform-specific binary
   (`@rolldown/binding-<platform>`). The pod that built this shell was a
   different OS/arch. Fixed with:
   ```bash
   npm install --no-save @rolldown/binding-darwin-arm64   # or your platform
   ```
3. **`typescript@7.0.2`'s own `tsc` binary still shells out to a
   proprietary native compiler** that isn't published anywhere we could
   install it from. Typechecking in this checkout was done with a real
   public `typescript@5.8` invoked directly against
   `tsconfig.app.json` (only pre-existing scaffold-config quirks not
   supported by public TS — `erasableSyntaxOnly`, standalone
   `tsBuildInfoFile` — needed bypassing; zero errors in any actual code).
   If you have access to the Emergent-published `typescript@7.0.2`
   compiler, `npm run typecheck` will work as-is.

None of this required touching `package.json`/`yarn.lock` — it's purely a
local-checkout repair.

## Verified integration (what was actually run, not assumed)

- `curl http://127.0.0.1:8000/health` → real DB-connected response
- `curl http://127.0.0.1:8000/wells?limit=3` → real SODIR-linked wells
  with coordinates
- `curl http://127.0.0.1:8000/risk/assess?dataset=VOLVE&well_id=15/9-F-1`
  → real evidence-based risk assessment
- `curl http://127.0.0.1:8000/risk/alerts?dataset=VOLVE&well_id=15/9-F-1`
  → real alerts with evidence strings
- Frontend dev server booted (`VITE ready`), served `index.html` (200),
  and every new/modified module (`main.tsx`, `App.tsx`,
  `EngineerDashboard.tsx`, `AdminDashboard.tsx`, `useBackend.ts`,
  `backend.ts`, `backend-types.ts`, `EvidenceDrawer.tsx`) transformed
  through Vite with **zero errors** (any syntax/import error there would
  have produced a 500, not a 200).
- Round-trip through the actual dev proxy verified:
  `curl http://127.0.0.1:5173/api/wells?limit=2` returned the same real
  well rows as hitting the backend directly.
- No browser extension was available in this environment to click
  through the UI visually — the checks above verify the wiring is
  correct (types, module graph, live data round-trip) but a manual
  click-through in an actual browser is still worth doing before a demo.

## Demo flow

1. `http://127.0.0.1:5173` → redirected to `/login`.
2. Choose **Drilling Engineer**. Lands on `/engineer`.
3. Type a well id or field name into "Filter by well id, field or
   dataset…" (e.g. `15/9-F-1`), click the row to set it as current well.
4. Current-well bar updates via `GET /wells/state` — if
   `is_simulated: true`, a `DEMO / SIMULATED` chip appears next to the
   depth; never labeled as live telemetry.
5. Nearby wells (`GET /wells/nearby`) and similar wells
   (`GET /wells/similar`) populate; clicking any row makes it the new
   current well.
6. Historical drilling events (`GET /events/well`) list with severity,
   depth, formation, and extraction provenance.
7. Risk & alert station (`GET /risk/assess`, `GET /risk/alerts`) shows
   all 5 risk types — always, even at `LOW` — with score (never called
   "probability") and level.
8. Click a risk card or alert row → **Why this alert?** drawer opens
   with contributing evidence, methodology, historical events,
   limitations, recommended action — every field sourced directly from
   the API response.
9. Ask the AI panel a suggested prompt or free text → `POST /query`; if
   the server has no `GROQ_API_KEY`, it falls back to
   `POST /query/structured` automatically and still returns a real,
   evidence-backed answer for the current well.
10. Document search (`POST /documents/search`) returns real chunk hits
    with similarity and page number.
11. Switch role (via `/login` or the app's role control) to **System
    Administrator** → `/admin`. KPI tiles show real `/health` and
    `/wells` counts and a live AI-availability probe; Users/Audit/
    Ingestion cards are visibly `MOCK`-badged.

## What's real vs. mock

| Area | Status |
|---|---|
| Wells, nearby, similar, context, state | **Real** — `/wells/*` |
| Historical events | **Real** — `/events/*` |
| Risk assessment + alerts | **Real** — `/risk/*` |
| AI query (NL + structured) | **Real** — `/query`, `/query/structured` |
| Document search + metadata | **Real** — `/documents/*` |
| System health | **Real** — `/health` |
| Users & roles, audit log, ingestion pipeline | **Mock** — backend has
  no endpoints yet; every card is badged and carries a `TODO(backend)`
  comment naming the future route |

No fake wells, events, risk scores, or AI answers are ever synthesized
in the real-data panels. Empty results render an honest empty state.
