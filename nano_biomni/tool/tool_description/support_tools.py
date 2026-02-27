"""Tool descriptions for code execution support tools.

Ported from biomni/tool/tool_description/support_tools.py.
"""

description = [
    {
        "name": "run_python_repl",
        "description": (
            "Execute arbitrary Python code in a persistent REPL session.  "
            "Variables and imports defined in earlier calls remain available in subsequent calls.  "
            "Captures and returns stdout / stderr output.  "
            "Use this for data processing, numerical analysis, bioinformatics pipelines, "
            "or any computation that cannot be done by a dedicated tool."
        ),
        "required_parameters": [
            {
                "name": "code",
                "type": "string",
                "description": "Python source code to execute.",
                "default": None,
            }
        ],
        "optional_parameters": [],
    },
]
