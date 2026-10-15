# real-estate-multimodal-agent — Build Plan

> Status: **Phase 0 done** — progress in [`ROADMAP.md`](ROADMAP.md). This file is the source of truth for the build.
> Update it in place as decisions change; don't append a log.

---

## 1. What we're building

A voice-first assistant that helps someone choose between apartments using the documents a
broker sent them. The user drops a pile of brochures (PDF) and floor plans (images) into a web
UI. A document-intelligence pipeline reads them, narrates what it finds live, and stores
**verified, evidence-backed** facts per listing. Then the user talks to the assistant in real
time ("I need two bedrooms… and a barbecue grill") and it narrows down the options, explains why,
and shows the exact page/crop each claim came from.

**Why it exists:** portfolio project for AI Engineer roles that ask for document intelligence +
LLM orchestration (first target: an "AI Senior Engineer (Vision)" role). It must stay
**company-agnostic** so the same repo works for any interview.

**Primary deliverable:** a ~2-minute demo video + a README with eval results.
Hosting / live demo is a later, optional step.

### What it demonstrates (mapped to typical JD items)

| JD item | Where it shows up |
|---|---|
| LLM orchestration (LangGraph, tool calling, agentic workflows) | Ingestion graph with conditional routing, verification and model escalation; tool calling in the voice session |
| Multimodal / VLMs reading complex visual documents | Floor plans, phone photos of printed pages, embedded images in brochures |
| Native PDF handling (PyMuPDF), layout | Text blocks + bounding boxes + embedded images extracted natively before any model call |
| Complex prompts / control flows for charts | Price-per-m² chart → structured series |
| Cost optimization (batching, model selection) | Native text skips the VLM; model routing chosen from eval data; cost per document shown in UI |
| Evals / observability | Ground-truth dataset, per-field accuracy per model, live pipeline narration |

### Non-goals (keep scope honest)

- No fine-tuning, no PyTorch in v1 (possible v2: CLIP-based region classifier as a cheap router).
- No auth, no multi-user, no deployment in v1.
- No Docker requirement — a Python venv + `npm` must be enough to run it.
- No real listings or scraped data — the dataset is synthetic so we own the ground truth.

---

## 2. Demo script (the video drives every decision)

Language: **English**. Target length: ~2 min.

1. **(0:00)** Empty app. "A broker sent me four apartments. Let's see what the agent makes of them."
2. **(0:10)** Drag 4 brochures (PDF) + 4 floor plans (PNG) + 1 phone photo of a printed price
   sheet into the drop zone.
3. **(0:15–0:45)** Narration panel streams, auto-expanded:
   - "Brochure B, page 1: native text found — extracting price, area, condo fee (cheap model)"
   - "Floor plan B: no text layer — sending to vision model"
   - "Floor plan B: 3 rooms that could be bedrooms; one labeled *Home office*"
   - "⚠ Conflict: brochure says 2 bedrooms, floor plan shows 2 + office — recorded both"
   - "Brochure D, page 2: price-per-m² chart — extracting 5-year series"
   Listing cards fill in live on the side. Footer shows total cost (e.g. "$0.04 · 9 documents").
4. **(0:45)** Panel collapses. Click the mic.
5. **(0:50–1:45)** Conversation:
   - "Hi! I got some apartment documents from a broker, can you help me pick one?"
   - "I need at least two bedrooms." → assistant names the matching options.
   - "And I really want a barbecue grill." → assistant picks one, explains why, **evidence panel
     opens** on the brochure crop showing the grill.
   - "Is it a good price for the area?" → answers from the extracted chart series.
   - Assistant proactively mentions the bedroom/office conflict on another listing.
6. **(1:45)** Cut to README eval table (accuracy × cost per model). End.

---

## 3. Architecture

```
                    ┌──────────────────────── Browser (React) ─────────────────────────┐
                    │  Drop zone · Narration panel · Listing cards · Chat · Voice orb   │
                    │  Evidence viewer                                                  │
                    └───────┬──────────────────────┬──────────────────────┬─────────────┘
              upload + SSE  │                      │ SDP offer / answer    │ WebRTC audio +
              (narration)   │                      │ tool calls (HTTP)     │ data channel "oai-events"
                    ┌───────▼──────────────────────▼───────┐       ┌───────▼──────────────┐
                    │              FastAPI                  │       │   OpenAI GPT-Live-1  │
                    │  /api/documents   /api/events (SSE)   │──────▶│  (voice, turn-taking)│
                    │  /api/listings    /api/evidence/{id}  │ SDP   │        │ delegation  │
                    │  /api/live/session  /api/live/tools   │ proxy │        ▼             │
                    └───────┬───────────────────┬───────────┘       │ backend model picks  │
                            │                   │                   │ tools (Responses)    │
                ┌───────────▼─────────┐   ┌─────▼──────┐            └──────────────────────┘
                │ Ingestion graph     │   │  SQLite    │
                │ (LangGraph)         │──▶│ listings,  │◀── conversation tools (plain Python,
                │ PyMuPDF · VLMs via  │   │ fields +   │    deterministic queries)
                │ OpenRouter          │   │ evidence   │
                └─────────────────────┘   └────────────┘
```

### Who does what (and why)

| Layer | Owner | Reason |
|---|---|---|
| Listening, speaking, interruptions | GPT-Live-1 | It's what the model is built for |
| Choosing which tool to call mid-conversation | OpenAI backend model via `delegation.type = "responses"` | Built into the Live protocol; no second agent needed |
| Conversation tools | Plain Python functions over SQLite | Fast + deterministic: answers come from verified data, not re-reading images |
| Document ingestion | **LangGraph graph** | This is where real control flow lives: route, extract, verify, escalate, persist |

> Interview line: *"I used LangGraph where there are hard decisions — routing, verification,
> model escalation — and kept the live conversation on deterministic tools over verified data,
> so voice latency never depends on a vision call."*

### Model usage

- **Extraction** → OpenRouter (single client, model is a string). Candidates: one Claude, one GPT,
  one Gemini (Flash-tier). Exact model IDs chosen in Phase 3 from current OpenRouter catalog.
- **Voice** → OpenAI direct (`gpt-live-1` + a backend reasoning model for delegation). GPT-Live is
  its own protocol and is **not** reachable through OpenRouter.
- **Routing rule** is decided by the eval, not by taste. Expected shape: cheap model for native
  text, strongest model only for floor plans / photos / charts, escalation on verification failure.

---

## 4. Data

### 4.1 Synthetic dataset (we own the ground truth)

`dataset/` contains 4 fictional listings (fictional neighborhoods, **USD**, **m²**). Generated by
a script, so every value is known.

Per listing:
- `brochure.pdf` — 2 pages, native text + an embedded photo (generated with `reportlab`).
  One brochure includes a **price-per-m² chart** (matplotlib, 5-year series).
- `floorplan.png` — drawn programmatically (matplotlib rectangles + room labels).
- One listing also has `price-sheet-photo.jpg` — a rendered page warped with perspective + shadow
  (Pillow) to look like a phone photo. No text layer → forces the vision path.
- `ground_truth.json` — the expected value of every field.

**Designed traps** (these make the demo and the eval interesting):
- Brochure says "2 bedrooms", floor plan shows 2 bedrooms + a room labeled "Home office".
- Amenity that only appears in a photo caption / floor plan label (e.g. BBQ grill on the balcony).
- Condo fee present only in the phone photo.
- Price-per-m² stated in text that disagrees with price ÷ area (plausibility check catches it).

### 4.2 Listing schema (Pydantic)

Every field is an `ExtractedField[T]`:

```
value: T | None
evidence: list[Evidence]     # document_id, page, bbox (x0,y0,x1,y1), crop path, quote
method: "native_text" | "vision"
model: str | None
confidence: float            # 0–1, from verification, not from the model's self-report alone
conflict: list[Alternative] | None
```

Fields: `title`, `neighborhood`, `price_usd`, `area_m2`, `price_per_m2`, `bedrooms`, `suites`,
`bathrooms`, `parking_spots`, `floor`, `condo_fee_usd`, `property_tax_usd`,
`amenities` (bbq_grill, pool, gym, gourmet_balcony, pet_friendly, elevator, doorman),
`price_trend` (list of {year, price_per_m2}), `notes`.

### 4.3 SQLite tables

- `documents` — id, filename, kind (pdf|image), sha256, pages, status, listing_id
- `listings` — id, title, merged JSON of the schema above
- `evidence` — id, listing_id, field, document_id, page, bbox, crop_path, quote, method, model
- `model_calls` — id, document_id, node, model, input_tokens, output_tokens, cost_usd, latency_ms
- `events` — id, run_id, ts, type, payload (narration history, replayable)

SQLAlchemy 2.0 models, tables created on startup, no migrations (DECISIONS [001]).

---

## 5. Ingestion graph (LangGraph)

```
            ┌────────────┐
 document ─▶│  classify  │  pdf with text layer? image? which listing does it belong to?
            └─────┬──────┘
        ┌─────────┴──────────┐
        ▼                    ▼
 ┌─────────────┐      ┌──────────────┐
 │ parse_pdf   │      │ prepare_image│  normalize, resize, store page image
 │ (PyMuPDF:   │      └──────┬───────┘
 │ text blocks,│             │
 │ bboxes,     │             │
 │ images,     │             │
 │ page render)│             │
 └──────┬──────┘             │
        ▼                    │
 ┌─────────────┐             │
 │ find_regions│ charts / photos / tables on the page (PyMuPDF image + drawing bboxes)
 └──────┬──────┘             │
        ├──────────┬─────────┘
        ▼          ▼
 ┌────────────┐ ┌──────────────┐
 │extract_text│ │extract_visual│  VLM on crops: floor plan, chart, photo-of-page
 │(cheap LLM, │ │(routed model)│
 │ native txt)│ └──────┬───────┘
 └─────┬──────┘        │
       └───────┬───────┘
               ▼
        ┌────────────┐   schema valid? cross-source consistent? plausible (price ÷ area)?
        │  verify    │
        └─────┬──────┘
     ok ┌─────┼────────────────┐ failed (1st time)
        │     │ failed again    ▼
        │     ▼           ┌────────────┐
        │  record         │  escalate  │ retry same crop with the stronger model
        │  conflict       └─────┬──────┘
        ▼     │                 └──▶ verify
 ┌────────────▼┐
 │ merge_listing│  merge fields from all docs of the listing, keep all evidence
 └──────┬───────┘
        ▼
    persist
```

- **Narration:** each node emits events with LangGraph's custom stream writer
  (`get_stream_writer()`), consumed by `graph.astream(..., stream_mode="custom")` and forwarded to
  the browser over SSE. Events are human-readable sentences + structured payload.
- **Batching:** documents of the same listing run concurrently; visual calls batched per listing.
- **Cost:** every model call writes to `model_calls`; UI footer sums it.
- **Max one escalation per field** — bounded cost, no loops.

---

## 6. Voice layer

Ported **conceptually** from a private reference (protocol only — nothing copied, see §10).

Backend (FastAPI):
- `POST /api/live/session` — receives the browser's SDP offer, calls
  `POST https://api.openai.com/v1/live/sessions` with:
  - `model: "gpt-live-1"`, voice, short spoken-style instructions
  - `delegation: { type: "responses", responses: { model, instructions, tools, tool_choice: "auto",
    parallel_tool_calls: false, max_output_tokens } }`
  - `transport: { type: "webrtc", sdp }`
  Returns the SDP answer. **The OpenAI key never reaches the browser.**
- `POST /api/live/tools` — `{name, arguments}` → runs the tool → JSON result.

Browser (`useLiveSession` hook, rewritten in English):
- `RTCPeerConnection` + mic track + data channel `oai-events`.
- Handles `session.started`, `session.input_transcript.delta/done`,
  `session.output_transcript.delta/done`, `session.delegation.created`,
  `response.event` → `function_call` → POST to `/api/live/tools` →
  `response.item.create (function_call_output)` + `response.create`.
- Typed text goes into the same session (`response.item.create` with `input_text`).

### Conversation tools

| Tool | Does |
|---|---|
| `list_listings()` | Short summary of every listing |
| `filter_listings(criteria)` | Structured filter (min_bedrooms, max_price, required_amenities…) |
| `get_listing(id)` | All fields + confidence + conflicts |
| `compare_listings(ids, aspects)` | Side-by-side on chosen aspects, incl. price vs. neighborhood trend |
| `show_evidence(listing_id, field)` | Returns evidence refs; **the browser reacts by opening the evidence viewer** |

Because tool calls pass through the browser, UI side effects (highlight a card, open evidence) are
free — no extra channel needed.

Backend instructions rule: never state a fact that didn't come from a tool; mention conflicts and
low-confidence fields explicitly.

---

## 7. Frontend

- **Layout:** left column = drop zone + listing cards; center = thread (narration + chat);
  right / overlay = evidence viewer. Voice orb in the composer.
- **assistant-ui vs shadcn rule:**
  - assistant-ui → thread, messages, composer, attachments, reasoning/narration panel, tool-call
    rows, voice orb.
  - shadcn → listing cards, badges, buttons, dialogs, layout primitives.
  - Never hand-build chat pieces with shadcn; never use assistant-ui outside the chat.
- **Runtime:** assistant-ui external-store runtime fed by our own state (SSE narration +
  Live transcript), so one thread shows both ingestion and conversation.
- **Narration panel:** auto-expanded while ingestion runs, collapses on completion.
- **Product name in the header:** "ListingLens" (repo name stays literal).

---

## 8. Repo structure

```
real-estate-multimodal-agent/
  README.md                  # pitch, GIF/video, architecture, eval table, how to run
  docs/
    PLAN.md                  # this file
    architecture.md          # written at the end, from the real code
  backend/
    requirements.txt         # venv + pip, Python 3.13
    app/
      main.py                # FastAPI app + routers
      config.py              # settings from .env
      db.py                  # SQLite / models
      schemas.py             # Listing, ExtractedField, Evidence
      api/                   # documents, events (SSE), listings, evidence, live
      ingestion/
        graph.py             # LangGraph wiring only
        nodes/               # classify, parse_pdf, prepare_image, find_regions,
                             # extract_text, extract_visual, verify, escalate, merge
        prompts/             # one file per prompt, versioned
        llm.py               # OpenRouter client + cost accounting
      live/
        session.py           # SDP exchange + session config
        tools.py             # conversation tool definitions + executors
    tests/
  dataset/
    generate.py              # builds PDFs, floor plans, photo, ground truth
    listings/                # generated output (committed, small)
  evals/
    run.py                   # runs ingestion per model, scores vs ground truth
    results/                 # CSV + markdown table
  frontend/
    (Vite + React + TS + shadcn + assistant-ui)
    src/features/voice/useLiveSession.ts
    src/features/ingestion/useIngestionEvents.ts
  .env.example               # OPENAI_API_KEY, OPENROUTER_API_KEY
  _run/win.bat, _run/mac.command   # one-click start (novo-projeto convention)
```

---

## 9. Phases

Each phase ends with something **runnable** and an **understanding checkpoint**: Vitor walks
through the code in his own words (in English, interview-style) before we move on. Code is
written to be read: small functions, clear names, no clever abstractions.

| # | Phase | Delivers | Done when | Est. |
|---|---|---|---|---|
| 0 | **Scaffold** | Repo via `novo-projeto` skill, venv + Vite, `.env.example`, run scripts, README stub | `run` starts empty backend + frontend; version compat checked (assistant-ui × React/Vite) | 0.5 d |
| 1 | **Dataset** | `dataset/generate.py` + 4 listings + traps + ground truth | Files open correctly; one photo has no text layer; ground truth matches visuals | 0.5–1 d |
| 2 | **Ingestion graph** | Nodes, graph, SQLite persistence, CLI: `python -m app.ingestion dataset/listings` | All 4 listings extracted with evidence; conflict recorded; cost logged | 1.5 d |
| 3 | **Evals + routing** | `evals/run.py`, results table for 3 models, routing config from results | Table per field type × model (accuracy, cost, latency); routing decision written in README | 0.5–1 d |
| 4 | **API** | Upload, SSE narration, listings, evidence crops | Ingestion triggered from HTTP, events visible via `curl` | 0.5 d |
| 5 | **UI (text-only)** | Drop zone, narration panel, cards, evidence viewer, chat | Full demo flow works by typing (this is also the recording fallback) | 1–1.5 d |
| 6 | **Voice** | `/api/live/*`, `useLiveSession`, tools, orb | Spoken demo script runs end to end | 0.5–1 d |
| 7 | **Polish + video** | README, architecture doc, eval table, GIF, recorded video | Video ≤ 2:30, README tells the story in 30 s of reading | 1 d |

**Total:** ~6–8 focused days. If a technical interview lands early, Phases 1–3 alone are already
showable (CLI + eval table).

---

## 10. Rules

- **Clean-room voice code.** The private PoC under `open-source/_temp/` is a protocol reference
  only. Do not copy files, prompts, names, IDs or domain terms from it. Delete `_temp/` (or keep it
  outside this repo) before the first push.
- **No secrets in git.** `.env` ignored from commit #1; `.env.example` only.
- **English everywhere** — code, comments, UI, prompts, README, commits.
- **Company-agnostic.** No employer or prospect names anywhere in the repo.
- **Facts come from tools.** Prompts forbid the voice model from inventing listing facts.
- **Don't over-claim in the README.** Report real eval numbers, including where models failed.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| GPT-Live protocol details changed since the reference (Sep 2026) | Phase 6 starts with a 30-min spike against current docs before writing UI |
| assistant-ui incompatible with React 19 / Vite 8 | Check in Phase 0; pin to versions it supports |
| VLM latency makes ingestion feel slow on video | Concurrency per listing; narration makes waiting feel intentional; edit video if needed |
| Voice demo flaky while recording | Text-only mode (Phase 5) is a full fallback; record several takes |
| Synthetic floor plans too easy (labels = OCR) | Include unlabeled room shapes + the "office vs bedroom" ambiguity |
| Scope creep (PyTorch, hosting, more listings) | Logged as v2 below, not done in v1 |

---

## 12. v2 ideas (not now)

- CLIP embeddings + small PyTorch head as a local region classifier (chart / floor plan / photo /
  text) to skip VLM calls → PyTorch + cost story.
- Docling comparison for layout analysis vs. raw PyMuPDF.
- Hosted demo + live walkthrough script.
- Real (public-domain) brochures as a harder eval split.

---

## 13. Open decisions (resolve during the build)

- [ ] Exact OpenRouter model IDs for the 3-way eval (Phase 3)
- [ ] Backend model for Live delegation (Phase 6)
- [x] ~~SQLModel vs. raw `sqlite3`~~ → SQLAlchemy 2.0 (Phase 0, DECISIONS [001])
- [ ] Voice choice for GPT-Live output (Phase 6)
- [ ] Whether typed text in the voice session should be answered in voice or text (Phase 6)
