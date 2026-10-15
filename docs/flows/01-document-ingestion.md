# 01 — Document ingestion

## What the user sees

The user drops the files a broker sent — PDF brochures, floor-plan images, phone photos of price
sheets. The assistant narrates what it is doing ("reading the brochure's text", "this image is a
floor plan", "the chart reading looks incomplete, retrying with a stronger model") and fills in
one card per apartment. When documents disagree — for example, the brochure says two bedrooms but
the floor plan shows a third room labeled *office* — the card shows both values instead of
silently picking one.

## Step by step

1. **classify** — each file is recognized as a PDF (with or without a text layer) or an image.
2. **parse_pdf / prepare_image** (in parallel) — PDFs are opened with PyMuPDF: the text layer is
   read for free, every embedded picture bigger than 5% of the page is cropped, and every page is
   rendered so evidence can be shown later. Images are copied (and downscaled if huge).
3. **extract_text** — a cheap model reads each brochure's text and returns the listing facts,
   each with the exact quote it came from. The quote is then located in the PDF to get the page
   and the rectangle to highlight.
4. **triage_images** — a cheap vision call decides what each image is: floor plan, chart, photo
   of a document, or just a property photo. Property photos stop here (nothing to extract).
5. **extract_visual** — floor plans, charts and document photos go to the model the routing
   assigns for that kind of image.
6. **verify** — each reading is checked for completeness and plausibility (e.g. a chart with
   fewer than 3 points, room sizes that don't add up to the stated area). A reading with problems
   goes to **escalate**, which retries it once on a model from a different provider. A reading
   that still has problems is kept, with a warning.
7. **merge** — documents are grouped into apartments by their printed title ("HARBOR VIEW 1104"
   on the plan matches "Harbor View 1104" in the brochure). For each field the native-text value
   wins over a vision value; disagreements are kept as conflicts. Price per m² is always computed
   from price and area, and a stated value that disagrees is flagged.
8. **persist** — listings, model calls (tokens, cost, latency) and events are saved to SQLite.

## Rules

- A fact is only reported if a document states it; models are told not to infer or compute.
- Every fact keeps its evidence: document, page, highlight rectangle, quote, method
  (native text / vision / computed) and model.
- Confidence: native text 0.95, vision 0.85; any conflict lowers it to at most 0.67.
- An amenity is `true` if any source mentions it; "not mentioned" is `false` with low confidence.
- Each reading is escalated at most once, so cost is bounded.

## States and errors

- Model call fails (timeout, bad JSON) → treated as a problem → one retry on the escalation model.
- API key rejected → the whole run stops with "The model provider rejected the API key".
- A document whose title can't be read → reported as "couldn't tell which listing this belongs to".
- No API key configured → the app runs in offline mode with canned answers and says so.

## Code references

- Graph wiring: `backend/app/ingestion/graph.py`
- Nodes: `backend/app/ingestion/nodes.py`
- PDF/image parsing: `backend/app/ingestion/documents.py`
- Model outputs → observations: `backend/app/ingestion/observations.py`
- Checks: `backend/app/ingestion/verify.py` · Merge & conflicts: `backend/app/ingestion/merge.py`
- Model routing: `backend/app/ingestion/routing.py` · Prompts: `backend/app/ingestion/prompts/`
- CLI: `python -m app.ingestion ../dataset/listings [--provider fake]`
- API: `POST /api/ingestions` (upload) or `POST /api/ingestions/sample`, then
  `GET /api/ingestions/{run_id}/events` (SSE) and `GET /api/listings` — `app/api/`, `app/ingestion_service.py`
