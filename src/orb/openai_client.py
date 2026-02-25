from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openai import OpenAI


logger = logging.getLogger(__name__)
FALLBACK_ASSISTANT_TEXT = "Sorry, I didn't catch that. Please try asking again."


class OrbOpenAIClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.client = OpenAI(api_key=api_key)

    def transcribe(self, audio_path: str, model: str) -> str:
        with Path(audio_path).open("rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model=model,
                file=audio_file,
            )
        return transcript.text.strip()

    def chat(self, messages: list[dict[str, str]], model: str) -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.5,
            max_tokens=140,
        )

        finish_reason = None
        if getattr(response, "choices", None):
            finish_reason = getattr(response.choices[0], "finish_reason", None)

        if not getattr(response, "choices", None):
            logger.warning(
                "OpenAI chat returned no choices; using fallback response (model=%s, finish_reason=%s)",
                model,
                finish_reason,
            )
            return FALLBACK_ASSISTANT_TEXT

        message = response.choices[0].message
        content = getattr(message, "content", None)

        if isinstance(content, str):
            cleaned = content.strip()
            if cleaned:
                return cleaned
        elif isinstance(content, list):
            extracted_parts: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        extracted_parts.append(text.strip())
                    continue

                text_value = _extract_text_attr(part)
                if text_value:
                    extracted_parts.append(text_value)

            if extracted_parts:
                return "\n".join(extracted_parts)

        logger.warning(
            "OpenAI chat returned unusable assistant content; using fallback response (model=%s, finish_reason=%s, content_type=%s)",
            model,
            finish_reason,
            type(content).__name__,
        )
        return FALLBACK_ASSISTANT_TEXT

    def tts(self, text: str, model: str, output_path: str, voice: str = "alloy") -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with self.client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice,
            input=text,
            format="mp3",
        ) as response:
            response.stream_to_file(output_path)
        return output_path


def _extract_text_attr(value: Any) -> str | None:
    text = getattr(value, "text", None)
    if isinstance(text, str):
        cleaned = text.strip()
        return cleaned or None
    return None
