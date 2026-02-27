"""Literature search tools for Nano-Bio-Omni.

Ported from biomni/tool/literature.py (snap-stanford/Biomni).
Dependencies: arxiv, biopython, requests, beautifulsoup4, googlesearch-python, PyPDF2
"""

from __future__ import annotations

import time


def query_arxiv(query: str, max_papers: int = 10) -> str:
    """Search arXiv for preprints matching the query.

    Parameters
    ----------
    query      : Search string.
    max_papers : Maximum results to return.
    """
    try:
        import arxiv

        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_papers,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = list(client.results(search))
        if not results:
            return "No papers found on arXiv."
        parts = []
        for paper in results:
            parts.append(
                f"Title   : {paper.title}\n"
                f"Authors : {', '.join(a.name for a in paper.authors[:3])}\n"
                f"Published: {paper.published.strftime('%Y-%m-%d') if paper.published else 'N/A'}\n"
                f"URL     : {paper.entry_id}\n"
                f"Abstract: {paper.summary[:300]}…\n"
            )
        return "\n---\n".join(parts)
    except ImportError:
        return "Error: 'arxiv' package not installed. Run: pip install arxiv"
    except Exception as exc:
        return f"Error querying arXiv: {exc}"


def query_pubmed(query: str, max_papers: int = 10) -> str:
    """Search PubMed for biomedical literature.

    Parameters
    ----------
    query      : PubMed search query.
    max_papers : Maximum results to return.
    """
    try:
        from Bio import Entrez

        Entrez.email = "nano-biomni@example.com"
        max_retries = 3
        for attempt in range(max_retries):
            try:
                handle = Entrez.esearch(db="pubmed", term=query, retmax=max_papers)
                record = Entrez.read(handle)
                handle.close()
                id_list = record.get("IdList", [])
                if not id_list:
                    return "No papers found on PubMed."

                fetch_handle = Entrez.efetch(
                    db="pubmed", id=",".join(id_list), rettype="abstract", retmode="text"
                )
                abstracts = fetch_handle.read()
                fetch_handle.close()
                return str(abstracts)[:8000]
            except Exception as exc:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return f"Error querying PubMed after {max_retries} attempts: {exc}"
    except ImportError:
        return "Error: 'biopython' not installed. Run: pip install biopython"
    return "Error: unexpected state in query_pubmed"


def search_google(query: str, num_results: int = 5) -> str:
    """Search Google and return top result URLs and titles.

    Parameters
    ----------
    query       : Search string.
    num_results : Number of results to return.
    """
    try:
        from googlesearch import search

        results = list(search(query, num_results=num_results, lang="en"))
        if not results:
            return "No Google results found."
        return "\n".join(f"{i+1}. {url}" for i, url in enumerate(results))
    except ImportError:
        return "Error: 'googlesearch-python' not installed. Run: pip install googlesearch-python"
    except Exception as exc:
        return f"Error performing Google search: {exc}"


def extract_pdf_content(url: str) -> str:
    """Download a PDF from a URL and extract its text.

    Parameters
    ----------
    url : Direct URL to a PDF file.
    """
    try:
        import io

        import PyPDF2
        import requests

        headers = {"User-Agent": "Mozilla/5.0 (Nano-Bio-Omni/0.1)"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        reader = PyPDF2.PdfReader(io.BytesIO(response.content))
        pages: list[str] = []
        for i, page in enumerate(reader.pages):
            if i >= 20:  # safety limit
                pages.append("[PDF truncated at page 20]")
                break
            text = page.extract_text() or ""
            pages.append(text)

        full_text = "\n".join(pages)
        return full_text[:8000] if len(full_text) > 8000 else full_text
    except ImportError as exc:
        return f"Error: missing package — {exc}. Run: pip install PyPDF2 requests"
    except Exception as exc:
        return f"Error extracting PDF from {url}: {exc}"
