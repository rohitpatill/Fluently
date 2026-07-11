"""Test fixtures. Every run uses a SEPARATE MongoDB database (the configured db name
with a '_test' suffix) whose collections are wiped before each test — the real
`fluently` database is never touched.

LLM strategy is flag-based:
  - default: all LLM calls are mocked (fast, free, deterministic)
  - live tests: `pytest -m live` (or run_tests.py --live) hit the real provider in .env
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Point the app at a throwaway *_test database BEFORE any app module reads settings.
_BASE_DB = os.environ.get("MONGODB_DB", "fluently")
os.environ["MONGODB_DB"] = f"{_BASE_DB}_test"

# ENCRYPTION_KEY (Fernet) comes from .env via load_dotenv() above — NEVER hardcoded here
# (test files are committed to Git). If it's missing, crypto tests will fail loudly, which is
# the correct signal to add it to .env.

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app import mongo
from app.deps import get_current_user, get_current_user_obj
from app.main import app
from app.models import User
from app.services import chat_service, judge_service, memory_service, model_service, topic_service

_COLLECTIONS = ["conversations", "messages", "words", "word_events", "memory_files", "users"]

# A stable, fixed user that the default `client` fixture is authenticated as. Existing
# router tests then run scoped to this user without needing a real Google login.
TEST_USER_ID = "0123456789abcdef01234567"


@pytest.fixture(autouse=True)
def fresh_db():
    db = mongo.get_db()
    for c in _COLLECTIONS:
        db[c].delete_many({})
    mongo.ensure_indexes()
    yield
    for c in _COLLECTIONS:
        db[c].delete_many({})


def seed_user(user_id: str, *, sub: str | None = None, email: str | None = None) -> User:
    """Insert a user doc with a chosen _id and bootstrap their 3 memory files."""
    from datetime import datetime, timezone

    from bson import ObjectId

    sub = sub or f"sub-{user_id}"
    email = email or f"{user_id}@example.com"
    # Seed an encrypted key + tier so LLM-gated routes (chat/conversation/opener) pass. The
    # key is a harmless placeholder encrypted with the test ENCRYPTION_KEY (from .env) — the
    # LLM factories are mocked, so its plaintext value is never actually used to call an API.
    from app.services import crypto_service

    mongo.users_col().insert_one(
        {"_id": ObjectId(user_id), "google_sub": sub, "email": email,
         "name": "Test User", "picture": "", "adopted_default": False,
         "encrypted_api_key": crypto_service.encrypt("test-placeholder-key"),
         "model_tier": "swift",
         "created_at": datetime.now(timezone.utc)}
    )
    memory_service.ensure_files(user_id)
    return User(id=user_id, google_sub=sub, email=email, name="Test User",
                encrypted_api_key="x", model_tier="swift")


@pytest.fixture
def client():
    """Authenticated client, scoped to TEST_USER_ID (auth dependency overridden)."""
    seed_user(TEST_USER_ID)
    test_user = User(id=TEST_USER_ID, google_sub=f"sub-{TEST_USER_ID}",
                     email=f"{TEST_USER_ID}@example.com", name="Test User",
                     encrypted_api_key="x", model_tier="swift")
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_user_obj] = lambda: test_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    """Unauthenticated client (no dependency override) — for testing auth gating itself."""
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c


# ---------- LLM mocking ----------
class FakeChatModel:
    """Stands in for a LangChain chat model. Feed it a list of AIMessage responses;
    each invoke() pops the next one (last one repeats)."""

    def __init__(self, responses=None):
        self.responses = list(responses or [AIMessage(content="Hey! Nice to hear from you.")])
        self.invocations = []

    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


class FakeStructuredModel:
    def __init__(self, result):
        self.result = result

    def invoke(self, messages):
        return self.result


class FakeStructuredFactory:
    """Mimics get_judge_model()/get_utility_model(): .with_structured_output(Schema) -> invoker."""

    def __init__(self, results_by_schema=None):
        self.results_by_schema = results_by_schema or {}

    def with_structured_output(self, schema):
        if schema in self.results_by_schema:
            return FakeStructuredModel(self.results_by_schema[schema])
        return FakeStructuredModel(schema())


@pytest.fixture(autouse=True)
def mock_llms(request, monkeypatch):
    """Mock every LLM factory unless the test is marked @pytest.mark.live."""
    if "live" in request.keywords:
        yield None
        return

    chat_model = FakeChatModel()
    structured = FakeStructuredFactory(
        {
            judge_service.JudgeResult: judge_service.JudgeResult(judgements=[]),
            topic_service.TopicList: topic_service.TopicList(topics=[]),
            topic_service.OnboardingFacts: topic_service.OnboardingFacts(
                identity=["Founder of a startup.", "26 years old."],
                memory=["Wants English to sound natural in meetings."],
                persona=[],
            ),
        }
    )
    monkeypatch.setattr(chat_service, "get_chat_model", lambda *a, **k: chat_model)
    monkeypatch.setattr(chat_service, "get_utility_model", lambda *a, **k: FakeChatModel([AIMessage(content="Test Title")]))
    monkeypatch.setattr(judge_service, "get_judge_model", lambda *a, **k: structured)
    monkeypatch.setattr(topic_service, "get_utility_model", lambda *a, **k: structured)

    # Each service resolves the user's per-user model before calling the (mocked) factory.
    # Stub the resolver so tests don't need a decryptable key / real provider.
    fake_resolved = model_service.ResolvedModel(
        provider="google_genai", model="gemini-3.1-flash-lite", api_key="test", tier="swift"
    )
    for svc in (chat_service, judge_service, topic_service):
        monkeypatch.setattr(svc, "resolve_for_user", lambda *a, **k: fake_resolved)
    yield chat_model
