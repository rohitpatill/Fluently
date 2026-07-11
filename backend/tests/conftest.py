"""Test fixtures. Every run uses a fresh temp SQLite DB + temp memory files —
the real backend/data/ is never touched.

LLM strategy is flag-based:
  - default: all LLM calls are mocked (fast, free, deterministic)
  - live tests: `pytest -m live` (or run_tests.py --live) hit the real provider
    configured in .env (DEFAULT_PROVIDER / DEFAULT_MODEL etc.)
"""

import os
import tempfile

# Point the app at a throwaway DB/data dir BEFORE any app module is imported.
_TMP = tempfile.mkdtemp(prefix="eng_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["DATA_DIR"] = _TMP

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.database import Base, SessionLocal, engine
from app.main import app
from app.services import chat_service, judge_service, topic_service


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # fresh memory files too
    for f in ("identity.md", "memory.md", "persona.md"):
        p = os.path.join(_TMP, f)
        if os.path.exists(p):
            os.remove(p)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


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
        # default: empty instance of the schema
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
        }
    )
    monkeypatch.setattr(chat_service, "get_chat_model", lambda *a, **k: chat_model)
    monkeypatch.setattr(chat_service, "get_utility_model", lambda *a, **k: FakeChatModel([AIMessage(content="Test Title")]))
    monkeypatch.setattr(judge_service, "get_judge_model", lambda *a, **k: structured)
    monkeypatch.setattr(topic_service, "get_utility_model", lambda *a, **k: structured)
    yield chat_model
