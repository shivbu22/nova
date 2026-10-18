from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from groq import Groq

try:
    # Prefer reusing the existing Nova key manager if available
    from Nova.KeyManager import GetKey as _legacy_get_key  # type: ignore[import]
except Exception:  # pragma: no cover - fallback if legacy code is removed
    _legacy_get_key = None  # type: ignore[assignment]


def _get_groq_api_key() -> str:
    if _legacy_get_key is not None:
        key = _legacy_get_key("Groq")
        if key:
            return key
    # As a fallback, rely on environment configuration if provided
    import os

    env_key = os.getenv("GROQ_API_KEY", "")
    if not env_key:
        raise RuntimeError(
            "Groq API key not found. Set it via Nova's key manager or GROQ_API_KEY."
        )
    return env_key


@dataclass
class ChatResult:
    content: str
    raw: Any


class GroqLLMClient:
    """Thin wrapper around Groq's chat.completions API.

    This client intentionally exposes only a minimal surface area needed by the
    nova2 core engine: non-streaming chat completion with optional tools.
    """

    def __init__(self, model: str) -> None:
        api_key = _get_groq_api_key()
        self._client = Groq(api_key=api_key)
        self._model = model

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ChatResult:
        """Perform a single chat completion call.

        :param messages: Conversation history in OpenAI/Groq format.
        :param tools: Optional tool definitions (not yet used by the minimal
                      nova2 core, but supported for future module integration).
        """

        kwargs: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        return ChatResult(content=content, raw=response)
