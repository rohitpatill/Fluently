"""Multi-provider model factory via LangChain's unified init_chat_model.

Per-user bring-your-own-key: the caller passes the resolved `provider`, `model`, and the
user's decrypted `api_key` (see `model_service.resolve_for_user`). The key is handed straight
to `init_chat_model` — we do NOT mutate `os.environ`, so concurrent users with different keys
never clobber each other.
"""

from langchain.chat_models import init_chat_model


def _init(provider: str, model: str, api_key: str | None, **kwargs):
    if api_key:
        kwargs["api_key"] = api_key
    return init_chat_model(model, model_provider=provider, **kwargs)


def get_chat_model(provider: str, model: str, api_key: str | None = None, **kwargs):
    return _init(provider, model, api_key, **kwargs)


def get_judge_model(provider: str, model: str, api_key: str | None = None, **kwargs):
    kwargs.setdefault("temperature", 0)
    return _init(provider, model, api_key, **kwargs)


def get_utility_model(provider: str, model: str, api_key: str | None = None, **kwargs):
    return _init(provider, model, api_key, **kwargs)
