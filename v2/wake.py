"""Shared wake-word policy for text and realtime voice conversations."""
import re

WAKE_POLICY = {
    "agent_name": "경동아",
    "wake_aliases": ["경동아"],
    "require_wake_name": True,
}


def calls_agent(text: str, policy: dict = WAKE_POLICY) -> bool:
    """Return True only when the utterance starts with the configured wake word."""
    if not policy.get("require_wake_name", True):
        return True
    aliases = {" ".join(alias.split()) for alias in [policy.get("agent_name", ""), *policy.get("wake_aliases", [])] if alias.strip()}
    names = "|".join(re.escape(alias) for alias in sorted(aliases, key=len, reverse=True))
    if not names:
        return False
    normalized = " ".join(text.split())
    return bool(re.match(rf'''^[\s"'“‘]*(?:{names})(?=$|[\s,，.!?。！？:：~～])''', normalized))


def addressed_question(question: str) -> str:
    return f"{WAKE_POLICY['agent_name']}, {question}"
