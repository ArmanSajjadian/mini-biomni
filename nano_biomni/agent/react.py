"""NanoAgent — ReAct reasoning loop for Nano-Bio-Omni.

Adapted from biomni/agent/react.py (snap-stanford/Biomni).

Key changes vs upstream:
  1. All biomni.* imports replaced with nano_biomni.*
  2. Breakpoint system — pauses before every tool call, lets the user inject
     corrections that the LLM sees before the tool runs.
  3. TAO (Thinking / Action / Observation) display via nano_biomni.utils.pretty_print
  4. Interactive _chat_loop() so the session persists after a paper analysis.
  5. Removed ToolRetriever, A1, env_desc references (not needed for nano scope).
  6. Timeout wrappers preserved from upstream (multiprocessing + SIGKILL).
"""

from __future__ import annotations

import json
import os
import signal
from collections.abc import Sequence
from functools import wraps
from multiprocessing import Process, Queue
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from nano_biomni.config import NanoConfig, default_config
from nano_biomni.llm import get_llm
from nano_biomni.utils import api_schema_to_langchain_tool, pretty_print, read_module2api

_BREAKPOINT_BANNER = "━" * 70


class AgentState(TypedDict):
    """Shared state threaded through the LangGraph nodes."""

    messages: Annotated[Sequence[BaseMessage], add_messages]


def _prompt_user_breakpoint(tool_name: str, tool_args: dict) -> str | None:
    """Display a breakpoint prompt and return user feedback (or None to continue)."""
    print(f"\n{_BREAKPOINT_BANNER}")
    print(f"  BREAKPOINT")
    print(f"  Tool : {tool_name}")
    print(f"  Args : {json.dumps(tool_args, indent=2, default=str)}")
    print(_BREAKPOINT_BANNER)
    print("  [Enter] continue  |  type feedback to correct  |  'skip' to disable")
    try:
        response = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        response = ""
    if response.lower() == "skip":
        return "SKIP_ALL"
    return response if response else None


class NanoAgent:
    """Standalone ReAct agent.  Mirrors the react class from Biomni but is
    self-contained — no Biomni package required.
    """

    def __init__(
        self,
        config: NanoConfig | None = None,
        tool_fields: list[str] | None = None,
    ) -> None:
        self.config = config or default_config

        # Ensure data directory exists
        os.makedirs(self.config.data_path, exist_ok=True)

        # Load tool descriptions → LangChain StructuredTools
        module2api = read_module2api(tool_fields)
        tools: list = []
        for module_name, api_list in module2api.items():
            print(f"Registering tools from: {module_name}")
            for api in api_list:
                try:
                    tools.append(api_schema_to_langchain_tool(api, module_name))
                except Exception as exc:
                    print(f"  [warn] could not register '{api.get('name')}': {exc}")
        self.tools = self._add_timeout_to_tools(tools)

        self.llm = get_llm(config=self.config)
        self.system_prompt: str = ""
        self.prompt: ChatPromptTemplate | None = None
        self.app = None
        self.log: list[str] = []
        self._skip_breakpoints = False  # set to True by 'skip' at runtime

    # ── Timeout wrapper (identical to Biomni) ─────────────────────────────────

    def _add_timeout_to_tools(self, tools: list) -> list:
        timeout = self.config.timeout_seconds

        def create_timed_func(original_func, timeout):
            tool_name = getattr(original_func, "__name__", "unknown")

            def process_func(func, args, kwargs, result_queue):
                try:
                    result_queue.put(("success", func(*args, **kwargs)))
                except Exception as exc:
                    result_queue.put(("error", str(exc)))

            @wraps(original_func)
            def timed_func(*args, **kwargs):
                result_queue: Queue = Queue()
                proc = Process(target=process_func, args=(original_func, args, kwargs, result_queue))
                proc.start()
                proc.join(timeout)
                if proc.is_alive():
                    print(f"TIMEOUT: {tool_name} timed out after {timeout}s")
                    proc.terminate()
                    proc.join(1)
                    if proc.is_alive():
                        os.kill(proc.pid, signal.SIGKILL)
                    return f"ERROR: Tool {tool_name} timed out after {timeout}s. Try simpler inputs."
                if not result_queue.empty():
                    status, result = result_queue.get()
                    return result if status == "success" else f"Error in {tool_name}: {result}"
                return "Error: tool completed but returned no result"

            return timed_func

        wrapped = []
        for tool in tools:
            t = tool
            t.func = create_timed_func(tool.func, timeout)
            wrapped.append(t)
        return wrapped

    # ── Configuration (system prompt + graph build) ───────────────────────────

    def configure(
        self,
        system_prompt: str | None = None,
        plan: bool = True,
        paper_context: str | None = None,
    ) -> None:
        """Build the system prompt and compile the LangGraph app.

        Parameters
        ----------
        system_prompt : Explicit override; if None a default biologist prompt is used.
        plan          : When True, asks the LLM to maintain a Research Plan block.
        paper_context : Injected after the base prompt — e.g. extracted experiment steps.
        """
        if system_prompt:
            base = system_prompt
        elif plan:
            base = (
                "You are a helpful biologist and research assistant.\n"
                "Given the user's request:\n"
                "- First, draft a high-level Research Plan and keep it updated.\n"
                "- Track which steps are done and what the observations mean.\n"
                "- Use the available tools to carry out each step.\n"
                "- When you write or run code, explain what it does before running it.\n"
            )
        else:
            base = "You are a helpful biologist and research assistant.\n"

        if paper_context:
            base += "\n" + paper_context

        self.system_prompt = base
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", base),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        self.app = self._build_graph(self.llm, self.tools)
        print("=" * 25 + " System Prompt " + "=" * 25)
        print(base[:600] + ("…" if len(base) > 600 else ""))

    # ── LangGraph construction ────────────────────────────────────────────────

    def _build_graph(self, llm, tools):
        tools_by_name = {t.name: t for t in tools}
        llm_with_tools = llm.bind_tools(tools)
        agent_self = self  # closure reference for breakpoints

        def call_model(state: AgentState, config: RunnableConfig | None = None):
            sys_msg = SystemMessage(content=agent_self.system_prompt)
            response = llm_with_tools.invoke([sys_msg] + list(state["messages"]), config=config)
            return {"messages": [response]}

        def tool_node(state: AgentState):
            outputs: list[ToolMessage] = []
            last_msg = state["messages"][-1]
            tool_calls = getattr(last_msg, "tool_calls", []) or []

            for tc in tool_calls:
                # ── BREAKPOINT ──────────────────────────────────────────────
                injected_feedback: str | None = None
                if agent_self.config.breakpoints and not agent_self._skip_breakpoints:
                    feedback = _prompt_user_breakpoint(tc["name"], tc.get("args", {}))
                    if feedback == "SKIP_ALL":
                        agent_self._skip_breakpoints = True
                    elif feedback:
                        injected_feedback = feedback

                # Run the tool
                try:
                    result = tools_by_name[tc["name"]].invoke(tc.get("args", {}))
                except Exception as exc:
                    result = {"error": str(exc)}

                # If the user provided feedback, prefix it to the observation
                content = json.dumps(result)
                if injected_feedback:
                    content = f"[User note before this result]: {injected_feedback}\n\n{content}"

                outputs.append(
                    ToolMessage(
                        content=content,
                        name=tc["name"],
                        tool_call_id=tc["id"],
                    )
                )
            return {"messages": outputs}

        def should_continue(state: AgentState):
            last = state["messages"][-1]
            if not getattr(last, "tool_calls", None):
                return "end"
            return "continue"

        workflow = StateGraph(AgentState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", should_continue, {"continue": "tools", "end": END})
        workflow.add_edge("tools", "agent")
        return workflow.compile()

    # ── Run ───────────────────────────────────────────────────────────────────

    def go(self, prompt: str) -> tuple[list[str], str]:
        """Execute one task prompt and stream the TAO loop to stdout.

        Returns (log, final_answer).
        """
        if self.app is None:
            self.configure()

        self._skip_breakpoints = False  # reset for each new go() call
        config = {"recursion_limit": self.config.recursion_limit}
        inputs = {"messages": [("user", prompt)]}
        self.log = []

        for s in self.app.stream(inputs, stream_mode="values", config=config):
            message = s["messages"][-1]
            out = pretty_print(message)
            self.log.append(out)

        final_content = s["messages"][-1].content if s else ""
        if isinstance(final_content, list):
            # Flatten Anthropic content blocks
            final_content = " ".join(b.get("text", "") for b in final_content if b.get("type") == "text")
        return self.log, str(final_content)

    # ── Interactive chat loop ─────────────────────────────────────────────────

    def chat(self, initial_prompt: str | None = None) -> None:
        """Persistent terminal chat loop.  Conversation history is maintained
        across turns so the LLM has full context.

        If *initial_prompt* is given it runs as the first turn automatically.
        """
        if self.app is None:
            self.configure()

        # Accumulate the full message history here
        history: list = []

        def _run_turn(user_text: str) -> str:
            nonlocal history
            history.append(("user", user_text))
            self._skip_breakpoints = False
            config = {"recursion_limit": self.config.recursion_limit}
            inputs = {"messages": history}
            last_content = ""

            for s in self.app.stream(inputs, stream_mode="values", config=config):
                message = s["messages"][-1]
                pretty_print(message)
                self.log.append(str(message))

            # Keep the full updated message list for next turn
            history = list(s["messages"])
            last_msg = s["messages"][-1]
            last_content = last_msg.content
            if isinstance(last_content, list):
                last_content = " ".join(b.get("text", "") for b in last_content if b.get("type") == "text")
            return str(last_content)

        if initial_prompt:
            _run_turn(initial_prompt)

        while True:
            try:
                user_input = input("\nYou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Exiting chat loop]")
                break

            if not user_input:
                continue
            if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                print("[Exiting chat loop]")
                break

            _run_turn(user_input)
