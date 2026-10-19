import os
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """App settings, read from environment variables or backend/.env."""

    # ENV_FILE="" disables the .env file (tests do this so they can never pick up real keys).
    model_config = SettingsConfigDict(env_file=os.environ.get("ENV_FILE", BACKEND_DIR / ".env") or None, extra="ignore")

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

    # Voice (GPT-Live-1, OpenAI only)
    voice_name: str = "marin"
    voice_backend_model: str = "gpt-5.6-terra"  # the Responses model the Live session delegates to

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """backend/.env wins over OS environment variables: a stale key set globally on the machine
        must not silently shadow the one configured for this project."""
        return init_settings, dotenv_settings, env_settings, file_secret_settings

    @property
    def resolved_llm_provider(self) -> str:
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.openrouter_api_key:
            return "openrouter"
        return "openai" if self.openai_api_key else "fake"


settings = Settings()
