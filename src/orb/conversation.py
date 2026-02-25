from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


@dataclass
class ConversationBuffer:
    max_turns: int
    reset_timeout_seconds: float | None = None
    turns: list[ChatMessage] = field(default_factory=list)
    _last_activity_ts: float | None = None

    def maybe_reset_for_inactivity(self, now: float | None = None) -> bool:
        if self.reset_timeout_seconds is None:
            return False

        current = time.monotonic() if now is None else now
        if self._last_activity_ts is None:
            self._last_activity_ts = current
            return False

        if current - self._last_activity_ts >= self.reset_timeout_seconds:
            self.reset(now=current)
            return True

        return False

    def add_turn(self, user_text: str, assistant_text: str, now: float | None = None) -> None:
        self.turns.append({"role": "user", "content": user_text})
        self.turns.append({"role": "assistant", "content": assistant_text})
        self._trim_to_max_turns()
        self._last_activity_ts = time.monotonic() if now is None else now

    def reset(self, now: float | None = None) -> None:
        self.turns.clear()
        self._last_activity_ts = time.monotonic() if now is None else now

    def build_messages(self, system_prompt: str, latest_user_text: str) -> list[ChatMessage]:
        return [{"role": "system", "content": system_prompt}, *self.turns, {"role": "user", "content": latest_user_text}]

    def _trim_to_max_turns(self) -> None:
        max_messages = self.max_turns * 2
        if len(self.turns) > max_messages:
            self.turns = self.turns[-max_messages:]
