# Review notes — autonomous build (Phases 2–7)

> Vitor asked me to build the remaining phases alone and log every decision for a later review.
> Each item says **what I decided**, **why**, and **what to check**. Full ADRs live in
> `DECISIONS.md`; this file is the short checklist for our review session.

---

## ⚠️ Blockers found

- **The `OPENAI_API_KEY` in your Windows user environment is rejected by OpenAI
  (`invalid_api_key`)**, and there is no `OPENROUTER_API_KEY`. So **no real model call was made
  during this build**. Everything was built and tested with canned model answers
  (`FakeLLMClient`). What still needs a real run once keys exist:
  - Phase 2: `python -m app.ingestion ../dataset/listings` with a real provider.
  - Phase 3: the eval table (`python -m evals.run`) — numbers in the README are placeholders until then.
  - Phase 6: the voice session (also needs your microphone).
- Model IDs come from the public OpenRouter catalog (Oct 2026). OpenAI-direct names
  (`gpt-6-luna`, `gpt-6.1-sol`, `gpt-6.1-sol-pro`) are assumed to be the OpenRouter ids without
  the `openai/` prefix — unverified.

## Phase 1 follow-up

- **Dataset files renamed** to broker-style unique names (`harbor-view-1104-brochure.pdf`), because
  dragging 9 files into the UI with four called `brochure.pdf` would collide.

## Phase 2 — Ingestion graph

- **Provider selection is automatic** (`LLM_PROVIDER=auto`): OpenRouter if its key exists, else
  OpenAI, else **offline mode** with canned answers (clearly announced in the narration). Lets
  anyone clone and click through the demo without keys. → DECISIONS [006]
- **Canned answers are generated from `dataset/spec.py`** (`dataset/make_fake_llm.py`) with one
  deliberate mistake (first chart reading has 2 points) so the escalation path is exercised.
  They are a test double — never presented as results. → DECISIONS [006]
- **Added a `triage_images` node** (not in the original plan): a cheap vision call classifies each
  image first, so property photos never reach an expensive model. → DECISIONS [007]
- **Everything becomes an `Observation`** (field + value + evidence) before merging, so merge and
  conflicts don't care which model or document type produced a fact. → DECISIONS [008]
- **Listings are grouped by printed title** (entity resolution on a normalized key). Simple and
  explainable; fails if a document has no title (reported as "unassigned"). → DECISIONS [008]
- **Conflict policy:** native text beats vision; price per m² is always computed; office rooms
  produce a bedrooms+offices alternative. Confidence numbers are fixed constants, not calibrated.
  → DECISIONS [008]
- **Escalation goes to a different provider** (Claude → GPT) for a second opinion, max once per
  reading. → DECISIONS [007]
- **A rejected API key aborts the run** instead of escalating (it would fail again). Error
  messages never include the key.
- **Evidence is stored inside the listing JSON**, not in a separate table as the plan said. The
  record is always read whole; a table would add joins without new queries. → DECISIONS [009]
- **Concurrency inside nodes with `asyncio.gather` + a semaphore (6)** instead of LangGraph's
  `Send` fan-out. Simpler to read; the graph still shows the parallel branches that matter.

## Phase 3 — Evals

- **Scoring by source category** (brochure text, phone photo, floor plan, chart, conflicts) instead
  of one global number, plus single-model baselines. → DECISIONS [010]
- **Candidate models:** 3 cheap (`claude-haiku-5.5`, `gpt-6-luna`, `gemini-3.8-flash`) + 3 strong
  (`claude-sonnet-5.5`, `gpt-6.1-sol`, `gemini-4-argon`) from the OpenRouter catalog. Full run =
  7 ingestions × ~21 calls; I expect well under US$ 1, but it was not run.
- **Offline eval results are git-ignored** — they only prove the harness works. Commit the real
  `evals/results/openrouter-latest.md` once it runs, and update `routing.py` from its suggestion.
- **Escalation inside single-model baselines uses the same model** (so baselines show what a
  single model really does alone).

## Phase 4 — API

- **Runs are `asyncio` background tasks inside the API process** (no Celery/Redis). Fine for a
  demo; a server restart mid-run leaves the run "running". → DECISIONS [011]
- **SSE, not WebSocket**, for the narration (one-way stream, free reconnects with `Last-Event-ID`).
- **Added `POST /api/ingestions/sample`** (not in the plan): ingests the bundled dataset, so a
  visitor can try the app without having documents. The UI gets a "Try sample documents" button.
- **Added `POST /api/reset`** to clear runs and listings between demo takes.
- **Your local `backend/.env` has `LLM_PROVIDER=fake`** (git-ignored) because the OpenAI key is
  invalid. Switch it to `auto` after adding valid keys.
- Uploads limited to 30 files × 20 MB; file names are reduced to their base name (no client paths).
