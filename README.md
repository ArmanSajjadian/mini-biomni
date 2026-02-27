# Nano-Bio-Omni

A standalone, terminal-based biomedical research agent that reads a scientific paper
and helps you replicate its experiments.

Adapted from [Stanford SNAP — Biomni](https://github.com/snap-stanford/Biomni):
the ReAct reasoning loop, tool schema system, and multi-provider LLM factory are all
ported directly from that project, stripped of heavy dependencies so the whole
system runs on a CPU-only Linux server with a local Ollama or vLLM instance.

---

## Quick start (remote server via SSH)

```bash
# 1. Clone
git clone https://github.com/ArmanSajjadian/mini-biomni.git
cd mini-biomni

# 2. Create a virtual environment (Python 3.11+)
python3 -m venv .venv
source .venv/bin/activate

# 3. Install (upgrade pip first — servers often ship an old version)
pip install --upgrade pip
pip install -r requirements.txt

# Optional: editable install (adds the `nano-biomni` CLI command)
# pip install -e .

# 4. Configure
cp .env.example .env
# Edit .env and set NANO_BASE_URL to your Ollama / vLLM endpoint
nano .env

# 5. Run (paper analysis mode)
python main.py --paper path/to/paper.pdf

# 5b. Run (plain chat mode)
python main.py --model llama3
```

> **Tip — keep the session alive over SSH:**
> ```bash
> tmux new -s nano
> python main.py --paper paper.pdf
> # Ctrl+B then D to detach; tmux attach -t nano to return
> ```

---

## LLM backends

### Ollama (default)
```bash
# .env
NANO_SOURCE=Ollama
NANO_BASE_URL=http://localhost:11434
NANO_LLM=llama3
```

### vLLM (OpenAI-compatible)
```bash
# .env
NANO_SOURCE=Custom
NANO_BASE_URL=http://localhost:8000/v1
NANO_LLM=meta-llama/Llama-3-8B-Instruct
```

### Anthropic / OpenAI (cloud)
```bash
ANTHROPIC_API_KEY=sk-ant-...
NANO_LLM=claude-sonnet-4-5
```

---

## CLI options

```
python main.py [OPTIONS]

  --paper   PATH     PDF or .txt file to analyse (optional — plain chat if omitted)
  --model   MODEL    LLM model name (overrides NANO_LLM)
  --base-url URL     Ollama / vLLM base URL (overrides NANO_BASE_URL)
  --source  SOURCE   Ollama | Custom | Anthropic | OpenAI (auto-detected if omitted)
  --tools   MODULES  Comma-separated tool modules (default: literature,support_tools,molecular_biology)
  --no-breakpoints   Disable breakpoint pauses — run fully autonomously
  --no-plan          Skip the Research Plan block in the system prompt
  --data-path DIR    Directory for intermediate files (default: ./data)
```

---

## What the agent does

1. **Paper parsing** — extracts the Methods section from your PDF using PyMuPDF,
   then asks the LLM to list discrete, replicable experiment steps.

2. **ReAct loop** — runs a LangGraph-based Thinking → Action → Observation cycle,
   displaying each step clearly in the terminal.

3. **Breakpoints** — before every tool call the agent pauses and shows:
   ```
   ━━━━━━━━━━━━━━━━━━ BREAKPOINT ━━━━━━━━━━━━━━━━━━
     Tool : query_pubmed
     Args : {"query": "CRISPR knockin mouse model"}
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     [Enter] continue  |  type feedback to correct  |  'skip' to disable
     >
   ```
   Type feedback to inject a correction the LLM will see before the tool runs,
   or press Enter to continue, or type `skip` to disable breakpoints for this run.

4. **Persistent chat** — after the initial analysis you stay in a chat loop with
   full conversation history, so you can ask follow-up questions or redirect the agent.

---

## Available tools

| Module | Tools |
|--------|-------|
| `literature` | `query_pubmed`, `query_arxiv`, `search_google`, `extract_pdf_content` |
| `support_tools` | `run_python_repl` (persistent Python REPL) |
| `molecular_biology` | `restriction_mapping`, `design_primers`, `reverse_complement`, `translate_dna` |

---

## Project structure

```
mini-biomni/
├── main.py                                  ← CLI entry point
├── nano_biomni/
│   ├── config.py                            ← NanoConfig dataclass
│   ├── llm.py                               ← LLM factory (Ollama / vLLM / Anthropic / OpenAI)
│   ├── utils.py                             ← TAO formatter + tool loading helpers
│   ├── agent/
│   │   ├── react.py                         ← ReAct loop (LangGraph) + breakpoints
│   │   └── paper_parser.py                  ← PDF → experiment steps
│   └── tool/
│       ├── literature.py                    ← PubMed, arXiv, Google, PDF
│       ├── support_tools.py                 ← Python REPL
│       ├── molecular_biology.py             ← Restriction mapping, primers
│       ├── tool_registry.py                 ← Registry helper
│       └── tool_description/               ← JSON-schema dicts (Biomni format)
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## Adapting Biomni tools

Each Biomni domain tool (genomics, pharmacology, etc.) can be ported to this repo by:

1. Copying the implementation file to `nano_biomni/tool/XXX.py`
   (remove any imports that require GPUs or unavailable packages).
2. Copying its tool description file to `nano_biomni/tool/tool_description/XXX.py`.
3. Adding `"XXX"` to the `--tools` argument.

---

## Credits

Core reasoning and tool architecture adapted from:
**Biomni** — Stanford SNAP Lab
https://github.com/snap-stanford/Biomni
Apache-2.0 License
