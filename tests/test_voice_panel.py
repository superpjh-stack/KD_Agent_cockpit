from unittest.mock import Mock

from kyungdong_agent.voice_panel import transcribe_once


def test_recording_is_not_retranscribed_after_send_or_reset():
    service = Mock()
    service.transcribe.return_value = "LOT 123 확인해줘"
    state = {"voice_digest": None, "voice_draft": ""}
    transcribe_once(service, b"audio", state)
    assert state["voice_draft"] == "LOT 123 확인해줘"
    state["voice_draft"] = ""
    transcribe_once(service, b"audio", state)
    service.transcribe.assert_called_once()
    assert state["voice_draft"] == ""
    transcribe_once(service, b"new audio", state)
    assert service.transcribe.call_count == 2


def test_failure_preserved_until_explicit_retry():
    service = Mock()
    service.transcribe.side_effect = [ValueError("말소리 없음"), "다시 인식한 질문"]
    state = {}
    transcribe_once(service, b"audio", state)
    assert state["voice_error"] == "말소리 없음"
    transcribe_once(service, b"audio", state)
    assert service.transcribe.call_count == 1
    transcribe_once(service, b"audio", state, retry=True)
    assert state["voice_draft"] == "다시 인식한 질문"
    assert state["voice_error"] == ""


def test_no_service_or_empty_recording_does_not_discard_draft():
    state = {"voice_draft": "사용자가 수정한 질문"}
    transcribe_once(None, b"audio", state)
    service = Mock()
    transcribe_once(service, None, state)
    service.transcribe.assert_not_called()
    assert state["voice_draft"] == "사용자가 수정한 질문"
