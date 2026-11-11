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
    assert calls_agent(text, WAKE_POLICY) is expected
