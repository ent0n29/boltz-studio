"""Citation generation for designs."""

from datetime import datetime
from typing import Literal

from ..logger import get_logger

logger = get_logger("citation")

CitationFormat = Literal["bibtex", "apa", "mla", "chicago", "ris"]


def generate_citation(
    design_id: str,
    design_name: str,
    author_name: str,
    created_at: datetime,
    description: str | None = None,
    format: CitationFormat = "bibtex",
    base_url: str = "https://boltz.studio",
) -> str:
    """Generate a citation for a design.

    Args:
        design_id: Design ID
        design_name: Name of the design
        author_name: Name of the author
        created_at: When the design was created
        description: Design description
        format: Citation format
        base_url: Base URL for the design link

    Returns:
        Formatted citation string
    """
    year = created_at.year
    month = created_at.strftime("%B")
    day = created_at.day
    url = f"{base_url}/designs/{design_id}"

    # Clean design name for citation key
    clean_name = "".join(c for c in design_name if c.isalnum())[:20]
    citation_key = f"{author_name.split()[0].lower()}{year}{clean_name.lower()}"

    if format == "bibtex":
        return f"""@misc{{{citation_key},
    author = {{{author_name}}},
    title = {{{design_name}}},
    year = {{{year}}},
    month = {{{month.lower()}}},
    howpublished = {{Boltz Studio}},
    url = {{{url}}},
    note = {{Protein design created with Boltz-2}}
}}"""

    elif format == "apa":
        return (
            f"{author_name} ({year}, {month} {day}). "
            f"{design_name}. Boltz Studio. {url}"
        )

    elif format == "mla":
        return (
            f'{author_name}. "{design_name}." Boltz Studio, '
            f"{day} {month[:3]}. {year}, {url}."
        )

    elif format == "chicago":
        return (
            f'{author_name}. "{design_name}." '
            f"Boltz Studio, {month} {day}, {year}. {url}."
        )

    elif format == "ris":
        return f"""TY  - DATA
AU  - {author_name}
TI  - {design_name}
PY  - {year}
DA  - {year}/{created_at.month:02d}/{day:02d}
PB  - Boltz Studio
UR  - {url}
N1  - Protein design created with Boltz-2
ER  -"""

    else:
        raise ValueError(f"Unknown citation format: {format}")


def generate_doi_placeholder(design_id: str) -> str:
    """Generate a DOI-style identifier for a design.

    Note: This is a placeholder format, not a real DOI.
    Real DOIs require registration with a DOI registration agency.

    Args:
        design_id: Design ID

    Returns:
        DOI-style identifier
    """
    # Use first 8 chars of UUID for shorter identifier
    short_id = design_id.replace("-", "")[:8]
    return f"10.boltz/{short_id}"
