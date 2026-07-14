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
    # Browser origins allowed by CORS — comma-separated, from .env. Every deployed
    # frontend origin must be listed here or its requests are blocked by the browser.
    # e.g. "http://localhost:5173,https://fluently-zeta.vercel.app"
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    # Secret used to sign the JWT session cookie (HS256). Generate a strong random value.
    session_secret: str = ""
    # Secret used to sign the short-lived state/nonce cookie during the OAuth handshake.
    state_cookie_secret: str = ""
    session_cookie_name: str = "fluently_session"
    session_max_age_days: int = 7

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse cors_allowed_origins into a clean list (trims spaces + trailing slashes)."""
        return [o.strip().rstrip("/") for o in self.cors_allowed_origins.split(",") if o.strip()]

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

    # --- Voice mode (Gemini Live real-time audio) ---
    # The live audio-to-audio model used for voice conversations. Kept configurable so we can
    # swap it (e.g. to a native-audio model that supports non-blocking tools) without a code
    # change. Voice mode uses the SAME per-user BYO key as text mode (resolved per request).
    voice_model: str = "gemini-3.1-flash-live-preview"

    # User's timezone — all temporal reasoning in the prompt is computed in this zone.
    user_timezone: str = "Asia/Kolkata"

    # Scoring matrix (see CLAUDE.md)
    score_perfect_unprompted: float = 5.0
    score_perfect_prompted: float = 3.0
    score_awkward: float = 1.0
    score_wrong: float = -2.0
    score_passive: float = 0.5
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


# --- Voice catalogue (Gemini Live prebuilt voices) ------------------------------------
# SINGLE SOURCE OF TRUTH for the voices a persona can speak with. Each entry:
#   id     -> the exact `voice_name` Gemini Live expects (case-sensitive)
#   label  -> what we show in the picker (same as the voice id, kept separate so we could
#             rename the display without breaking the API value)
#   tone   -> Google's own short "tone, pitch" descriptor (as shown in AI Studio's picker)
#   gender -> "male" | "female" — community-inferred (Google publishes tone, NOT gender);
#             used ONLY to pick a sensible DEFAULT voice from a persona's Gender field.
# Users can audition every voice live in Google AI Studio (link surfaced in the UI):
#   https://aistudio.google.com/live?model=gemini-3.1-flash-live-preview
# Adding/removing a voice = edit this list only (backend list endpoint + UI both read it).
VOICES: list[dict] = [
    {"id": "Puck", "label": "Puck", "tone": "Upbeat, Middle pitch", "gender": "male"},
    {"id": "Charon", "label": "Charon", "tone": "Informative, Lower pitch", "gender": "male"},
    {"id": "Fenrir", "label": "Fenrir", "tone": "Excitable, Younger", "gender": "male"},
    {"id": "Orus", "label": "Orus", "tone": "Firm, Middle pitch", "gender": "male"},
    {"id": "Iapetus", "label": "Iapetus", "tone": "Clear, Middle pitch", "gender": "male"},
    {"id": "Umbriel", "label": "Umbriel", "tone": "Easy-going, Middle pitch", "gender": "male"},
    {"id": "Algieba", "label": "Algieba", "tone": "Smooth, Lower pitch", "gender": "male"},
    {"id": "Algenib", "label": "Algenib", "tone": "Gravelly, Lower pitch", "gender": "male"},
    {"id": "Rasalgethi", "label": "Rasalgethi", "tone": "Informative, Middle pitch", "gender": "male"},
    {"id": "Alnilam", "label": "Alnilam", "tone": "Firm, Lower middle pitch", "gender": "male"},
    {"id": "Schedar", "label": "Schedar", "tone": "Even, Lower middle pitch", "gender": "male"},
    {"id": "Achird", "label": "Achird", "tone": "Friendly, Middle pitch", "gender": "male"},
    {"id": "Zubenelgenubi", "label": "Zubenelgenubi", "tone": "Casual, Middle pitch", "gender": "male"},
    {"id": "Sadaltager", "label": "Sadaltager", "tone": "Knowledgeable, Middle pitch", "gender": "male"},
    {"id": "Enceladus", "label": "Enceladus", "tone": "Breathy, Lower pitch", "gender": "male"},
    {"id": "Sadachbia", "label": "Sadachbia", "tone": "Lively, Lower pitch", "gender": "male"},
    {"id": "Zephyr", "label": "Zephyr", "tone": "Bright, Higher pitch", "gender": "female"},
    {"id": "Kore", "label": "Kore", "tone": "Firm, Middle pitch", "gender": "female"},
    {"id": "Leda", "label": "Leda", "tone": "Youthful, Higher pitch", "gender": "female"},
    {"id": "Aoede", "label": "Aoede", "tone": "Breezy, Middle pitch", "gender": "female"},
    {"id": "Callirrhoe", "label": "Callirrhoe", "tone": "Easy-going, Middle pitch", "gender": "female"},
    {"id": "Autonoe", "label": "Autonoe", "tone": "Bright, Middle pitch", "gender": "female"},
    {"id": "Despina", "label": "Despina", "tone": "Smooth, Middle pitch", "gender": "female"},
    {"id": "Erinome", "label": "Erinome", "tone": "Clear, Middle pitch", "gender": "female"},
    {"id": "Laomedeia", "label": "Laomedeia", "tone": "Upbeat, Higher pitch", "gender": "female"},
    {"id": "Achernar", "label": "Achernar", "tone": "Soft, Higher pitch", "gender": "female"},
    {"id": "Gacrux", "label": "Gacrux", "tone": "Mature, Middle pitch", "gender": "female"},
    {"id": "Pulcherrima", "label": "Pulcherrima", "tone": "Forward, Middle pitch", "gender": "female"},
    {"id": "Vindemiatrix", "label": "Vindemiatrix", "tone": "Gentle, Middle pitch", "gender": "female"},
    {"id": "Sulafat", "label": "Sulafat", "tone": "Warm, Middle pitch", "gender": "female"},
]

# Fast lookup: voice id -> entry.
VOICES_BY_ID: dict[str, dict] = {v["id"]: v for v in VOICES}

# The default voice when a persona has no voice set, keyed by its Gender field.
# Falls back to DEFAULT_VOICE for unknown/blank gender.
DEFAULT_VOICE = "Puck"  # friendly, neutral-masculine — a safe default companion voice
_DEFAULT_VOICE_BY_GENDER = {
    "male": "Puck",
    "female": "Aoede",
}


def is_valid_voice(voice: str) -> bool:
    """True if `voice` is a known Gemini Live voice id."""
    return (voice or "").strip() in VOICES_BY_ID


def default_voice_for_gender(gender: str) -> str:
    """Pick a sensible default voice from a persona's Gender field (no LLM). Used when a
    persona is created (onboarding / Discover) without an explicit voice choice."""
    return _DEFAULT_VOICE_BY_GENDER.get((gender or "").strip().lower(), DEFAULT_VOICE)


def resolve_voice(voice: str, gender: str = "") -> str:
    """Return a valid voice id: the persona's chosen voice if valid, else a gender default."""
    v = (voice or "").strip()
    if v in VOICES_BY_ID:
        return v
    return default_voice_for_gender(gender)
