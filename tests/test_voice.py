from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from kyungdong_agent.voice import VoiceService, MAX_RECORDING_BYTES


def test_transcription_uses_korean_and_preserves_question():
    client = MagicMock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(text="  자재가 부족해?  ")
    assert VoiceService(client).transcribe(b"recording") == "자재가 부족해?"
    args = client.audio.transcriptions.create.call_args.kwargs
    assert args["language"] == "ko"
    assert args["file"][1] == b"recording"


def test_invalid_recordings_do_not_call_api():
    client = MagicMock()
    for data in [b"", b"x" * (MAX_RECORDING_BYTES + 1)]:
        with pytest.raises(ValueError):
            VoiceService(client).transcribe(data)
    client.audio.transcriptions.create.assert_not_called()
    client.audio.transcriptions.create.return_value = SimpleNamespace(text=" ")
    with pytest.raises(ValueError):
        VoiceService(client).transcribe(b"silent")


def test_speech_preserves_answer_and_evidence():
    client = MagicMock()
    client.audio.speech.with_streaming_response.create.return_value.__enter__.return_value.read.return_value = b"mp3-data"
    text = "자재가 부족합니다.\n근거: DB 자재 ML-260904"
    assert VoiceService(client).speak(text) == b"mp3-data"
    assert client.audio.speech.with_streaming_response.create.call_args.kwargs["input"] == text


def test_speech_failure_and_size_guards():
    client = MagicMock()
    for text in ["", "x" * 4001]:
        with pytest.raises(ValueError):
            VoiceService(client).speak(text)
    client.audio.speech.with_streaming_response.create.assert_not_called()
    client.audio.speech.with_streaming_response.create.return_value.__enter__.return_value.read.return_value = b""
    with pytest.raises(ValueError):
        VoiceService(client).speak("짧은 답변")
