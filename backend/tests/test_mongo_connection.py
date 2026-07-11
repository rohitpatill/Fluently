"""Live MongoDB connection smoke test.

Verifies the Atlas cluster is reachable, we can write/read/delete a doc, and that
ensure_indexes() succeeds. Marked `live` (needs the real MONGODB_URI + network), so
it's deselected by the default `-m "not live"` run. Run explicitly with:

    .venv\\Scripts\\python -m pytest tests/test_mongo_connection.py -m live -s
"""

import pytest

from app import mongo


@pytest.mark.live
def test_ping():
    res = mongo.ping()
    assert res.get("ok") == 1.0


@pytest.mark.live
def test_write_read_delete_roundtrip():
    col = mongo.get_db()["_conn_test"]
    col.delete_many({"_probe": True})
    ins = col.insert_one({"_probe": True, "hello": "fluently"})
    assert ins.inserted_id is not None

    doc = col.find_one({"_id": ins.inserted_id})
    assert doc is not None and doc["hello"] == "fluently"

    col.delete_one({"_id": ins.inserted_id})
    assert col.find_one({"_id": ins.inserted_id}) is None


@pytest.mark.live
def test_ensure_indexes():
    mongo.ensure_indexes()
    names = set(mongo.words_col().index_information().keys())
    assert "uq_user_text" in names
