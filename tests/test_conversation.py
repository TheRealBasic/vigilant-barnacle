from __future__ import annotations

from orb.conversation import ConversationBuffer


def test_conversation_history_accumulates() -> None:
    buffer = ConversationBuffer(max_turns=4)

    buffer.add_turn("Hi", "Hello")
    buffer.add_turn("How are you?", "Doing well")

    assert buffer.turns == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "Doing well"},
    ]


def test_conversation_history_trims_when_max_turns_exceeded() -> None:
    buffer = ConversationBuffer(max_turns=2)

    buffer.add_turn("u1", "a1")
    buffer.add_turn("u2", "a2")
    buffer.add_turn("u3", "a3")

    assert buffer.turns == [
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "u3"},
        {"role": "assistant", "content": "a3"},
    ]


def test_conversation_resets_after_inactivity() -> None:
    buffer = ConversationBuffer(max_turns=4, reset_timeout_seconds=10)

    buffer.add_turn("hello", "hi", now=100)

    reset = buffer.maybe_reset_for_inactivity(now=111)

    assert reset is True
    assert buffer.turns == []
