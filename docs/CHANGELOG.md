# Changelog — real-estate-multimodal-agent

> What was done, why it was done that way, and what each change teaches.
> Narrative changelog (not the git log). Required after every completed task.

---

## [004] Evals and model routing (Phase 3)

**What was done:**
- `evals/score.py`: one check per fact vs. `ground_truth.json`, grouped by source category.
- `evals/run.py`: runs the full pipeline per setup (routed + single-model baselines), writes a
  markdown + JSON report with accuracy per category, cost, calls, escalations and time, and
  suggests a routing per task.
- 5 scorer tests; offline results are git-ignored (they test the harness, not models).

**Why:** Phase 3 of `PLAN.md` — routing must be justified by measurements.

**New concepts introduced:** eval categories, single-model baseline (decision [010]).
**Not done:** the real eval run (no valid API key during the build — see `REVIEW-NOTES.md`).

---

## [003] Ingestion graph (Phase 2)

**What was done:**
- `app/ingestion/`: LangGraph graph (`graph.py`) with nodes classify -> parse_pdf || prepare_image ->
  extract_text || (triage_images -> extract_visual) -> verify <-> escalate -> merge -> persist.
- PDF parsing with PyMuPDF (text layer, embedded images, page renders, quote -> bbox lookup).
- `llm.py`: one `complete_json` interface; OpenRouter / OpenAI via the OpenAI SDK, and a
  `FakeLLMClient` with canned answers. `routing.py`: model per task.
- `observations.py`, `verify.py`, `merge.py`: pure functions for evidence, checks and merging.
- SQLite tables (`models.py`) and `store.py`; CLI `python -m app.ingestion`.
- 22 new tests, including the full graph over the dataset (offline).
- Dataset files renamed to unique, broker-style names.

**Why:** Phase 2 of `PLAN.md` — the core of the project.

**New concepts introduced:** observation, triage, escalation, entity resolution, structured
output, join edge (see `GLOSSARY.md`); decisions [006]–[009].
- *Gotcha:* the Windows console (cp1252) can't print `→`/`⚠`; the CLI reconfigures stdout to UTF-8.

---

## [002] Synthetic dataset (Phase 1)

**What was done:**
- `dataset/spec.py` describes the four listings (facts, floor-plan rooms, where each fact is
  printed, and the traps). It is the single source of truth.
- Renderers: `brochure.py` (reportlab PDF with a native text layer), `images.py` (floor plans,
  stylized building photos, neighborhood price chart with matplotlib), `phone_photo.py` (price
  sheet drawn with Pillow, then warped, shaded, noised and blurred like a phone photo).
- `generate.py` writes `dataset/listings/<slug>/` with the documents and `ground_truth.json`.
- `test_dataset.py` (9 tests): floor plans agree with the facts, the demo query has exactly one
  answer, brochures have extractable text, the traps are where we put them, and generation is
  byte-identical across runs.

**Why:**
Phase 1 of `PLAN.md`. Evals (Phase 3) need documents whose correct answers we know exactly; real
brochures would need hand labeling and can't be published.

**New concepts introduced:**
- *Ground truth derived from the generator* — documents and expected answers come from the same
  objects, so they can't disagree. Traps are explicit spec fields, not accidents. See `DECISIONS.md` [005].
- *Native text layer vs. image-only document* — the brochures carry real text (PyMuPDF reads it
  for free), while the phone photo has none and must go through a vision model. See `GLOSSARY.md`.
- *Determinism gotcha* — reportlab names embedded images after their file path, so rendering them
  to temp files made every PDF different. Images are now rendered in memory (`BytesIO`), and
  ground-truth dict order no longer depends on `frozenset` iteration. A test guards this.

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
