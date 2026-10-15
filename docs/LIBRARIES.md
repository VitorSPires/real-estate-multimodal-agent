# Libraries — real-estate-multimodal-agent

> For each library: what it is, why we chose it, alternatives, and how we use it here.

---

## Frontend

### assistant-ui (`@assistant-ui/react`)
**What it is:** React building blocks for AI chat UIs — thread, composer, attachments, reasoning
and tool-call rendering — distributed shadcn-style (the component code is copied into the repo).
**Why we chose it:** The demo needs a polished chat with a live "what the pipeline is doing" panel
and tool-call rows; building that by hand would eat days.
**Alternatives:** Vercel AI SDK Elements (tied to the AI SDK runtime); hand-built shadcn chat (slow).
**How we use it:** `src/components/assistant-ui/` holds the components; `App.tsx` feeds the
`Thread` through `useExternalStoreRuntime`, so we own the message state.

### shadcn/ui (Radix base, Nova preset)
**What it is:** A collection of accessible components (Radix + Tailwind) copied into the repo
instead of installed as a dependency.
**Why we chose it:** House standard, and assistant-ui is built on the same tokens, so both share
one theme.
**Alternatives:** MUI / Chakra (heavier, separate theming).
**How we use it:** `src/components/ui/` — listing cards, badges, dialogs, buttons.

### Tailwind CSS 4
**What it is:** Utility-first CSS, configured from `src/index.css` (no `tailwind.config`).
**Why / how:** Required by shadcn and assistant-ui. Loaded via the `@tailwindcss/vite` plugin.

## Backend

### FastAPI
**What it is:** Async Python web framework with Pydantic validation and auto OpenAPI docs.
**Why we chose it:** House standard; native fit for streaming (SSE) and Python AI libraries.
**How we use it:** `app/main.py`; routers in `app/api/`, all under `/api`.

### SQLAlchemy 2.0
**What it is:** Python ORM / SQL toolkit.
**Why we chose it:** House standard; works the same on SQLite and Postgres. See DECISIONS [001].
**How we use it:** `app/db.py` — engine, `SessionLocal`, `Base`, `init_db()`.

### PyMuPDF (`pymupdf`)
**What it is:** Fast PDF library: text with positions (bounding boxes), embedded images, page rendering.
**Why we chose it:** Reading the native text layer costs nothing, and bounding boxes give us evidence locations for free.
**Alternatives:** pdfplumber (great for tables, slower), Docling (layout models, heavier — v2 comparison).
**How we use it:** Dataset tests check the brochures' text layer; Phase 2 parses PDFs with it.

### reportlab
**What it is:** Python library that writes PDFs.
**How we use it:** `dataset/brochure.py` builds the brochures (`SimpleDocTemplate` + flowables).
`rl_config.invariant = 1` keeps output byte-identical.

### matplotlib
**What it is:** Plotting library.
**How we use it:** `dataset/images.py` draws floor plans, stylized building photos and the price chart.

### Pillow
**What it is:** Image manipulation library.
**How we use it:** `dataset/phone_photo.py` draws the price sheet and degrades it (perspective
warp, shading, noise, blur) to look like a phone photo.

### pydantic-settings
**What it is:** Typed settings loaded from environment variables and `.env`.
**How we use it:** `app/config.py` — `settings.openai_api_key`, `settings.database_url`, …

### pytest + httpx2
**What it is:** Test runner, plus the HTTP client FastAPI's `TestClient` now uses (`httpx` was deprecated by Starlette).
**How we use it:** `backend/tests/`.
