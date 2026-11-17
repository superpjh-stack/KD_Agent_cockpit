import pytest

from v2.wake import WAKE_POLICY, calls_agent


@pytest.mark.parametrize('text,expected', [
    ('경동아, 자재 LOT를 알려줘', True),
    ('경동아 납기 지연을 확인해줘', True),
    ('  “경동아!” FAT 결과를 알려줘', True),
    ('자재 LOT를 알려줘', False),
    ('경동아니야, 자재 LOT를 알려줘', False),
    ('오늘 경동아, 납기 지연을 알려줘', False),
])
def test_wake_grammar(text, expected):
    assert calls_agent(text, {**WAKE_POLICY, "require_wake_name": True}) is expected


def test_default_policy_accepts_unaddressed_question():
    assert calls_agent("자재 현황을 알려줘")

@pytest.mark.parametrize('text,expected', [
    ('경동아, 자재 현황 알려줘', True),
    ('경동아! 납기는?', True),
    ('자재 현황 알려줘', False),
    ('그럼 납기는?', False),
    ('오늘 경동아라고 불렀어', False),
    ('경동아니야', False),
])
def test_voice_requires_wake_each_turn(text, expected):
    from v2.wake import VOICE_WAKE_POLICY
    assert calls_agent(text, VOICE_WAKE_POLICY) is expected
    assert calls_agent(text) is True
