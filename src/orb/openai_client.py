from __future__ import annotations

from pathlib import Path

from openai import OpenAI


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

    def chat(self, user_text: str, model: str, system_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            temperature=0.5,
            max_tokens=140,
        )
        return response.choices[0].message.content.strip()

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
