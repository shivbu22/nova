from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from .config import NovaConfig
from .llm_client import GroqLLMClient


@dataclass
class Conversation:
    messages: List[Dict[str, Any]] = field(default_factory=list)

    def add_system(self, content: str) -> None:
        self.messages.append({"role": "system", "content": content})

    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})


def build_system_prompt(config: NovaConfig) -> str:
    """Construct the main system prompt, mirroring the legacy behaviour."""

    hidden = (
        "You keep your answers as short as possible. You always use the metric system. "
        "You use the date format dd.mm.yyyy. You only mention the date and time if "
        "specifically asked to do so. You speak in the following language: "
        f"{config.language}. You never make up information. You never promise an "
        "alternative solution if a module or tool fails to execute. Your response "
        "will be read out by a text-to-speech system, so avoid excessive special "
        "characters."
    )
    return f"{config.behaviour} {hidden}"


def _append_runtime_context(messages: List[Dict[str, Any]], config: NovaConfig) -> List[Dict[str, Any]]:
    now = datetime.now()
    messages_with_context = list(messages)
    messages_with_context.append(
        {
            "role": "system",
            "content": "The date is " + now.strftime("%d/%m/%Y") + " The time is " + now.strftime("%H:%M"),
        }
    )
    if config.name:
        messages_with_context.append(
            {"role": "system", "content": f"The name of the user is {config.name}."}
        )
    return messages_with_context


def run_repl(config: NovaConfig) -> None:
    """Run a simple text-only REPL in the terminal.

    This does not use audio, hotword detection, or TTS. It is intended as a
    clean, minimal core loop that can be extended later.
    """

    conv = Conversation()
    conv.add_system(build_system_prompt(config))

    llm = GroqLLMClient(model=config.groq_model)

    print("nova2 text chat — type 'exit' to quit.\n")
    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting nova2.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Exiting nova2.")
            break

        conv.add_user(user_input)
        messages = _append_runtime_context(conv.messages, config)

        try:
            result = llm.chat(messages)
        except Exception as exc:  # Keep this user-facing and simple
            print(f"assistant> [ERROR] LLM call failed: {exc}")
            continue

        reply = result.content.strip()
        conv.add_assistant(reply)
        print(f"assistant> {reply}\n")
