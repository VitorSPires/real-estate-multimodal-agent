# Changelog — real-estate-multimodal-agent

> What was done, why it was done that way, and what each change teaches.
> Narrative changelog (not the git log). Required after every completed task.

---

## [009] First real-model run (OpenAI) and the fixes it needed

**What was done:**
- First ingestion with real models (OpenAI direct): 4 listings, 20 calls, US$ 0.037, both designed
  conflicts detected, fees read from the tilted photo, BBQ found on the floor plan.
- Fixes found by that run:
  - `backend/.env` now wins over OS environment variables (a stale global key was shadowing it);
    tests disable the `.env` file so they can never use real keys (decision [015]).
  - No `temperature` in requests: gpt-6 models only accept the default (400 otherwise).
  - Structured outputs in **strict** mode via `chat.completions.parse(response_format=Model)`:
    with a non-strict schema, gpt-6-luna sometimes returned the schema itself.
  - Prompt: "Parking: None" means 0, not null (the only eval failure, now fixed).
  - OpenAI-only escalation model: `gpt-6-astra` (`gpt-6.1-sol-pro` doesn't exist).
  - Evals pick only reachable candidates (OpenAI-only without an OpenRouter key) and close the
    HTTP client before the event loop ends.
- First real eval (`evals/results/openai-latest.md`): routed, gpt-6-luna alone and gpt-6.1-sol
  alone all reach 100%; gpt-6-luna costs US$ 0.005 per run vs 0.038 routed.

**Why:** Verify the pipeline against real models, as planned after the offline build.

**New concepts introduced:** strict structured outputs; benchmark saturation (every setup at 100%
means the dataset can't separate models yet).

---

## [008] README, architecture, video script (Phase 7)

**What was done:**
- `README.md` rewritten as the project's showcase (what it demonstrates, how it works with a
  Mermaid diagram, evals, run instructions incl. offline mode, layout, limitations) with 4
  screenshots in `docs/images/` (captured from the running app with headless Edge over CDP).
- `docs/architecture.md` (from the real code) and `docs/VIDEO-SCRIPT.md` (scenes, checklist,
  interview follow-up lines).
- Evidence viewer tabs now show the quote ("USD 298,000" vs "45 m²"), so sources are distinguishable.
- New favicon (house + magnifier) replacing the Vite logo; mobile layout checked (no horizontal scroll).

**Why:** Phase 7 of `PLAN.md` — the repo must tell the story in 30 seconds of reading.

**Not done:** the video itself and the real eval table (both need valid API keys and, for the
video, a microphone).

---

## [007] Voice with GPT-Live-1 (Phase 6)

**What was done:**
- Backend: `app/live/session.py` (Live session config: voice instructions, delegation to a
  Responses model with the conversation tools), `POST /api/live/session` (SDP exchange via the
  OpenAI SDK, key stays server-side), `POST /api/live/tools` (tool relay); 4 tests with a stubbed SDK.
- Frontend: `useLiveSession` (mic, WebRTC, data channel, transcripts by speaker/pause, tool relay,
  mute, hang up), `VoiceControls` in the composer (via a new `ComposerActions` slot in the vendored
  `thread.aui.tsx`), voice transcripts and tool calls appended to the same thread.
- Settings `VOICE_NAME` (default `marin`) and `VOICE_BACKEND_MODEL` (default `gpt-5.6-terra`).

**Why:** Phase 6 of `PLAN.md`.

**New concepts introduced:** WebRTC, SDP, delegation (see `GLOSSARY.md`); decision [014].

**Not verified:** a real voice conversation — the OpenAI key available during the build is
rejected, and the browser pane blocks the microphone. Verified: the session request reaches
OpenAI (401 from the key), the tool relay, error states, and the UI states up to the mic prompt.

---

## [006] Text-only UI wired to the backend (Phase 5)

**What was done:**
- Backend: conversation tools (`app/assistant/tools.py`), shared instructions, text chat tool loop
  (`app/assistant/chat.py`), offline rule-based agent, `POST /api/chat`; 8 new tests.
- Frontend: drop zone + "Try sample documents", live narration in the thread (collapsible),
  listing cards with clickable facts, conflicts and amenities, evidence viewer (page render with
  the source region highlighted), chat with tool-call rows, card highlighting and evidence opening
  driven by tool calls, "Offline mode" badge, "Start over".
- shadcn components added: card, badge, sheet, scroll-area, separator.

**Why:** Phase 5 of `PLAN.md`. The full demo now works by typing — also the fallback for the video.

**New concepts introduced:** tools driving UI side effects; one timeline for several message
sources (decisions [012], [013]).
- *Edited vendored component:* `components/assistant-ui/reasoning.tsx` label changed to
  "Reading the documents" / "How I read the documents".
- *Gotcha:* `uvicorn --reload` did not pick up a change on Windows during the build; restart the
  server if behavior looks stale.

---

## [005] API (Phase 4)

**What was done:**
- `POST /api/ingestions` (multipart upload), `POST /api/ingestions/sample` (bundled dataset),
  `GET /api/ingestions/{id}`, `GET /api/ingestions/{id}/events` (SSE, replay + live),
  `GET /api/listings[/{id}]`, `GET /api/files/{path}` (evidence images, traversal-safe),
  `POST /api/reset`; `/api/health` now reports the active LLM provider.
- `app/ingestion_service.py` runs the graph as a background task; `app/events.py` fans out live events.
- 7 API tests with an isolated data dir and offline answers (`tests/conftest.py`).

**Why:** Phase 4 of `PLAN.md` — the UI needs uploads, a live narration stream and the listings.

**New concepts introduced:** SSE with `Last-Event-ID` replay, replay-then-follow (decision [011]).
- *Gotcha:* an SSE response can't turn into a 404 once streaming starts, so the run is validated
  in a dependency (`existing_run`) before the generator runs.

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
