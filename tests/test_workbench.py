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


def test_voice_review_send_and_speech_failure_keeps_answer(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from kyungdong_agent.voice import VoiceService

    repo = kyungdong_agent.KyungdongRepository(tmp_path / "demo.db")
    monkeypatch.setattr(kyungdong_agent, "create_repository", lambda path: repo)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    ask = Mock(return_value=SimpleNamespace(text="자재 확인이 필요합니다.", sources=[], evidence=[],
        data_tools=[], data_evidence=[], searched_documents=False, knowledge_base_connected=True, response_id="r1"))
    monkeypatch.setattr(kyungdong_agent.ManufacturingAgent, "ask", ask)
    monkeypatch.setattr(VoiceService, "speak", Mock(side_effect=RuntimeError("unavailable")))
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py")).run(timeout=20)
    app.session_state["voice_draft"] = "LOT 123 확인해줘"
    app.run()
    assert not ask.called
    app.button(key="send_voice").click().run()
    assert not app.exception
    assert ask.call_args.args[0] == "LOT 123 확인해줘"
    assert app.session_state["voice_draft"] == ""
    message = app.session_state["messages"][-1]
    assert message["content"] == "자재 확인이 필요합니다."
    assert "voice_error" in message
