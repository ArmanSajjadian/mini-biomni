"""Tool descriptions for literature search tools.

Schema format matches Biomni's tool_description convention so that
api_schema_to_langchain_tool() works without modification.
"""

description = [
    {
        "name": "query_arxiv",
        "description": (
            "Search arXiv for preprints matching the query.  "
            "Returns titles and abstracts of the top results."
        ),
        "required_parameters": [
            {
                "name": "query",
                "type": "string",
                "description": "Search query string (title words, author, topic, etc.)",
                "default": None,
            }
        ],
        "optional_parameters": [
            {
                "name": "max_papers",
                "type": "integer",
                "description": "Maximum number of papers to return.",
                "default": 10,
            }
        ],
    },
    {
        "name": "query_pubmed",
        "description": (
            "Search PubMed for biomedical literature matching the query.  "
            "Returns titles and abstracts of the top results."
        ),
        "required_parameters": [
            {
                "name": "query",
                "type": "string",
                "description": "PubMed search query (supports MeSH terms and boolean operators).",
                "default": None,
            }
        ],
        "optional_parameters": [
            {
                "name": "max_papers",
                "type": "integer",
                "description": "Maximum number of papers to return.",
                "default": 10,
            }
        ],
    },
    {
        "name": "search_google",
        "description": (
            "Perform a web search using Google and return the top result URLs and snippets.  "
            "Use for finding protocols, databases, or recent news not indexed in PubMed/arXiv."
        ),
        "required_parameters": [
            {
                "name": "query",
                "type": "string",
                "description": "Search query string.",
                "default": None,
            }
        ],
        "optional_parameters": [
            {
                "name": "num_results",
                "type": "integer",
                "description": "Number of search results to return.",
                "default": 5,
            }
        ],
    },
    {
        "name": "extract_pdf_content",
        "description": (
            "Download and extract the full text from a PDF at the given URL.  "
            "Useful for reading a specific paper once you have its direct PDF link."
        ),
        "required_parameters": [
            {
                "name": "url",
                "type": "string",
                "description": "Direct URL to a PDF file.",
                "default": None,
            }
        ],
        "optional_parameters": [],
    },
]
