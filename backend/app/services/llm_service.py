"""Multi-provider model factory via LangChain's unified init_chat_model."""

import os

from langchain.chat_models import init_chat_model

from ..config import settings

# make sure keys from .env reach the provider SDKs even if only set via pydantic settings
_ENV_KEYS = {
    "OPENAI_API_KEY": settings.openai_api_key,
    "ANTHROPIC_API_KEY": settings.anthropic_api_key,
    "GOOGLE_API_KEY": settings.google_api_key,
}
for k, v in _ENV_KEYS.items():
    if v and not os.environ.get(k):
        os.environ[k] = v


def get_chat_model(provider: str | None = None, model: str | None = None, **kwargs):
    provider = provider or settings.default_provider
    model = model or settings.default_model
    return init_chat_model(model, model_provider=provider, **kwargs)


def get_judge_model(**kwargs):
    return init_chat_model(settings.judge_model, model_provider=settings.judge_provider, temperature=0, **kwargs)


def get_utility_model(**kwargs):
    return init_chat_model(settings.utility_model, model_provider=settings.utility_provider, **kwargs)
