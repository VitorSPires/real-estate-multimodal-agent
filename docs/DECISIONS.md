# Architectural Decisions — real-estate-multimodal-agent

> ADRs: each important decision with context, options and why it won.
> Numbered, never deleted — a reverted decision becomes a new one that references the old.

---

## [001] SQLite + SQLAlchemy 2.0, no migrations

**Context:** Public demo repo; anyone cloning it should run it with zero setup. Data volume is a
handful of listings.

**Options considered:**
- **PostgreSQL (house default)** — production-grade, but needs a server or a managed instance to run the demo.
- **SQLModel** — Pydantic-native, less code, but another abstraction to explain.
- **SQLite + SQLAlchemy 2.0** — file-based, zero setup, same ORM as the house standard.

**Choice:** SQLite + SQLAlchemy 2.0. Tables are created on startup (`init_db`), no Alembic.

**Why:** Zero-setup clone-and-run matters more than migrations for a demo. Keeping SQLAlchemy
means the code transfers directly to Postgres if the project ever grows.

---

## [002] LangGraph in ingestion, deterministic tools in the conversation

**Context:** GPT-Live-1 delegates reasoning and tool choice to an OpenAI backend model
(`delegation.type = "responses"`). A LangGraph agent behind a voice tool would add a second "brain"
and latency.

**Options considered:**
- **LangGraph agent as a voice tool** — shows LangGraph in the conversation, but doubles reasoning and adds seconds of silence.
- **LangGraph for ingestion, plain functions as voice tools** — graph where real control flow exists (routing, verification, escalation); fast deterministic queries in the call.

**Choice:** LangGraph for ingestion only. Voice tools are plain Python over SQLite.

**Why:** Voice latency must never depend on a vision call, and answers must come from verified
data. It also gives a clear interview story about *where* orchestration belongs.

---

## [003] OpenRouter for extraction, OpenAI direct for voice

**Context:** We want to compare several vision models and route by measured accuracy and cost.
GPT-Live uses its own protocol and is not available through OpenRouter.

**Choice:** Extraction calls go through OpenRouter (model = a string, one key). Voice uses the
OpenAI API directly.

**Why:** One client makes the 3-model eval cheap to build; the final routing is chosen from eval
data (Phase 3), not by preference.

---

## [009] Evidence stored inside the listing JSON

**Context:** The plan listed a separate `evidence` table.

**Choice:** `listings.record` holds the whole `ListingRecord` (fields, conflicts, evidence) as JSON.

**Why:** The record is always read and written as a unit (API, voice tools, UI card). A table
would add joins without enabling any query we need. Revisit if we ever search across evidence.

---

## [008] Observations, title-based grouping and the conflict policy

**Context:** Facts arrive from different documents, read by different models, sometimes disagreeing.

**Choice:**
- Every reading is converted to `Observation`s (field, value, evidence) before merging.
- Documents are grouped into listings by a normalized printed title (`listing_key`).
- Per field: native text beats vision; disagreeing values are kept as `conflict` alternatives.
- Price per m² is always computed from price and area; a stated value off by >3% is a conflict.
- A room labeled *office* on the plan produces a "bedrooms + offices" alternative.
- Confidence: fixed constants (native text 0.95, vision 0.85, conflict <= 0.67).

**Why:** Merge logic stays independent of models and document types, and is unit-testable.
Keeping conflicts instead of resolving them is the product: the buyer should see the
disagreement. **Limitation:** confidence values are heuristics, not calibrated probabilities.

---

## [007] Image triage before extraction; escalation to a different provider

**Context:** Brochures embed decorative photos next to charts; vision calls on strong models are the main cost.

**Choice:** A `triage_images` node classifies each image with a cheap model; only floor plans,
charts and document photos go to the (routed) strong model. A reading that fails verification is
retried once on `Routing.escalation`, a model from a different provider.

**Why:** Cost (decorative images never reach an expensive model) and robustness (a second
provider is less likely to repeat the same mistake). Bounded: one escalation per reading.

---

## [006] Automatic provider selection and an offline mode with canned answers

**Context:** The repo is public and must be explorable without API keys; during the autonomous
build no valid key was available.

**Options considered:**
- **Require keys** — honest, but nobody can click through the demo without paying.
- **Offline mode with canned answers** — the full pipeline and UI run; answers come from fixtures.

**Choice:** `LLM_PROVIDER=auto` picks OpenRouter -> OpenAI -> offline (`fake`). Fixtures are
generated from the dataset spec (`dataset/make_fake_llm.py`) with one deliberate error to
exercise escalation. Offline mode announces itself in the narration and in the UI.

**Why:** Tests and UI development need deterministic model answers anyway; reusing them as an
offline demo is free. Clearly labeled so it is never mistaken for model results.

---

## [005] Synthetic dataset generated from a spec

**Context:** Evals need documents with known correct answers, and the repo is public.

**Options considered:**
- **Real brochures** — realistic, but need manual labeling and can't be redistributed.
- **AI-generated images** — look real, but the content isn't controllable, so there's no exact ground truth.
- **Programmatic generation from a spec** — less photo-realistic, but every value is known and the traps are deliberate.

**Choice:** Programmatic generation (`dataset/spec.py` → renderers → `ground_truth.json`).

**Why:** Exact ground truth and designed traps matter more than realism for measuring extraction.
Realism comes from the hard parts (unlabeled chart, shorthand floor plans, degraded phone photo).
Real public-domain brochures stay a v2 idea for a harder eval split.

---

## [004] Monorepo with `backend/` and `frontend/`, venv + requirements.txt

**Context:** House convention suggests `<project>-backend` / `<project>-frontend` and the plan
mentioned `uv`.

**Choice:** Short folder names (`backend/`, `frontend/`) and a plain venv + `requirements.txt`
on Python 3.13.

**Why:** The project name is long; short names read better in the README and match the `_run`
scripts. `uv` is not installed on the dev machine and the `_run` scripts' reinstall-on-change
check is built around `requirements.txt`.
