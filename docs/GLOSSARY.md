# Glossary — real-estate-multimodal-agent

> Technical terms in plain English, with examples from this project.

---

## B

**Baseline (single-model)**
The same pipeline with one model doing every task. The routed setup must beat it on cost, accuracy or both.
*In this project:* `single:<model>` setups in `evals/run.py`.

## D

**Delegation (GPT-Live)**
The voice model hands "thinking" work to another model. With `delegation.type = "responses"`, a
Responses model receives the task, can call our tools, and gives the voice model what to say.
*In this project:* `app/live/session.py` → `session_config()`.

**Dev proxy**
In development the frontend (port 5173) and the API (port 8000) are different servers. Instead of
calling the API directly (which would need CORS), the browser calls `/api/...` on the frontend's
own address and Vite forwards the request to FastAPI.
*In this project:* `frontend/vite.config.ts` → `proxy: { '/api': 'http://127.0.0.1:8000' }`.

## E

**Entity resolution**
Deciding which records describe the same real-world thing.
*In this project:* `merge.listing_key` matches "HARBOR VIEW 1104" (floor plan) with "Harbor View 1104" (brochure).

**Escalation**
Retrying a reading that failed verification with a stronger (and different) model, once.
*In this project:* the `escalate` node, model `Routing.escalation`.

**External store runtime**
An assistant-ui mode where the chat component doesn't manage messages itself: it renders whatever
list *we* keep in React state and calls us back when the user sends something.
*In this project:* `useExternalStoreRuntime` in `frontend/src/App.tsx`. Later, ingestion
narration and voice transcripts will be appended to that same list.

## G

**Ground truth**
The known correct answer for each field, used to score the extraction pipeline.
*In this project:* `dataset/listings/<slug>/ground_truth.json`, generated from `dataset/spec.py`.

## J

**Join edge**
In LangGraph, `add_edge(["a", "b"], "c")` makes `c` wait until both `a` and `b` finished.
*In this project:* `verify` waits for both `extract_text` and `extract_visual`.

## L

**Lifespan**
A FastAPI hook that runs code once when the server starts (and once when it stops).
*In this project:* `app/main.py` creates the SQLite database there.

## N

**Native text layer**
Text stored *as text* inside a PDF (you can select and copy it). Reading it needs no AI. Scanned
pages and photos don't have one: their text is just pixels and needs OCR or a vision model.
*In this project:* the brochures have one; `price-sheet-photo.jpg` doesn't.

## O

**Observation**
One fact from one place in one document, with its evidence (`field`, `value`, `evidence`).
*In this project:* `app/ingestion/schemas.py`; every model reading becomes a list of these.

**Offline mode**
Running the pipeline with canned model answers (`LLM_PROVIDER=fake`), for tests and for exploring
the demo without API keys.

## P

**Perspective transform**
Warping an image so a rectangle becomes a skewed quadrilateral, like a page photographed at an angle.
*In this project:* `dataset/phone_photo.py` → `_degrade_like_phone_photo`.

## S

**SDP (Session Description Protocol)**
The text a WebRTC peer sends to describe its connection (codecs, network candidates). The browser
creates an *offer*; the other side replies with an *answer*.
*In this project:* the browser's offer goes to `POST /api/live/session`, which returns OpenAI's answer.

**SQLite**
A database stored in a single file, no server needed.
*In this project:* `backend/data/app.db`, created automatically on startup.

**SSE (Server-Sent Events)**
A one-way stream from server to browser over a normal HTTP response (`text/event-stream`). The
browser's `EventSource` reconnects automatically and sends the last event id it saw
(`Last-Event-ID`), so the server can resume.
*In this project:* `GET /api/ingestions/{id}/events` streams the pipeline narration.

**Structured output**
Asking a model to answer with JSON that matches a schema (`response_format=json_schema`), then
validating it with Pydantic.
*In this project:* `llm.complete_json(..., schema=TextExtraction)`.

## T

**Triage**
A cheap first look that decides where something goes next.
*In this project:* `triage_images` classifies each image (floor plan, chart, document photo, property photo).

## W

**WebRTC**
Browser technology for real-time audio/video between two peers, plus *data channels* for
messages. Used here for the voice call with GPT-Live-1.
*In this project:* `frontend/src/features/voice/useLiveSession.ts`.
