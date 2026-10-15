# Roadmap — real-estate-multimodal-agent

> What we still have to build, in approximate order. Forward-looking mirror of `CHANGELOG.md`
> (which records what is done). The *how* of each phase lives in [`PLAN.md`](PLAN.md) §9.
>
> Legend: ✅ done · 🔜 next · 📋 planned · 💡 idea/future

---

## Phase 0 — Scaffold ✅
- ✅ Repo, living docs, backend (FastAPI + SQLite), frontend (Vite + shadcn + assistant-ui), `_run` scripts

## Phase 1 — Synthetic dataset ✅
- ✅ `dataset/generate.py`: 4 listings (brochure PDF, floor plan PNG, one phone photo, one price chart)
- ✅ Designed traps + `ground_truth.json` per listing (see `dataset/README.md`)

## Phase 2 — Ingestion graph ✅
- ✅ Schema, SQLite tables, LangGraph graph with triage + escalation, cost accounting, CLI
- 📋 First run with real models (needs a valid API key — see `REVIEW-NOTES.md`)

## Phase 3 — Evals + model routing ✅
- ✅ `evals/run.py` + scorer: accuracy per source category × cost × time, routing suggestion
- 📋 Real run with OpenRouter and routing update from its results (needs key)

## Phase 4 — API ✅
- ✅ Upload + sample runs, SSE narration (replay + live), listings, evidence files, reset

## Phase 5 — UI (text-only) ✅
- ✅ Drop zone + samples, narration panel, listing cards, evidence viewer, chat with tools

## Phase 6 — Voice 🔜
- 🔜 Spike against current GPT-Live docs
- 📋 `/api/live/session` (SDP proxy) + `/api/live/tools`, `useLiveSession` hook, voice orb

## Phase 7 — Polish + video
- 📋 README story, architecture doc, eval table, recorded demo video

## Future 💡
- 💡 CLIP + small PyTorch head as a local region classifier (cheaper routing)
- 💡 Docling vs. PyMuPDF layout comparison
- 💡 Hosted demo + live walkthrough script
