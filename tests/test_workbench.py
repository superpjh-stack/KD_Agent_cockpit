from pathlib import Path

import dotenv
from streamlit.testing.v1 import AppTest

import kyungdong_agent


def test_customer_flow_without_api(tmp_path, monkeypatch):
    repo = kyungdong_agent.KyungdongRepository(tmp_path / "demo.db")
    monkeypatch.setattr(kyungdong_agent, "create_repository", lambda path: repo)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py")).run(timeout=20)
    assert not app.exception
    target = next(s for s in app.selectbox if s.label == "업무 대상")
    target.select(repo.projects()[0]["project_id"]).run()
    assert not app.exception
    for _ in range(2):
        next(b for b in app.button if b.label == "새 대화").click().run()
        assert not app.exception
    app.selectbox(key="data_table").select("rules").run()
    assert not app.exception
    next(b for b in app.button if b.label == "확인할 일 요약").click().run()
    assert not app.exception
    assert len(app.session_state["messages"]) == 1
