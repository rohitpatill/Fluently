from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    default_provider: str = "anthropic"
    default_model: str = "claude-sonnet-5"
    judge_provider: str = "anthropic"
    judge_model: str = "claude-haiku-4-5-20251001"
    utility_provider: str = "anthropic"
    utility_model: str = "claude-haiku-4-5-20251001"

    database_url: str = "sqlite:///./data/eng.db"
    data_dir: str = "./data"

    # Scoring matrix (see CLAUDE.md)
    score_perfect_unprompted: float = 5.0
    score_perfect_prompted: float = 3.0
    score_awkward: float = 1.0
    score_wrong: float = -2.0
    score_passive: float = 0.5
    score_daily_cap: float = 10.0
    decay_idle_days: int = 14
    decay_per_week: float = 1.0

    # How many target words to weave into a conversation turn
    target_words_per_conversation: int = 3

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
