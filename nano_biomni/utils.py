"""Utilities for Nano-Bio-Omni.

Adapted from biomni/utils.py (snap-stanford/Biomni).
Key additions:
  - TAO (Thinking / Action / Observation) terminal display
  - Stripped-down tool loading helpers (no Biomni-specific paths)
"""

from __future__ import annotations

import importlib
import io
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from functools import wraps
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# ── TAO display widths ──────────────────────────────────────────────────────────
_WIDTH = 70
_MAX_OBS_CHARS = 3000  # truncate long tool outputs in the terminal


def _divider(label: str, char: str = "━") -> str:
    pad = max(0, _WIDTH - len(label) - 2)
    left = pad // 2
    right = pad - left
    return f"{char * left} {label} {char * right}"


def pretty_print(message: BaseMessage | tuple, printout: bool = True) -> str:
    """Format and optionally print a LangChain message using TAO headers.

    Returns the formatted string regardless of *printout*.
    """
    if isinstance(message, tuple):
        # Raw (role, content) tuples — just stringify
        out = str(message)
        if printout:
            print(out)
        return out

    lines: list[str] = []

    if isinstance(message, AIMessage):
        # ── THINKING ──────────────────────────────────────────────────────────
        if isinstance(message.content, list):
            # Anthropic-style: list of text/tool_use blocks
            text_parts = [b["text"] for b in message.content if b.get("type") == "text" and b.get("text")]
            tool_parts = [b for b in message.content if b.get("type") == "tool_use"]

            if text_parts:
                lines.append(_divider("THINKING"))
                lines.append("\n".join(text_parts).strip())

            for tp in tool_parts:
                lines.append(_divider("ACTION"))
                lines.append(f"Tool : {tp['name']}")
                lines.append(f"Args : {tp['input']}")
        else:
            # Plain string content with optional tool_calls
            if message.content and message.content.strip():
                lines.append(_divider("THINKING"))
                lines.append(message.content.strip())

            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    lines.append(_divider("ACTION"))
                    lines.append(f"Tool : {tc['name']}")
                    lines.append(f"Args : {tc['args']}")

        # If the AI message has no tool calls and no content it's a silent step
        if not lines:
            lines.append(_divider("THINKING"))
            lines.append("(no output)")

    elif isinstance(message, ToolMessage):
        # ── OBSERVATION ───────────────────────────────────────────────────────
        lines.append(_divider("OBSERVATION"))
        content = str(message.content)
        if len(content) > _MAX_OBS_CHARS:
            content = content[:_MAX_OBS_CHARS] + f"\n… [truncated {len(message.content) - _MAX_OBS_CHARS} chars]"
        lines.append(content)

    else:
        # System / Human / other
        lines.append(_divider(message.type.upper() + " MESSAGE"))
        lines.append(str(message.content))

    out = "\n".join(lines) + "\n"
    if printout:
        print(out)
    return out


# ── Tool loading helpers ────────────────────────────────────────────────────────

def read_module2api(tool_fields: list[str] | None = None) -> dict[str, list[dict]]:
    """Load all tool description dicts from nano_biomni.tool.tool_description.

    Returns {module_path: [schema_dict, ...]} matching the Biomni convention
    so that api_schema_to_langchain_tool() can be called identically.
    """
    if tool_fields is None:
        tool_fields = ["literature", "support_tools", "molecular_biology"]

    module2api: dict[str, list[dict]] = {}
    for field in tool_fields:
        desc_module_name = f"nano_biomni.tool.tool_description.{field}"
        impl_module_name = f"nano_biomni.tool.{field}"
        try:
            desc_module = importlib.import_module(desc_module_name)
            module2api[impl_module_name] = desc_module.description
        except ModuleNotFoundError as exc:
            print(f"[utils] Warning: could not load tool description '{field}': {exc}")
    return module2api


class CustomBaseModel(BaseModel):
    """Pydantic base that carries the originating API schema."""

    _api_schema: dict | None = None

    @classmethod
    def set_api_schema(cls, schema: dict) -> None:
        cls._api_schema = schema


def safe_execute_decorator(func):
    """Wrap a tool function so unhandled exceptions become error strings."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            return f"Error executing {func.__name__}: {exc}\n{traceback.format_exc()}"

    return wrapper


def api_schema_to_langchain_tool(api_schema: dict, module_name: str) -> StructuredTool:
    """Convert a Biomni-style API schema dict + its module into a LangChain StructuredTool.

    Adapted from biomni/utils.py — identical schema format, local module resolution.
    """
    module = importlib.import_module(module_name)
    api_function = getattr(module, api_schema["name"])
    api_function = safe_execute_decorator(api_function)

    type_mapping: dict[str, Any] = {
        "string": str,
        "str": str,
        "integer": int,
        "int": int,
        "boolean": bool,
        "bool": bool,
        "List[str]": list[str],
        "List[int]": list[int],
        "Dict": dict,
        "Any": Any,
    }

    annotations: dict[str, Any] = {}
    for param in api_schema.get("required_parameters", []):
        ptype = param["type"]
        annotations[param["name"]] = type_mapping.get(ptype, str)

    fields: dict[str, Any] = {
        param["name"]: Field(description=param.get("description", ""))
        for param in api_schema.get("required_parameters", [])
    }

    ApiInput = type("Input", (CustomBaseModel,), {"__annotations__": annotations, **fields})
    ApiInput.set_api_schema(api_schema)

    return StructuredTool.from_function(
        func=api_function,
        name=api_schema["name"],
        description=api_schema["description"],
        args_schema=ApiInput,
        return_direct=True,
    )


# ── Stdout-capturing exec helper (used by support_tools.run_python_repl) ────────

def capture_exec(code: str, namespace: dict) -> str:
    """Execute *code* in *namespace*, capturing stdout/stderr. Returns output string."""
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            exec(code, namespace)  # noqa: S102
    except Exception:
        buf_err.write(traceback.format_exc())
    stdout = buf_out.getvalue()
    stderr = buf_err.getvalue()
    parts = []
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append("[stderr]\n" + stderr)
    return "\n".join(parts) if parts else "(no output)"
