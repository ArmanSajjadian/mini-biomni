"""Molecular biology tools — lightweight, no GPU dependencies.

Ported / adapted from biomni/tool/molecular_biology.py (snap-stanford/Biomni).
Depends only on BioPython (biopython).
"""

from __future__ import annotations


def restriction_mapping(sequence: str, enzymes: list[str]) -> str:
    """Perform in-silico restriction enzyme digestion.

    Parameters
    ----------
    sequence : DNA sequence (IUPAC, case-insensitive).
    enzymes  : List of enzyme names, e.g. ['EcoRI', 'BamHI'].
    """
    try:
        from Bio.Restriction import RestrictionBatch
        from Bio.Seq import Seq

        seq = Seq(sequence.upper().strip())
        rb = RestrictionBatch(enzymes)
        analysis = rb.search(seq)

        lines: list[str] = [f"Restriction mapping of {len(seq)}-bp sequence\n"]
        for enzyme, cuts in analysis.items():
            if cuts:
                fragments = _compute_fragment_sizes(cuts, len(seq))
                lines.append(
                    f"{enzyme}: {len(cuts)} cut(s) at positions {cuts}\n"
                    f"  Fragment sizes: {fragments}"
                )
            else:
                lines.append(f"{enzyme}: no cuts")
        return "\n".join(lines)
    except ImportError:
        return "Error: 'biopython' not installed. Run: pip install biopython"
    except Exception as exc:
        return f"Error in restriction_mapping: {exc}"


def _compute_fragment_sizes(cut_positions: list[int], seq_len: int) -> list[int]:
    """Compute fragment sizes from cut positions (1-based BioPython convention)."""
    positions = sorted(cut_positions)
    boundaries = [0] + positions + [seq_len]
    return [boundaries[i + 1] - boundaries[i] for i in range(len(boundaries) - 1)]


def design_primers(
    sequence: str,
    primer_length: int = 20,
    tm_target: int = 60,
) -> str:
    """Design PCR primers for the given DNA template.

    Parameters
    ----------
    sequence      : Target DNA template (5'→3').
    primer_length : Desired primer length in nt (default 20).
    tm_target     : Target Tm in °C (default 60).
    """
    try:
        from Bio.SeqUtils import MeltingTemp as MT
        from Bio.Seq import Seq

        seq = sequence.upper().strip().replace(" ", "")
        if len(seq) < primer_length * 2 + 10:
            return f"Sequence too short ({len(seq)} bp) for primer design with length {primer_length}."

        # Simple scan: try different start positions on both ends and pick the
        # candidate closest to tm_target.
        def _best_primer(region: str) -> tuple[str, float, float]:
            best = (region[:primer_length], None, None)
            best_delta = float("inf")
            for start in range(min(10, len(region) - primer_length)):
                cand = region[start : start + primer_length]
                try:
                    tm = float(MT.Tm_NN(Seq(cand)))
                except Exception:
                    tm = _tm_wallace(cand)
                gc = _gc_content(cand)
                delta = abs(tm - tm_target)
                if delta < best_delta:
                    best = (cand, round(tm, 1), round(gc, 1))
                    best_delta = delta
            return best

        fwd_region = seq[:primer_length + 10]
        rev_region = str(Seq(seq[-primer_length - 10 :]).reverse_complement())

        fwd, fwd_tm, fwd_gc = _best_primer(fwd_region)
        rev, rev_tm, rev_gc = _best_primer(rev_region)

        return (
            f"Forward primer : 5'-{fwd}-3'\n"
            f"  Tm={fwd_tm}°C  GC={fwd_gc}%\n"
            f"Reverse primer : 5'-{rev}-3'\n"
            f"  Tm={rev_tm}°C  GC={rev_gc}%\n"
            f"Expected amplicon size: {len(seq) - (len(seq) - primer_length) + primer_length} bp (approx)"
        )
    except ImportError:
        return "Error: 'biopython' not installed. Run: pip install biopython"
    except Exception as exc:
        return f"Error in design_primers: {exc}"


def _tm_wallace(seq: str) -> float:
    """Basic Wallace rule Tm: 2*(A+T) + 4*(G+C)."""
    s = seq.upper()
    return 2 * (s.count("A") + s.count("T")) + 4 * (s.count("G") + s.count("C"))


def _gc_content(seq: str) -> float:
    s = seq.upper()
    if not s:
        return 0.0
    return 100.0 * (s.count("G") + s.count("C")) / len(s)


def reverse_complement(sequence: str) -> str:
    """Return the reverse complement of a DNA sequence.

    Parameters
    ----------
    sequence : DNA sequence (A/T/G/C, case-insensitive).
    """
    try:
        from Bio.Seq import Seq

        return str(Seq(sequence.upper().strip()).reverse_complement())
    except ImportError:
        # Pure-Python fallback
        comp = str.maketrans("ATGCatgc", "TACGtacg")
        return sequence.translate(comp)[::-1]
    except Exception as exc:
        return f"Error in reverse_complement: {exc}"


def translate_dna(sequence: str, frame: int = 0) -> str:
    """Translate a DNA coding sequence to amino acids.

    Parameters
    ----------
    sequence : DNA coding sequence (case-insensitive).
    frame    : Reading frame offset — 0, 1, or 2.
    """
    try:
        from Bio.Seq import Seq

        seq = Seq(sequence.upper().strip()[frame:])
        protein = str(seq.translate(to_stop=False))
        return f"Protein ({len(protein)} aa): {protein}"
    except ImportError:
        return "Error: 'biopython' not installed. Run: pip install biopython"
    except Exception as exc:
        return f"Error in translate_dna: {exc}"
