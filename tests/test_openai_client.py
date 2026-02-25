from __future__ import annotations

from types import SimpleNamespace

from orb.openai_client import FALLBACK_ASSISTANT_TEXT, OrbOpenAIClient


class _StubCompletions:
    def __init__(self, response: object) -> None:
        self._response = response

    def create(self, **_: object) -> object:
        return self._response


def _build_client_with_response(response: object) -> OrbOpenAIClient:
    client = OrbOpenAIClient.__new__(OrbOpenAIClient)
    client.client = SimpleNamespace(
        chat=SimpleNamespace(completions=_StubCompletions(response))
    )
    return client


def test_chat_parses_normal_text_response() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content="  Hello from Orb!  "),
            )
        ]
    )
    client = _build_client_with_response(response)

    result = client.chat(
        user_text="Hi",
        model="gpt-4o-mini",
        system_prompt="You are Orb.",
    )

    assert result == "Hello from Orb!"


def test_chat_uses_fallback_for_none_or_empty_content() -> None:
    none_content_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=None),
            )
        ]
    )
    empty_content_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content="   "),
            )
        ]
    )

    none_client = _build_client_with_response(none_content_response)
    empty_client = _build_client_with_response(empty_content_response)

    none_result = none_client.chat(
        user_text="Hi",
        model="gpt-4o-mini",
        system_prompt="You are Orb.",
    )
    empty_result = empty_client.chat(
        user_text="Hi",
        model="gpt-4o-mini",
        system_prompt="You are Orb.",
    )

    assert none_result == FALLBACK_ASSISTANT_TEXT
    assert empty_result == FALLBACK_ASSISTANT_TEXT
