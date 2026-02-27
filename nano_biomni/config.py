"""Central configuration for Nano-Bio-Omni.

Adapted from biomni/config.py (snap-stanford/Biomni).
All settings can be overridden via environment variables or constructor args.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class NanoConfig:
    # ── LLM ────────────────────────────────────────────────────────────────────
    llm: str = "llama3"
    # "Ollama" | "Custom" (any OpenAI-compatible, e.g. vLLM) | "Anthropic" | "OpenAI"
    source: str | None = None          # auto-detected from model name if None
    base_url: str = "http://localhost:11434"
    api_key: str = "EMPTY"
    temperature: float = 0.0

    # ── Agent behaviour ─────────────────────────────────────────────────────────
    timeout_seconds: int = 120
    # Pause before every tool call and let user inject corrections
    breakpoints: bool = True
    # Max LangGraph recursion steps before giving up
    recursion_limit: int = 50

    # ── Paths ───────────────────────────────────────────────────────────────────
    data_path: str = "./data"

    def __post_init__(self) -> None:
        """Override with environment variables when present."""
        if v := os.getenv("NANO_LLM"):
            self.llm = v
        if v := os.getenv("NANO_SOURCE"):
            self.source = v
        if v := os.getenv("NANO_BASE_URL"):
            self.base_url = v
        if v := os.getenv("NANO_API_KEY"):
            self.api_key = v
        if v := os.getenv("NANO_TEMPERATURE"):
            self.temperature = float(v)
        if v := os.getenv("NANO_TIMEOUT_SECONDS"):
            self.timeout_seconds = int(v)
        if v := os.getenv("NANO_BREAKPOINTS"):
            self.breakpoints = v.lower() not in ("false", "0", "no")
        if v := os.getenv("NANO_DATA_PATH"):
            self.data_path = v

    def to_dict(self) -> dict:
        return {
            "llm": self.llm,
            "source": self.source,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "timeout_seconds": self.timeout_seconds,
            "breakpoints": self.breakpoints,
            "recursion_limit": self.recursion_limit,
            "data_path": self.data_path,
        }


# Module-level default — used when no explicit config is passed
default_config = NanoConfig()
