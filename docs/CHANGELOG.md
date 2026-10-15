# Changelog — real-estate-multimodal-agent

> What was done, why it was done that way, and what each change teaches.
> Narrative changelog (not the git log). Required after every completed task.

---

## [001] Project scaffold (Phase 0)

**What was done:**
- Backend: FastAPI app with a lifespan hook that creates the SQLite database, settings via
  `pydantic-settings`, SQLAlchemy 2.0 engine/session, `GET /api/health`, and one pytest test.
- Frontend: Vite + React + TypeScript app with Tailwind 4, shadcn/ui (Radix base, Nova preset) and
  the assistant-ui `Thread`. A placeholder runtime (`useExternalStoreRuntime`) echoes a fixed
  reply, and a header badge (`features/health/BackendStatus.tsx`) calls `/api/health` through the
  Vite proxy.
- `_run/` one-click scripts (Windows + macOS), root `.gitignore`, living docs (`CLAUDE.md` + `docs/`).
- Verified: backend test passes, `npm run build` passes, app renders in the browser with
  "Backend online" and the chat round-trip works, no console errors.

**Why:**
Phase 0 of `PLAN.md`. Every later phase plugs into this skeleton: ingestion into `app/`, the
narration stream into the thread runtime, cards into the left column.

**New concepts introduced:**
- *External store runtime* (assistant-ui) — the chat UI renders messages that *we* own in React
  state, so ingestion events and voice transcripts can share one thread. See `GLOSSARY.md`.
- *Dev proxy* — the browser only talks to `/api` on the Vite origin; Vite forwards to FastAPI. The
  target is `127.0.0.1`, not `localhost`, because Node 22 resolves `localhost` to IPv6 first while
  uvicorn listens on IPv4 (this broke the first run with `ECONNREFUSED`).
- assistant-ui's registry mixes import paths (`@/components/assistant-ui/elements/...`, `../utils/...`)
  and the shadcn CLI flattened the files. All of them were moved to `src/components/assistant-ui/`
  and imports rewritten. Re-adding an assistant-ui component may need the same fix
  (see `PATTERNS.md`).
- `httpx2` replaces `httpx` for FastAPI's `TestClient` (Starlette deprecated `httpx`).
- Decisions [001]–[004] in `DECISIONS.md`.
