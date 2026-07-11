"""Bring-your-own-key model config: the Swift/Sage tier catalogue + the user's key/tier.

Used by BOTH the onboarding "How smart should I be?" step and the Settings "Brain" card.
The plaintext key never leaves this module (verified → encrypted → stored); no endpoint ever
returns it.
"""

from fastapi import APIRouter, Depends, HTTPException

from .. import repo
from ..config import tier_config
from ..deps import get_current_user
from ..schemas import ModelStatusOut, ModelTierOut, SetKeyRequest, SetTierRequest
from ..services import crypto_service, model_service

router = APIRouter(prefix="/api/model", tags=["model"])


@router.get("/tiers", response_model=list[ModelTierOut])
def list_tiers():
    """The two 'brains' a user can pick (name/tagline/price/model id). No auth-specific data."""
    return model_service.tiers_public()


@router.get("/status", response_model=ModelStatusOut)
def status(user_id: str = Depends(get_current_user)):
    """Whether the current user has a working key configured, and which tier. Never the key."""
    user = repo.get_user(user_id)
    has_key = bool(user and user.encrypted_api_key and user.model_tier)
    return ModelStatusOut(has_key=has_key, tier=(user.model_tier if user else ""))


@router.post("/key", response_model=ModelStatusOut)
def set_key(payload: SetKeyRequest, user_id: str = Depends(get_current_user)):
    """Verify the key against the chosen tier's model, then store it ENCRYPTED. 400 if the key
    doesn't work. Same endpoint powers onboarding and the Settings 'replace key' flow."""
    tier = (payload.tier or "").strip().lower()
    if tier_config(tier) is None:
        raise HTTPException(400, "Unknown model tier.")
    api_key = (payload.api_key or "").strip()
    if not api_key:
        raise HTTPException(400, "API key is required.")
    if not model_service.verify_key(api_key, tier):
        raise HTTPException(400, "That key didn't work. Double-check it and try again.")
    repo.set_user_key(user_id, crypto_service.encrypt(api_key), tier)
    return ModelStatusOut(has_key=True, tier=tier)


@router.put("/tier", response_model=ModelStatusOut)
def switch_tier(payload: SetTierRequest, user_id: str = Depends(get_current_user)):
    """Switch Swift↔Sage using the already-stored key. 400 if unknown tier or no key yet."""
    tier = (payload.tier or "").strip().lower()
    if tier_config(tier) is None:
        raise HTTPException(400, "Unknown model tier.")
    user = repo.get_user(user_id)
    if user is None or not user.encrypted_api_key:
        raise HTTPException(400, "Add an API key before choosing a tier.")
    repo.set_user_tier(user_id, tier)
    return ModelStatusOut(has_key=True, tier=tier)
