# Glossary — real-estate-multimodal-agent

> Technical terms in plain English, with examples from this project.

---

## D

**Dev proxy**
In development the frontend (port 5173) and the API (port 8000) are different servers. Instead of
calling the API directly (which would need CORS), the browser calls `/api/...` on the frontend's
own address and Vite forwards the request to FastAPI.
*In this project:* `frontend/vite.config.ts` → `proxy: { '/api': 'http://127.0.0.1:8000' }`.

## E

**External store runtime**
An assistant-ui mode where the chat component doesn't manage messages itself: it renders whatever
list *we* keep in React state and calls us back when the user sends something.
*In this project:* `useExternalStoreRuntime` in `frontend/src/App.tsx`. Later, ingestion
narration and voice transcripts will be appended to that same list.

## L

**Lifespan**
A FastAPI hook that runs code once when the server starts (and once when it stops).
*In this project:* `app/main.py` creates the SQLite database there.

## S

**SQLite**
A database stored in a single file, no server needed.
*In this project:* `backend/data/app.db`, created automatically on startup.
