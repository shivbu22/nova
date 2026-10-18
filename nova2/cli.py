from __future__ import annotations

from .config import load_config, save_config, NovaConfig
from .core_engine import run_repl


def main() -> None:
    cfg = load_config()

    # On first run, persist defaults so users can edit the file manually
    save_config(cfg)

    run_repl(cfg)


if __name__ == "__main__":  # pragma: no cover
    main()
