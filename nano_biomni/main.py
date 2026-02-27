#!/usr/bin/env python3
"""Nano-Bio-Omni — CLI entry point.

Usage
-----
# Chat mode (no paper):
    python main.py --model llama3

# Paper analysis mode:
    python main.py --paper path/to/paper.pdf --model llama3

# With remote Ollama / vLLM:
    python main.py --paper paper.pdf --model qwen2.5:7b \\
        --base-url http://my-server:11434

    python main.py --paper paper.pdf \\
        --model meta-llama/Llama-3-8B-Instruct \\
        --source Custom --base-url http://my-server:8000/v1

# Disable breakpoints (run fully autonomously):
    python main.py --paper paper.pdf --no-breakpoints
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap

from dotenv import load_dotenv

# Load .env before importing project modules so env vars are available
load_dotenv()

from nano_biomni.agent.paper_parser import parse_paper
from nano_biomni.agent.react import NanoAgent
from nano_biomni.config import NanoConfig

_BANNER = textwrap.dedent("""\
    ╔══════════════════════════════════════════════════════════════════════╗
    ║               Nano-Bio-Omni  —  Paper Replication Agent             ║
    ║   Adapted from Stanford SNAP Biomni  •  github.com/snap-stanford   ║
    ╚══════════════════════════════════════════════════════════════════════╝
""")

_TOOLS_HELP = textwrap.dedent("""\
    Available tool modules (comma-separated):
        literature        — PubMed, arXiv, Google, PDF extraction
        support_tools     — Python REPL (persistent namespace)
        molecular_biology — Restriction mapping, primer design, translation
    Default: all three.
""")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nano-biomni",
        description="Biomedical research agent that reads papers and assists with experiment replication.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_TOOLS_HELP,
    )
    p.add_argument(
        "--paper", "-p",
        metavar="PATH",
        default=None,
        help="Path to a research paper (PDF or .txt).  If omitted, starts in plain chat mode.",
    )
    p.add_argument(
        "--model", "-m",
        metavar="MODEL",
        default=None,
        help="LLM model name (e.g. llama3, qwen2.5:7b, claude-sonnet-4-5).  "
             "Overrides NANO_LLM env var.",
    )
    p.add_argument(
        "--base-url", "-u",
        metavar="URL",
        default=None,
        help="Ollama / vLLM base URL (e.g. http://localhost:11434).  Overrides NANO_BASE_URL.",
    )
    p.add_argument(
        "--source", "-s",
        metavar="SOURCE",
        default=None,
        choices=["Ollama", "Custom", "Anthropic", "OpenAI"],
        help="LLM backend: Ollama | Custom | Anthropic | OpenAI.  Auto-detected if omitted.",
    )
    p.add_argument(
        "--tools", "-t",
        metavar="MODULES",
        default="literature,support_tools,molecular_biology",
        help="Comma-separated list of tool modules to load.",
    )
    p.add_argument(
        "--no-breakpoints",
        action="store_true",
        default=False,
        help="Disable breakpoint pauses (run autonomously).",
    )
    p.add_argument(
        "--no-plan",
        action="store_true",
        default=False,
        help="Skip the Research Plan block in the system prompt.",
    )
    p.add_argument(
        "--data-path",
        metavar="DIR",
        default=None,
        help="Directory for intermediate data / downloads.  Default: ./data",
    )
    return p


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    print(_BANNER)

    # ── Build config ─────────────────────────────────────────────────────────
    cfg = NanoConfig()
    if args.model:
        cfg.llm = args.model
    if args.base_url:
        cfg.base_url = args.base_url
    if args.source:
        cfg.source = args.source
    if args.data_path:
        cfg.data_path = args.data_path
    if args.no_breakpoints:
        cfg.breakpoints = False

    tool_fields = [t.strip() for t in args.tools.split(",") if t.strip()]

    print(f"  Model      : {cfg.llm}")
    print(f"  Source     : {cfg.source or 'auto-detect'}")
    print(f"  Base URL   : {cfg.base_url}")
    print(f"  Tools      : {', '.join(tool_fields)}")
    print(f"  Breakpoints: {cfg.breakpoints}")
    print()

    # ── Build agent ──────────────────────────────────────────────────────────
    try:
        agent = NanoAgent(config=cfg, tool_fields=tool_fields)
    except Exception as exc:
        print(f"[ERROR] Could not initialise agent: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Parse paper (if provided) ────────────────────────────────────────────
    paper_context: str | None = None
    initial_prompt: str | None = None

    if args.paper:
        paper_path = args.paper
        if not os.path.exists(paper_path):
            print(f"[ERROR] Paper file not found: {paper_path}", file=sys.stderr)
            sys.exit(1)

        try:
            paper_data = parse_paper(paper_path, agent.llm)
        except Exception as exc:
            print(f"[ERROR] Paper parsing failed: {exc}", file=sys.stderr)
            sys.exit(1)

        paper_context = paper_data["system_context"]

        if paper_data["steps"]:
            steps_preview = "\n".join(
                f"  {i+1}. {s}" for i, s in enumerate(paper_data["steps"][:5])
            )
            ellipsis = f"\n  … and {len(paper_data['steps']) - 5} more" if len(paper_data["steps"]) > 5 else ""
            print(f"\nExtracted {len(paper_data['steps'])} experiment steps:")
            print(steps_preview + ellipsis + "\n")

        initial_prompt = (
            f"I have loaded the paper: \"{paper_data['title']}\".  "
            f"I identified {len(paper_data['steps'])} replicable experiment steps.  "
            "Please start by summarising the key methodology and then help me work through "
            "the experiment steps one by one, using the available tools as needed."
        )

    # ── Configure & run ──────────────────────────────────────────────────────
    agent.configure(
        plan=not args.no_plan,
        paper_context=paper_context,
    )

    print("\nStarting interactive session.  Type 'exit' or Ctrl-C to quit.\n")
    agent.chat(initial_prompt=initial_prompt)


if __name__ == "__main__":
    main()
