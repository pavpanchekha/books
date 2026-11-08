from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelProvider(Protocol):
    def structured(
        self,
        *,
        model: str,
        schema: type[T],
        system: str,
        user: str,
        images: list[Path] | None = None,
    ) -> T: ...

    def image(
        self,
        *,
        model: str,
        prompt: str,
        size: str,
        quality: str,
        output_format: str,
    ) -> bytes: ...


class OpenAIProvider:
    def __init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as error:  # pragma: no cover - friendly CLI failure
            raise RuntimeError("Install dependencies with `uv sync`.") from error
        self.client = OpenAI()

    def structured(
        self,
        *,
        model: str,
        schema: type[T],
        system: str,
        user: str,
        images: list[Path] | None = None,
    ) -> T:
        if images:
            content: list[dict[str, object]] = [{"type": "text", "text": user}]
            for path in images:
                mime = mimetypes.guess_type(path.name)[0] or "image/png"
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{encoded}",
                            "detail": "high",
                        },
                    }
                )
            user_message: object = content
        else:
            user_message = user

        completion = self.client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            response_format=schema,
        )
        message = completion.choices[0].message
        if message.refusal:
            raise RuntimeError(f"Model refused the request: {message.refusal}")
        if message.parsed is None:
            raise RuntimeError("Model returned no structured result")
        return message.parsed

    def image(
        self,
        *,
        model: str,
        prompt: str,
        size: str,
        quality: str,
        output_format: str,
    ) -> bytes:
        result = self.client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            output_format=output_format,
            n=1,
        )
        encoded = result.data[0].b64_json
        if not encoded:
            raise RuntimeError("Image API returned no image data")
        return base64.b64decode(encoded)


def make_provider(name: str) -> ModelProvider:
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unknown provider {name!r}; implemented providers: openai")

