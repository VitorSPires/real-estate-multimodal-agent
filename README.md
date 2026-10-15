# real-estate-multimodal-agent

> 🚧 Work in progress — see [`docs/ROADMAP.md`](docs/ROADMAP.md).

**ListingLens** is a voice-first assistant that reads the documents a broker sent you — PDF
brochures, floor plans, phone photos of printed price sheets — extracts verified facts with
evidence, and helps you choose an apartment in a real-time conversation.

**What it demonstrates:** document intelligence with vision-language models, native PDF parsing,
LangGraph orchestration with verification and model escalation, eval-driven model routing, and a
real-time voice interface (OpenAI GPT-Live-1) backed by deterministic tools.

## Run it

Requirements: Python 3.13+, Node 22+.

1. Copy `backend/.env.example` to `backend/.env` and fill in the keys (the `_run` script does the copy for you).
2. Double-click `_run/win.bat` (Windows) or `_run/mac.command` (macOS).
3. Open http://localhost:5173.

## Docs

- [`docs/PLAN.md`](docs/PLAN.md) — design and build plan
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — architectural decisions
