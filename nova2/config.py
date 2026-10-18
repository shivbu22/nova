from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal, Any, Dict
import json


# Default path for nova2 configuration (stored at repo root by default)
CONFIG_PATH = Path(__file__).resolve().parent.parent / "nova2.config.json"


OfflineMode = Literal["False", "True", "Mixed"]


@dataclass
class NovaConfig:
    """Configuration for the nova2 assistant.

    This intentionally mirrors the key ideas of the legacy NovaSettings.config
    file but uses a typed, dataclass-based representation.
    """

    language: str = "en"
    hotword: str = "Nova"
    # Use a currently supported Groq Llama 3 model by default.
    # The older "llama3-70b-8192" model has been decommissioned.
    groq_model: str = "llama3-8b-8192"
    elevenlabs_model: str = "eleven_turbo_v2_5"
    elevenlabs_voice_id: str = "Xb7hH8MSUJpSbSDYk0k2"
    offline_mode: OfflineMode = "False"
    stream_voice: bool = True
    microphone_index: int = 0
    behaviour: str = "You are an AI assistant called 'Nova'."
    name: str = ""


def _coerce_offline_mode(value: Any) -> OfflineMode:
    if value in ("False", "True", "Mixed"):
        return value  # type: ignore[return-value]
    # Fallback to online if invalid
    return "False"


def load_config(path: Path | None = None) -> NovaConfig:
    """Load configuration from JSON, falling back to defaults if missing.

    This is deliberately tolerant: unknown keys are ignored, and on any parse
    error we return the default configuration.
    """

    cfg_path = path or CONFIG_PATH
    if not cfg_path.is_file():
        return NovaConfig()

    try:
        data: Dict[str, Any] = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return NovaConfig()

    raw_model = str(data.get("groq_model", "llama3-8b-8192"))
    # Migrate deprecated Groq model name if present
    if raw_model == "llama3-70b-8192":
        raw_model = "llama3-8b-8192"

    return NovaConfig(
        language=str(data.get("language", "en")),
        hotword=str(data.get("hotword", "Nova")),
        groq_model=raw_model,
        elevenlabs_model=str(data.get("elevenlabs_model", "eleven_turbo_v2_5")),
        elevenlabs_voice_id=str(
            data.get("elevenlabs_voice_id", "Xb7hH8MSUJpSbSDYk0k2")
        ),
        offline_mode=_coerce_offline_mode(data.get("offline_mode", "False")),
        stream_voice=bool(data.get("stream_voice", True)),
        microphone_index=int(data.get("microphone_index", 0)),
        behaviour=str(
            data.get(
                "behaviour", "You are an AI assistant called 'Nova'."
            )
        ),
        name=str(data.get("name", "")),
    )


def save_config(config: NovaConfig, path: Path | None = None) -> None:
    """Persist configuration to JSON.

    This creates parent directories as needed.
    """

    cfg_path = path or CONFIG_PATH
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(config)
    cfg_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
