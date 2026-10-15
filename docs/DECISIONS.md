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

## [004] Monorepo with `backend/` and `frontend/`, venv + requirements.txt

**Context:** House convention suggests `<project>-backend` / `<project>-frontend` and the plan
mentioned `uv`.

**Choice:** Short folder names (`backend/`, `frontend/`) and a plain venv + `requirements.txt`
on Python 3.13.

**Why:** The project name is long; short names read better in the README and match the `_run`
scripts. `uv` is not installed on the dev machine and the `_run` scripts' reinstall-on-change
check is built around `requirements.txt`.
