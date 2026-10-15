# real-estate-multimodal-agent — Project Context

Voice-first assistant that reads apartment documents a broker sent (PDF brochures, floor-plan
images, phone photos), extracts verified facts with evidence, and helps the user pick a listing in
a real-time conversation. Public portfolio project for AI Engineer interviews (document
intelligence + LLM orchestration). UI product name: **ListingLens**.

The full design lives in [`docs/PLAN.md`](docs/PLAN.md). Progress lives in [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Stack

**Frontend (`frontend/`):** React 19 + TypeScript + Vite 8 + Tailwind 4 + shadcn/ui (Radix, Nova preset) + assistant-ui
**Backend (`backend/`):** Python 3.13 + FastAPI + SQLAlchemy 2.0 + Pydantic (venv + `requirements.txt`)
**Database:** SQLite file at `backend/data/app.db` (created on startup, no migrations)
**AI:** LangGraph ingestion graph; extraction models via OpenRouter; voice via OpenAI GPT-Live-1
**Files:** local disk under `backend/data/` (uploads, page renders, evidence crops)
**Auth / Deploy:** none (local demo). Hosting is an optional later step.

---

## Architecture

### Frontend — feature-based
```
src/
├── features/<feature>/         components + hooks of one feature (e.g. features/health)
├── components/ui/              shadcn primitives (cards, buttons, dialogs…)
├── components/assistant-ui/    assistant-ui chat components (thread, composer, reasoning, tools)
└── lib/                        shared helpers (cn, …)
```

### Backend — by responsibility
```
app/
├── main.py         FastAPI app, lifespan, router registration
├── config.py       settings from env / backend/.env
├── db.py           engine, session, Base, init_db
├── api/            HTTP routers (all mounted under /api)
├── ingestion/      LangGraph graph + nodes + prompts   (Phase 2)
└── live/           GPT-Live session + conversation tools (Phase 6)
```

---

## Key decisions

- **IDs:** UUID v7 for database rows; readable slugs (`listing-a`) for dataset listings.
- **Secrets:** `backend/.env` (git-ignored) + `.env.example`. The OpenAI key never reaches the browser — the backend proxies the WebRTC SDP exchange.
- **Facts come from tools:** the voice model never states a listing fact that didn't come from a tool result.
- **LangGraph lives in ingestion**, not in the live conversation (see `docs/DECISIONS.md`).
- **Company-agnostic:** no employer or prospect names anywhere in the repo.
- **Clean-room voice code:** the private PoC in `open-source/_temp/` is a protocol reference only — never copy from it.

---

## Conventions

- Build by **complete feature** (backend + frontend + integration), not by layer.
- **English everywhere:** code, comments, UI copy, prompts, docs, commit messages.
- **assistant-ui vs shadcn:** assistant-ui for anything inside the chat (thread, composer, attachments, reasoning/narration, tool rows, voice orb); shadcn for everything else (cards, badges, dialogs, layout). Never hand-build chat pieces with shadcn.
- Code is written to be **read and explained in an interview**: small functions, clear names, no clever abstractions.
- Every route lives under `/api`; Vite proxies `/api` to `127.0.0.1:8000` in dev.

---

## Running

- One click: `_run/win.bat` (Windows) or `_run/mac.command` (macOS).
- Backend tests: `cd backend && .venv/Scripts/python -m pytest` (`.venv/bin/python` on macOS).
- Frontend build check: `cd frontend && npm run build`.

---

## Living documentation

When a task is completed, update the relevant files in `docs/`:

| Situation | File |
|---|---|
| New technical term | `docs/GLOSSARY.md` |
| New library | `docs/LIBRARIES.md` |
| New pattern or convention | `docs/PATTERNS.md` |
| Architectural decision | `docs/DECISIONS.md` |
| Feature completed or changed (end-to-end flow) | `docs/flows/<NN>-<feature>.md` |
| New plan, or a phase planned/completed | `docs/ROADMAP.md` (forward-looking) |
| Any change | `docs/CHANGELOG.md` ← always required (backward-looking) |

**Rules:**
- Write in English, explaining as if the reader has never seen the term.
- Use examples from this project's code, never generic ones.
- `CHANGELOG.md` entries always include: what was done, why, and which new concept appeared.
- `ROADMAP.md` and `CHANGELOG.md` mirror each other — future and past. `PLAN.md` is the design spec; update it in place when a design decision changes.
- `docs/flows/` documents serve two readers (developers and a future support/RAG assistant), so each section must be self-contained and readable by a non-technical person.
