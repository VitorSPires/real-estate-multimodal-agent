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

## Phase 5 — Text UI

- **One set of conversation tools** (`app/assistant/tools.py`) for text chat and voice; pure
  functions over SQLite, no model calls. → DECISIONS [012]
- **Added a `neighborhood_price_check` tool** (not in the plan) for the demo question "is it a good
  price for the area?" — it uses the chart from *any* brochure of the same neighborhood.
- **Offline chat is a rule-based agent** that only knows the demo conversation (bedrooms,
  amenities, price, compare). Labeled offline; real chat uses `claude-sonnet-5.5` (OpenRouter)
  or `gpt-6.1-sol` (OpenAI), overridable with `CHAT_MODEL`.
- **Cards appear when merging finishes**, not progressively per document as the plan said. The
  narration streams live, which carries the "watch it work" moment; provisional cards would add
  state-juggling code for little gain. Easy to add later from the `facts` events (already emitted).
- **Narration = assistant-ui "reasoning" part**, label changed in the vendored component.
  → DECISIONS [013]
- **Starter suggestions disappear after the first message** (they'd be stale).
- **Floor-plan evidence highlights the whole image**, not the BBQ symbol itself: vision readings
  don't return coordinates. Possible upgrade: ask the model for a bounding box per amenity.

## Phase 6 — Voice

- **Not verified end to end** (invalid key + the browser pane blocks the mic). What *is* verified:
  `client.live.create` reaches OpenAI (it answered 401 for the key), the tool relay, error states,
  and the UI up to the microphone prompt. **First thing to test with a valid key.**
- **Session created with the OpenAI SDK** (`client.live.create`), not a raw HTTP call; event names
  taken from the SDK's types (transcripts are delta-only — there is no `.done` event, so turns are
  split on speaker change or a 1.2 s pause). → DECISIONS [014]
- **Tools relayed by the browser** (like your PoC) rather than a server sideband connection. The
  UI reacts to results for free; sideband is the production upgrade.
- **Defaults:** voice `marin` (SDK default), delegated model `gpt-5.6-terra` (the one your PoC
  used successfully). Both configurable (`VOICE_NAME`, `VOICE_BACKEND_MODEL`).
- **Greeting:** on `session.started` the app appends an instruction asking for a one-sentence greeting.
- **Typed messages during a call go to the text chat**, not into the voice session. The two
  "brains" don't share context — acceptable for the demo script (talk *or* type), worth unifying later.
- **Voice controls live in the composer** via a small slot added to the vendored `thread.aui.tsx`
  (instead of assistant-ui's own voice runtime, which expects its own adapter).
- **No frontend unit tests** (no test runner set up in the frontend); voice logic is only typed and
  built. A Vitest suite for `useLiveSession`'s event handling would be a good follow-up.
