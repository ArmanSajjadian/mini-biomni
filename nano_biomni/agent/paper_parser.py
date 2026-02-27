"""Paper parser for Nano-Bio-Omni.

Accepts a PDF or plain-text file, extracts the methodology sections,
then uses the LLM to identify discrete, replicable experiment steps.
Returns a structured dict injected into the agent's system prompt.
"""

from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel

# ── Section-heading regexes ─────────────────────────────────────────────────────
_METHOD_HEADERS = re.compile(
    r"(?im)^(?:\d+[\.\s]+)?"
    r"(materials?\s+and\s+methods?|experimental\s+(section|procedures?|methods?)|"
    r"methods?\s+and\s+materials?|methodology|methods?|procedures?)"
    r"\s*$"
)
_NEXT_SECTION = re.compile(
    r"(?im)^(?:\d+[\.\s]+)?(?:results?|discussion|conclusion|acknowledgements?|"
    r"references?|supplementary|appendix|funding|author\s+contributions?)"
    r"\s*$"
)

_CHUNK_CHARS = 8000   # max chars sent to the LLM for step extraction
_MAX_PDF_PAGES = 40   # safety limit


def _extract_text_from_pdf(path: str) -> str:
    """Extract full text from a PDF using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ImportError(
            "PyMuPDF is required for PDF parsing.  Install with: pip install PyMuPDF"
        ) from exc

    doc = fitz.open(path)
    pages = []
    for i, page in enumerate(doc):
        if i >= _MAX_PDF_PAGES:
            pages.append(f"\n[… PDF truncated at page {_MAX_PDF_PAGES} …]\n")
            break
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def _extract_text_from_txt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def extract_full_text(path: str) -> str:
    """Return the raw text of a PDF or .txt file."""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return _extract_text_from_pdf(path)
    elif ext in (".txt", ".md"):
        return _extract_text_from_txt(path)
    else:
        # Try PDF first, fall back to text
        try:
            return _extract_text_from_pdf(path)
        except Exception:
            return _extract_text_from_txt(path)


def _find_methods_section(text: str) -> str:
    """Heuristically extract the Methods / Materials section."""
    lines = text.splitlines()
    start_idx = None
    end_idx = len(lines)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if start_idx is None and _METHOD_HEADERS.match(stripped):
            start_idx = i + 1
        elif start_idx is not None and _NEXT_SECTION.match(stripped):
            end_idx = i
            break

    if start_idx is None:
        # No explicit section found — return the whole text (LLM will figure it out)
        return text[:_CHUNK_CHARS]

    methods_text = "\n".join(lines[start_idx:end_idx]).strip()
    # Truncate to a safe LLM input size
    if len(methods_text) > _CHUNK_CHARS:
        methods_text = methods_text[:_CHUNK_CHARS] + "\n\n[… truncated …]"
    return methods_text


def _extract_title(text: str) -> str:
    """Best-effort title extraction: first non-empty line."""
    for line in text.splitlines():
        clean = line.strip()
        if clean and len(clean) > 10:
            return clean[:200]
    return "Unknown title"


def _extract_abstract(text: str) -> str:
    """Return a rough abstract (text up to ~600 chars or first paragraph)."""
    snippet = text[:2000]
    # Look for "Abstract" header
    m = re.search(r"(?im)^abstract\s*\n(.+?)(?=\n\n|\Z)", snippet, re.DOTALL)
    if m:
        return m.group(1).strip()[:600]
    # Fallback: first 600 chars
    return snippet[:600].strip()


_STEP_EXTRACTION_PROMPT = """\
You are a biomedical research assistant.  Below is the Methods section of a scientific paper.

Your task: identify and list ALL discrete, replicable experiment steps described in the Methods.
For each step write one concise sentence in imperative form (e.g. "Prepare X by doing Y").
Number the steps sequentially.  If a step requires a specific reagent, concentration, or instrument, include it.
Do not include general lab-safety or administrative steps.

Methods section:
\"\"\"
{methods_text}
\"\"\"

Reply with ONLY the numbered list of experiment steps, nothing else.
"""


def extract_experiment_steps(methods_text: str, llm: BaseChatModel) -> list[str]:
    """Ask the LLM to pull discrete experiment steps from the methods text."""
    prompt = _STEP_EXTRACTION_PROMPT.format(methods_text=methods_text)
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))

    steps: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        m = re.match(r"^\d+[\.\)]\s+(.+)", line)
        if m:
            steps.append(m.group(1).strip())
        elif line and not steps and not re.match(r"^\d", line):
            # Fallback: lines that look like steps before any numbering
            steps.append(line)
    return steps


def parse_paper(path: str, llm: BaseChatModel) -> dict:
    """Parse a research paper and extract replicable experiment steps.

    Returns
    -------
    dict with keys:
        path          : original file path
        title         : best-effort title
        abstract      : first paragraph / abstract snippet
        methods_text  : extracted Methods section text
        steps         : list[str] of replicable experiment steps
        system_context: formatted string ready to inject into the agent system prompt
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Paper not found: {path}")

    print(f"[paper_parser] Extracting text from: {path}")
    full_text = extract_full_text(path)

    title = _extract_title(full_text)
    abstract = _extract_abstract(full_text)
    methods_text = _find_methods_section(full_text)

    print(f"[paper_parser] Methods section: {len(methods_text)} chars — extracting steps via LLM…")
    steps = extract_experiment_steps(methods_text, llm)
    print(f"[paper_parser] Identified {len(steps)} replicable steps.")

    if steps:
        numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    else:
        numbered = "(No steps could be extracted automatically — see methods text below)"

    system_context = textwrap.dedent(f"""\
        ## Paper Context
        Title   : {title}
        Abstract: {abstract[:300]}…

        ## Replicable Experiment Steps
        The user wants to replicate the following steps extracted from the paper's Methods section.
        Use your available tools to assist with each step.

        {numbered}

        ## Full Methods Text (for reference)
        {methods_text[:2000]}…
    """)

    return {
        "path": path,
        "title": title,
        "abstract": abstract,
        "methods_text": methods_text,
        "steps": steps,
        "system_context": system_context,
    }
