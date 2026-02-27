"""Support tools — Python REPL with persistent namespace.

Ported from biomni/tool/support_tools.py (snap-stanford/Biomni).
The exec namespace is module-level so it persists for the lifetime of the
process (i.e. across multiple tool calls in the same agent session).
"""

from __future__ import annotations

from nano_biomni.utils import capture_exec

# Persistent execution namespace — survives across run_python_repl calls
_REPL_NAMESPACE: dict = {}


def run_python_repl(code: str) -> str:
    """Execute Python code in a persistent REPL session.

    Variables defined in earlier calls remain available in subsequent calls.
    stdout and stderr are captured and returned as a string.

    Parameters
    ----------
    code : Python source code to execute.
    """
    global _REPL_NAMESPACE
    return capture_exec(code, _REPL_NAMESPACE)
