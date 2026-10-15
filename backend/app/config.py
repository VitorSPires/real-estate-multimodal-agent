from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """App settings, read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    environment: str = "development"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'app.db'}"
    data_dir: Path = BACKEND_DIR / "data"

    # Model providers
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    # auto = OpenRouter if its key is set, else OpenAI, else the offline fake (canned answers).
    llm_provider: Literal["auto", "openrouter", "openai", "fake"] = "auto"
    fake_responses: Path = BACKEND_DIR / "app" / "ingestion" / "fakes" / "dataset_responses.json"
    chat_model: str = ""  # empty = provider default (see app/assistant/chat.py)

    @property
    def resolved_llm_provider(self) -> str:
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.openrouter_api_key:
            return "openrouter"
        return "openai" if self.openai_api_key else "fake"


settings = Settings()
