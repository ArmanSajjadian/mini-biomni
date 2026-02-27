"""Tool descriptions for molecular biology tools.

Lightweight subset ported from biomni/tool/tool_description/molecular_biology.py.
Only includes tools with no heavy ML dependencies (BioPython only).
"""

description = [
    {
        "name": "restriction_mapping",
        "description": (
            "Perform in-silico restriction enzyme digestion on a DNA sequence.  "
            "Returns the cut positions, fragment sizes, and a summary for each requested enzyme."
        ),
        "required_parameters": [
            {
                "name": "sequence",
                "type": "string",
                "description": "DNA sequence (IUPAC alphabet, case-insensitive).",
                "default": None,
            },
            {
                "name": "enzymes",
                "type": "List[str]",
                "description": (
                    "List of restriction enzyme names to test "
                    "(e.g. ['EcoRI', 'BamHI', 'HindIII'])."
                ),
                "default": None,
            },
        ],
        "optional_parameters": [],
    },
    {
        "name": "design_primers",
        "description": (
            "Design PCR primer pairs for the given DNA template sequence.  "
            "Returns forward and reverse primer sequences with their Tm and GC content."
        ),
        "required_parameters": [
            {
                "name": "sequence",
                "type": "string",
                "description": "Target DNA template sequence (5'→3').",
                "default": None,
            }
        ],
        "optional_parameters": [
            {
                "name": "primer_length",
                "type": "integer",
                "description": "Desired primer length in nucleotides.",
                "default": 20,
            },
            {
                "name": "tm_target",
                "type": "integer",
                "description": "Target melting temperature in °C.",
                "default": 60,
            },
        ],
    },
    {
        "name": "reverse_complement",
        "description": "Return the reverse complement of a DNA sequence.",
        "required_parameters": [
            {
                "name": "sequence",
                "type": "string",
                "description": "DNA sequence (A/T/G/C, case-insensitive).",
                "default": None,
            }
        ],
        "optional_parameters": [],
    },
    {
        "name": "translate_dna",
        "description": (
            "Translate a DNA coding sequence into an amino acid sequence.  "
            "Returns the protein sequence using the standard genetic code."
        ),
        "required_parameters": [
            {
                "name": "sequence",
                "type": "string",
                "description": "DNA coding sequence starting with ATG (case-insensitive).",
                "default": None,
            }
        ],
        "optional_parameters": [
            {
                "name": "frame",
                "type": "integer",
                "description": "Reading frame offset: 0, 1, or 2.",
                "default": 0,
            }
        ],
    },
]
