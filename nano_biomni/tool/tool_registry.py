"""Minimal tool registry for Nano-Bio-Omni.

Simplified from biomni/tool/tool_registry.py.
Provides a convenient handle to list all registered tools and look them up by name.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from nano_biomni.utils import api_schema_to_langchain_tool, read_module2api


class ToolRegistry:
    """Loads all tool descriptions and builds a name → StructuredTool mapping."""

    def __init__(self, tool_fields: list[str] | None = None) -> None:
        self._tools: dict[str, StructuredTool] = {}
        self._schemas: dict[str, dict] = {}

        module2api = read_module2api(tool_fields)
        for module_name, api_list in module2api.items():
            for schema in api_list:
                try:
                    tool = api_schema_to_langchain_tool(schema, module_name)
                    self._tools[schema["name"]] = tool
                    self._schemas[schema["name"]] = schema
                except Exception as exc:
                    print(f"[ToolRegistry] Warning: skipping '{schema.get('name')}': {exc}")

    @property
    def tools(self) -> list[StructuredTool]:
        return list(self._tools.values())

    def get(self, name: str) -> StructuredTool | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def summary(self) -> str:
        lines = [f"Registered {len(self._tools)} tools:"]
        for name, tool in self._tools.items():
            lines.append(f"  {name}: {tool.description[:80]}")
        return "\n".join(lines)
