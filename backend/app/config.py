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

    # --- Bring-your-own-key model tiers (per-user Gemini keys) ---
    # Symmetric key (Fernet) used to encrypt users' API keys at rest. Generate with
    # `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
    # Kept ONLY in .env — never in the DB. A DB leak alone yields useless ciphertext.
    encryption_key: str = ""

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

    @property
    def cross_site(self) -> bool:
        """True when the frontend and backend are on different sites (registrable domains).
        In that case the session cookie must be SameSite=None + Secure to survive at all."""
        def host(url: str) -> str:
            u = url.lower().split("://", 1)[-1]
            return u.split("/", 1)[0].split(":", 1)[0]

        be, fe = host(self.oauth_redirect_base), host(self.frontend_url)
        if be == fe:
            return False
        # Compare the last two labels (registrable-ish): api.x.com vs app.x.com -> same site.
        return be.split(".")[-2:] != fe.split(".")[-2:]

    @property
    def cookie_samesite(self) -> str:
        """'none' for cross-site deployments (SPA and API on different domains), else 'lax'.
        Browsers only accept SameSite=None when the cookie is also Secure (https)."""
        return "none" if (self.cross_site and self.cookie_secure) else "lax"

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


# --- Model tiers (the two "brains" a user can pick) ------------------------------------
# SINGLE SOURCE OF TRUTH for the Swift/Sage choice: tier key -> everything the app and the
# UI need. Provider is fixed to google_genai (Gemini) for now; adding a tier later = add a
# row here (no code change elsewhere). Prices are per 1M tokens, shown verbatim in the UI.
MODEL_TIERS: dict[str, dict] = {
    "swift": {
        "key": "swift",
        "name": "Swift",
        "provider": "google_genai",
        "model": "gemini-3.1-flash-lite",
        "tagline": "Quick, natural conversation. Light on your quota.",
        "price": "Input $0.25 / Output $1.50 per 1M tokens",
    },
    "sage": {
        "key": "sage",
        "name": "Sage",
        "provider": "google_genai",
        "model": "gemini-3.5-flash",
        "tagline": "Sharper, more thoughtful replies — but uses your quota noticeably faster.",
        "price": "Input $1.50 / Output $9.00 per 1M tokens",
    },
}

DEFAULT_MODEL_TIER = "swift"


def tier_config(tier: str) -> dict | None:
    """Look up a tier's config by key; None if unknown."""
    return MODEL_TIERS.get((tier or "").strip().lower())
