from kyungdong_agent import KyungdongRepository, project_snapshot, risk_label, user_question_history


def test_history_keeps_recent_user_questions_only():
    messages = [
        {"role": "assistant", "content": "안내"},
        {"role": "user", "content": "첫 질문", "created_at": "09:00"},
        {"role": "assistant", "content": "답변"},
        {"role": "user", "content": "최근 질문", "created_at": "09:10"},
    ]
    history = user_question_history(messages)
    assert [item["content"] for item in history] == ["최근 질문", "첫 질문"]


def test_project_snapshot_drives_context_and_risk(tmp_path):
    repository = KyungdongRepository(tmp_path / "cockpit.db")
    snapshot = project_snapshot(repository, "KGT-26002")
    assert snapshot["project"]["equipment_type"] == "진공건조기"
    assert snapshot["material_issue_count"] >= 1
    label, icon = risk_label(snapshot)
    assert label in {"주의", "높음"}
    assert icon in {"🟠", "🔴"}
