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

    # MongoDB (Atlas) — the app's primary datastore.
    mongodb_uri: str = ""
    mongodb_db: str = "fluently"
    data_dir: str = "./data"

    # --- Google OAuth ("Continue with Google") + session ---
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    # The public base URL of THIS backend. The Google callback is derived from it.
    # In production, set this to e.g. https://api.yourapp.com (also flips cookies to Secure).
    oauth_redirect_base: str = "http://localhost:8000"
    # Where the user's browser is sent after a successful login (the SPA origin).
    frontend_url: str = "http://localhost:5173"
    # Secret used to sign the JWT session cookie (HS256). Generate a strong random value.
    session_secret: str = ""
    # Secret used to sign the short-lived state/nonce cookie during the OAuth handshake.
    state_cookie_secret: str = ""
    session_cookie_name: str = "fluently_session"
    session_max_age_days: int = 7

    @property
    def google_redirect_uri(self) -> str:
        """The exact redirect URI registered in Google Cloud Console."""
        return f"{self.oauth_redirect_base.rstrip('/')}/api/auth/google/callback"

    @property
    def cookie_secure(self) -> bool:
        """Cookies get the Secure flag automatically once the backend is served over https."""
        return self.oauth_redirect_base.lower().startswith("https")

    # User's timezone — all temporal reasoning in the prompt is computed in this zone.
    user_timezone: str = "Asia/Kolkata"

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
