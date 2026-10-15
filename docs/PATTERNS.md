# Patterns and Conventions — real-estate-multimodal-agent

> Patterns used in the code: what each is, why we use it, and where it appears.

---

## Architecture

### Settings object
**What it is:** One typed `Settings` instance built from env vars / `backend/.env`, imported wherever config is needed.
**Why:** No scattered `os.getenv`; misconfigured types fail at startup.
**In the project:**
```python
# app/config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'app.db'}"
    openai_api_key: str = ""

settings = Settings()
```

### Startup work in `lifespan`
**What it is:** FastAPI's lifespan context runs code once before the app serves requests.
**In the project:** `app/main.py` calls `init_db()` there to create the data folder and tables.

## Frontend

### Feature folders
**What it is:** Code grouped by feature (`src/features/<feature>/`) instead of by file type.
**In the project:** `src/features/health/BackendStatus.tsx`.

### Chat vs. non-chat components
**What it is:** assistant-ui owns everything inside the chat; shadcn owns everything else.
**Why:** Prevents two competing implementations of the same UI piece.
**In the project:** `src/components/assistant-ui/` vs. `src/components/ui/`.

### Adding assistant-ui components
**What it is:** Components come from the assistant-ui registry through the shadcn CLI:
`npx shadcn@latest add https://r.assistant-ui.com/<name>.json`.
**Gotcha:** The CLI drops the files flat in `src/components/` and the registry uses mixed import
paths. After adding one, move the files into `src/components/assistant-ui/` and rewrite imports
(`@/components/assistant-ui/elements/X` → `@/components/assistant-ui/X`, `../utils/X` → `./utils/X`).
Then run `npm run build`.
