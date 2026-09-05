from kyungdong_agent import KyungdongRepository, KyungdongToolRegistry


def test_dashboard_preserves_confirmed_reference_facts(tmp_path):
    repo = KyungdongRepository(tmp_path / "demo.db")
    data = repo.dashboard()
    assert data["confirmed_avg_lead_days"] == 90
    assert data["confirmed_annual_units"] == 50
    assert (data["laser_before_days"], data["laser_after_days"]) == (4, 1)


def test_material_quote_and_fat_demo_are_explicit(tmp_path):
    repo = KyungdongRepository(tmp_path / "demo.db")
    assert any(row["document_attached"] == 0 for row in repo.inspection_issues())
    assert all("미검증" in row["model_status"] for row in repo.quote_analysis())
    assert any(row["result"] == "불합격" for row in repo.fat_quality())


def test_registry_is_read_only_and_blocks_unknown_tools(tmp_path):
    registry = KyungdongToolRegistry(KyungdongRepository(tmp_path / "demo.db"))
    names = {item["name"] for item in registry.definitions}
    assert all(not name.startswith(("create_", "update_", "delete_")) for name in names)
    assert "허용되지 않은" in registry.execute("delete_project", "{}")
    output = registry.execute("get_material_status", '{"project_id":null,"issues_only":true}')
    assert '"status": "ok"' in output

