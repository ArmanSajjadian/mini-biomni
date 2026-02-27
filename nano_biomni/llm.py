"""LLM factory for Nano-Bio-Omni.

Adapted from biomni/llm.py (snap-stanford/Biomni).
Supports Ollama, vLLM / any OpenAI-compatible server, Anthropic, and OpenAI.
Auto-detects the backend from the model name so you usually only need to set
NANO_LLM and NANO_BASE_URL in your .env.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal

from langchain_core.language_models.chat_models import BaseChatModel

if TYPE_CHECKING:
    from nano_biomni.config import NanoConfig

SourceType = Literal["OpenAI", "Anthropic", "Ollama", "Custom"]
ALLOWED_SOURCES: set[str] = {"OpenAI", "Anthropic", "Ollama", "Custom"}


def get_llm(
    model: str | None = None,
    temperature: float | None = None,
    source: SourceType | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    config: NanoConfig | None = None,
) -> BaseChatModel:
    """Return a LangChain chat model for the requested backend.

    Parameters
    ----------
    model:       Model name, e.g. "llama3", "qwen2.5:7b",
                 "meta-llama/Llama-3-8B-Instruct", "claude-sonnet-4-5"
    temperature: Sampling temperature (0 = deterministic).
    source:      "Ollama" | "Custom" | "Anthropic" | "OpenAI".
                 Auto-detected from model name when None.
    base_url:    Base URL for Ollama (http://host:11434) or vLLM
                 (http://host:8000/v1).  Only needed for "Ollama" / "Custom".
    api_key:     API key; "EMPTY" for local servers.
    config:      NanoConfig — fills any unset parameters from config values.
    """
    # Fill from config
    if config is not None:
        if model is None:
            model = config.llm
        if temperature is None:
            temperature = config.temperature
        if source is None:
            source = config.source
        if base_url is None:
            base_url = config.base_url
        if api_key is None:
            api_key = config.api_key

    # Hard defaults
    if model is None:
        model = "llama3"
    if temperature is None:
        temperature = 0.0
    if api_key is None:
        api_key = "EMPTY"

    # ── Auto-detect source ───────────────────────────────────────────────────
    if source is None:
        env_source = os.getenv("NANO_SOURCE") or os.getenv("LLM_SOURCE", "")
        if env_source in ALLOWED_SOURCES:
            source = env_source  # type: ignore[assignment]
        elif model.startswith("claude-"):
            source = "Anthropic"
        elif model.startswith("gpt-"):
            source = "OpenAI"
        elif base_url is not None and "ollama" not in (base_url or "").lower() and "11434" not in (base_url or ""):
            # Looks like a non-Ollama OpenAI-compatible server (vLLM, SGLang…)
            source = "Custom"
        elif any(
            kw in model.lower()
            for kw in ("llama", "mistral", "qwen", "gemma", "phi", "deepseek", "orca", "vicuna", "dolphin")
        ):
            source = "Ollama"
        else:
            # Fall back to Ollama — works for most local models
            source = "Ollama"

    # ── Build model ──────────────────────────────────────────────────────────
    if source == "Ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise ImportError(
                "langchain-ollama is required for Ollama models.  "
                "Install with: pip install langchain-ollama"
            ) from exc

        # When a custom base_url is provided (e.g. remote Ollama) pass it through
        kwargs: dict = {"model": model, "temperature": temperature}
        if base_url and base_url != "http://localhost:11434":
            kwargs["base_url"] = base_url
        return ChatOllama(**kwargs)

    elif source == "Custom":
        # Any OpenAI-compatible API: vLLM, SGLang, LM Studio, etc.
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise ImportError(
                "langchain-openai is required for Custom (vLLM/SGLang) models.  "
                "Install with: pip install langchain-openai"
            ) from exc

        if not base_url:
            raise ValueError(
                "base_url must be set when source='Custom' "
                "(e.g. http://localhost:8000/v1 for vLLM)"
            )
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=8192,
            base_url=base_url,
            api_key=api_key,
        )

    elif source == "Anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise ImportError(
                "langchain-anthropic is required for Anthropic models.  "
                "Install with: pip install langchain-anthropic"
            ) from exc

        # Load key from env if not already set
        if not os.environ.get("ANTHROPIC_API_KEY"):
            try:
                import subprocess

                result = subprocess.run(
                    ["bash", "-c", "source ~/.bash_profile 2>/dev/null && echo $ANTHROPIC_API_KEY"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.stdout.strip():
                    os.environ["ANTHROPIC_API_KEY"] = result.stdout.strip()
            except Exception:
                pass

        return ChatAnthropic(model=model, temperature=temperature, max_tokens=8192)

    elif source == "OpenAI":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise ImportError(
                "langchain-openai is required for OpenAI models.  "
                "Install with: pip install langchain-openai"
            ) from exc

        return ChatOpenAI(model=model, temperature=temperature)

    else:
        raise ValueError(
            f"Unknown source '{source}'. Valid options: Ollama, Custom, Anthropic, OpenAI"
        )
