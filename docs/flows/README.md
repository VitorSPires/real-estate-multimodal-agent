# Flows — real-estate-multimodal-agent

> **End-to-end** documentation of each feature: how it really works, from the user's click to the
> database and back.

## Who it's for

1. **Developers** (and future me) — understand how a feature is built without reading all the code.
2. **A future support assistant** — these documents can become the knowledge base (RAG) of an
   assistant that answers end users' questions, so they must be readable by non-technical people.

## Convention

- **One file per feature/journey**, numbered in roadmap order: `01-<feature>.md`, `02-<feature>.md`.
- Always in **English** and self-contained (don't assume the reader has seen the code).
- Every document follows `00-template.md`.

## Why this format

Clear headings and self-contained paragraphs are not just style: when an embedding pipeline chunks
these files, each section becomes an independent searchable piece. A paragraph that says "as
mentioned above" loses its meaning once it's cut out.

No flows yet — the first one (`01-document-ingestion.md`) arrives with Phase 2.
