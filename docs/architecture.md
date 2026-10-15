# Architecture

Written from the code as it is. The original design is in [`PLAN.md`](PLAN.md); the reasons behind
each choice are in [`DECISIONS.md`](DECISIONS.md).

## Components

```
Browser (React)                               Backend (FastAPI, one process)
─────────────────                             ───────────────────────────────────────────
DropZone ── POST /api/ingestions ───────────▶ ingestion_service ── asyncio task ──┐
useIngestion ◀── SSE /ingestions/{id}/events ◀ events (DB + in-memory fan-out)    │
ListingCard ◀── GET /api/listings ◀───────── store (SQLite)  ◀── persist ◀── LangGraph graph
EvidenceViewer ◀── GET /api/files/... ◀───── page renders / crops / uploads (data/)
Thread (assistant-ui) ── POST /api/chat ────▶ assistant/chat.py ── tools ── store
useLiveSession ── POST /api/live/session ───▶ live/session.py ── OpenAI client.live.create
     ▲  WebRTC audio + data channel ◀──────────────────────────────▶ GPT-Live-1 (OpenAI)
     └── POST /api/live/tools ──────────────▶ assistant/tools.py ── store
```

## Ingestion graph

`backend/app/ingestion/graph.py` wires the nodes in `nodes.py`:

| Node | Does | Model |
|---|---|---|
| `classify` | PDF with text layer / scanned PDF / image | — |
| `parse_pdf` ∥ `prepare_image` | text layer, embedded image crops, page renders; image copies | — |
| `extract_text` | brochure text → `TextExtraction` (values + quotes) | `routing.text` (cheap) |
| `triage_images` | image kind: floor plan / chart / document photo / property photo | `routing.triage` (cheap) |
| `extract_visual` | floor plan → rooms + amenities; chart → series; photo → facts | per kind (strong) |
| `verify` | completeness + plausibility per reading (`verify.py`) | — |
| `escalate` | re-read readings with problems, once | `routing.escalation` (other provider) |
| `merge` | group by title, choose values, record conflicts (`merge.py`) | — |
| `persist` | listings, model calls, cost → SQLite | — |

State is a `TypedDict` with reducers where two nodes write the same key (`regions` from both parse
branches, `extractions` keyed by region). Dependencies (LLM client, routing, folders, store) are
injected as LangGraph *runtime context*, not kept in state. Nodes narrate with
`get_stream_writer()`; the runner forwards those events to the CLI, the SSE stream or the evals.

### Data shapes (`schemas.py`)

1. **LLM outputs** — `TextExtraction`, `RegionTriage`, `FloorPlanReading`, `ChartReading`.
2. **Observations** — `Observation(field, value, evidence)`, produced by `observations.py`.
   Evidence = document, page, normalized bbox, quote, method, model, image path.
3. **ListingRecord** — fields, amenities and price trend as `FieldValue(value, confidence,
   evidence, conflict)`. Stored whole as JSON in `listings.record`.

## Model access (`llm.py`, `routing.py`)

One method: `complete_json(model, system, user_text, schema, images, call_key)`.
`OpenAICompatibleClient` serves OpenRouter and OpenAI (Chat Completions + `json_schema` response
format; OpenRouter reports exact cost, otherwise a price table estimates it). `FakeLLMClient`
answers from `ingestion/fakes/dataset_responses.json` (offline mode, tests). `Routing` maps each
task to a model; `LLM_PROVIDER=auto` picks OpenRouter → OpenAI → offline.

## Conversation (`assistant/`)

Six deterministic tools over the stored listings: `list_listings`, `filter_listings`,
`get_listing`, `compare_listings`, `neighborhood_price_check`, `show_evidence`. They are exposed in
two formats: Chat Completions (text chat loop, max 5 rounds) and Responses-API function tools
(GPT-Live delegation). Shared instructions in `instructions.py`. Offline, `offline.py` plays the
model with simple rules.

## Voice (`live/`, `features/voice/`)

The browser creates a WebRTC offer; `POST /api/live/session` calls `client.live.create` with
`gpt-live-1`, short voice instructions, and `delegation.type = "responses"` (backend model + the
tools). OpenAI's SDP answer goes back to the browser; audio flows directly. Tool calls arrive on the
data channel as `response.event` → `function_call`; the browser runs them via `POST /api/live/tools`
and replies with `function_call_output` + `response.create`. Transcript deltas become thread
messages (new message on speaker change or a 1.2 s pause).

## Frontend

- `useIngestion` — starts runs, follows SSE (`EventSource` resumes with `Last-Event-ID`).
- `useAssistantThread` — one timeline (runs + typed + voice messages) rendered by assistant-ui via
  an external-store runtime; a run is a message whose *reasoning* part is the narration.
- `App.onStep` — tool results drive the UI: `show_evidence` opens the viewer, `filter_listings`
  highlights cards.
- `EvidenceViewer` — page render with the bbox overlay, all sources and conflicts.
- Component split: `components/assistant-ui/` (chat), `components/ui/` (shadcn), `features/` (app).

## Persistence

SQLite (`backend/data/app.db`) via SQLAlchemy 2.0; tables `ingestion_runs`, `documents`,
`listings`, `model_calls`, `events`. Files per run under `backend/data/runs/<run_id>/`
(`uploads/`, `pages/`, `regions/`, `images/`). Everything is local and git-ignored.

## Testing

- `backend/tests` — merge/verify units, full graph over the dataset (offline), API (SSE replay,
  uploads, file safety), tools + offline agent, voice endpoints with a stubbed SDK.
- `dataset/test_dataset.py` — spec consistency, traps, deterministic generation.
- `evals/test_score.py` — scorer.
