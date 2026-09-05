import pytest

from kyungdong_agent import KyungdongRepository


def test_inventory_reflects_persistent_samples(tmp_path):
    path = tmp_path / "demo.db"
    repo = KyungdongRepository(path)
    inventory = {item["table"]: item for item in repo.table_inventory()}
    assert inventory["operations"]["count"] == 6
    assert inventory["rules"]["count"] == 7
    assert inventory["rules"]["exists"] is True
    assert len(repo.knowledge_documents()) == 10
    doc_ids = {doc["document_id"] for doc in repo.knowledge_documents()}
    assert all(rule["source_document"] in doc_ids for rule in repo.get_rules())
    repo.save_setting("vector_store_id", "test-store")
    repo.save_uploaded_document("test-file", "test.md", "test document")
    reopened = KyungdongRepository(path)
    assert reopened.setting("vector_store_id") == "test-store"
    assert len(reopened.knowledge_documents()) == 11
    assert len(reopened.get_rules()) == 7


def test_local_document_search(tmp_path):
    repo = KyungdongRepository(tmp_path / "demo.db")
    hits = repo.search_knowledge("자재 부족 대체 승인")
    assert hits[0]["document_id"] == "KGT-KB-005"
    assert "PO-26088" in hits[0]["text"]
    assert repo.search_knowledge("") == []
    assert repo.search_knowledge("zzzzzzzz") == []


def test_browser_limits_and_stable_paging(tmp_path):
    repo = KyungdongRepository(tmp_path / "demo.db")
    rows = repo.table_records("operations")
    assert repo.table_records("operations", limit=2, offset=2) == rows[2:4]
    with pytest.raises(ValueError):
        repo.table_records("sqlite_master")
    with pytest.raises(ValueError):
        repo.table_records('operations"; DROP TABLE projects; --')
    with pytest.raises(ValueError):
        repo.table_records("operations", limit=101)
    assert len(repo.projects()) == 3
