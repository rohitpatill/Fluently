"""Per-user model resolution: which Gemini model + which (decrypted) API key to use.

Users bring their own key and pick a tier (Swift/Sage — see `config.MODEL_TIERS`). The chosen
tier governs EVERY LLM call for that user (chat, judge, utility). This module is the single
place that turns a `user_id` into a concrete `{provider, model, api_key}` bundle, and that
verifies a key actually works before we store it.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain.chat_models import init_chat_model

from .. import repo
from ..config import DEFAULT_MODEL_TIER, MODEL_TIERS, settings, tier_config
from . import crypto_service


class NoModelConfigured(Exception):
    """The user hasn't set up a working key + tier yet — the app must gate them to onboarding."""


@dataclass
class ResolvedModel:
    provider: str
    model: str
    api_key: str
    tier: str


def tiers_public() -> list[dict]:
    """The tier catalogue for the UI (name/tagline/price/model id). No secrets."""
    return [
        {"key": t["key"], "name": t["name"], "model": t["model"], "tagline": t["tagline"], "price": t["price"]}
        for t in MODEL_TIERS.values()
    ]


def resolve_for_user(user_id: str) -> ResolvedModel:
    """Load the user, decrypt their key, map their tier → model. Raises NoModelConfigured
    if they haven't finished the 'How smart should I be?' setup."""
    user = repo.get_user(user_id)
    if user is None or not user.encrypted_api_key or not user.model_tier:
        raise NoModelConfigured("No model configured for this user.")
    cfg = tier_config(user.model_tier) or tier_config(DEFAULT_MODEL_TIER)
    return ResolvedModel(
        provider=cfg["provider"],
        model=cfg["model"],
        api_key=crypto_service.decrypt(user.encrypted_api_key),
        tier=user.model_tier,
    )


def verify_key(api_key: str, tier: str) -> bool:
    """Make one tiny throwaway call to confirm the key works for the tier's model.
    Returns True/False — never raises (a bad key is an expected outcome, not an error)."""
    cfg = tier_config(tier) or tier_config(DEFAULT_MODEL_TIER)
    if not (api_key or "").strip():
        return False
    try:
        llm = init_chat_model(
            cfg["model"],
            model_provider=cfg["provider"],
            api_key=api_key.strip(),
            max_output_tokens=1,
            temperature=0,
        )
        llm.invoke("hi")
        return True
    except Exception:
        return False
