import json

import pytest

from kyungdong_agent import KyungdongRepository, KyungdongToolRegistry


@pytest.fixture
def repo(tmp_path):
    return KyungdongRepository(tmp_path / "demo.db")


def test_project_scope_and_inspection_join(repo):
    result = repo.evaluate_rules(as_of="2026-01-01")
    assert result["findings"]
    for project in repo.projects():
        scoped = repo.evaluate_rules(project["project_id"], "2026-01-01")
        assert scoped["findings"] == [r for r in result["findings"] if r["project_id"] == project["project_id"]]
    assert any(f["source_table"] == "incoming_inspections" for f in result["findings"])
    assert all(f["document_available"] for f in result["findings"])


def test_date_boundary_completed_and_missing_data(repo):
    with repo._connect() as connection:
        connection.execute("UPDATE operations SET status='진행', due_date='2026-04-01', actual_hours=NULL WHERE operation_id='OP-001'")
    def matches(day):
        return [f for f in repo.evaluate_rules(as_of=day)["findings"] if f["rule_id"] == "DEMO-R004" and f["record_id"] == "OP-001"]
    assert not matches("2026-04-01")
    assert matches("2026-04-02")
    assert any(r.get("record_id") == "OP-001" for r in repo.evaluate_rules()["unevaluated"])
    with repo._connect() as connection:
        connection.execute("UPDATE operations SET status='완료' WHERE operation_id='OP-001'")
    assert not matches("2026-04-02")


def test_modified_rule_not_silently_evaluated(repo):
    with repo._connect() as connection:
        connection.execute("UPDATE rules SET condition='arbitrary expression' WHERE rule_id='DEMO-R001'")
    result = repo.evaluate_rules()
    assert any(r["rule_id"] == "DEMO-R001" for r in result["unevaluated"])
    assert not any(r["rule_id"] == "DEMO-R001" for r in result["findings"])


def test_rule_engine_does_not_truncate_at_browser_page_limit(repo):
    with repo._connect() as connection:
        for index in range(110):
            connection.execute("INSERT INTO operations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f"EXTRA-{index:03}", "P-TEST", "용접", 1, 2, "내부", "완료", "2026-04-01"))
    result = repo.evaluate_rules()
    assert len([f for f in result["findings"] if str(f["record_id"]).startswith("EXTRA-")]) == 110


def test_tool_validation_and_no_writes(repo):
    registry = KyungdongToolRegistry(repo)
    before = repo.table_records("operations")
    result = json.loads(registry.execute("evaluate_rules", {"project_id": None, "as_of": "2026-04-01"}))
    assert result["status"] == "ok" and result["demo_data"]
    assert repo.table_records("operations") == before
    assert "error" in json.loads(registry.execute("evaluate_rules", {"as_of": "bad"}))
    assert "error" in json.loads(registry.execute("evaluate_rules", {"project_id": "unknown"}))
    with pytest.raises(ValueError):
        repo.rule_records("rules; DROP TABLE projects")
