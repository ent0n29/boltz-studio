"""Bulk export routes."""

import io
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..logger import get_logger
from ..middleware import RequiredUser
from ..services.design_store import DesignStore, get_design_store
from ..services.citation import generate_citation

logger = get_logger("routes.export")

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/designs")
async def export_designs(
    design_ids: list[str],
    include_pdb: bool = Query(True),
    include_fasta: bool = Query(True),
    include_citation: bool = Query(True),
    include_metadata: bool = Query(True),
    user: RequiredUser = None,  # Optional - for tracking
    store: DesignStore = Depends(get_design_store),
) -> StreamingResponse:
    """Export multiple designs as a ZIP file.

    Args:
        design_ids: List of design IDs to export
        include_pdb: Include PDB structure files
        include_fasta: Include FASTA sequence files
        include_citation: Include citation files
        include_metadata: Include JSON metadata
        user: Optional authenticated user
        store: Design store

    Returns:
        ZIP file containing requested files
    """
    if len(design_ids) > 100:
        raise HTTPException(
            status_code=400,
            detail="Maximum 100 designs per export"
        )

    if len(design_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one design ID required"
        )

    # Create ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for design_id in design_ids:
            design = store.get_public(design_id)
            if not design:
                continue

            # Sanitize name for filesystem
            safe_name = "".join(
                c if c.isalnum() or c in "._- " else "_"
                for c in design.name
            )[:50]
            folder = f"{safe_name}_{design_id[:8]}"

            if include_pdb:
                zf.writestr(
                    f"{folder}/{safe_name}.pdb",
                    design.structure_pdb
                )

            if include_fasta:
                fasta = f">{design.name}\n{design.sequence}\n"
                zf.writestr(
                    f"{folder}/{safe_name}.fasta",
                    fasta
                )

            if include_citation:
                citation = generate_citation(
                    design_id=design_id,
                    design_name=design.name,
                    author_name=design.author.display_name,
                    created_at=design.created_at,
                    format="bibtex",
                )
                zf.writestr(
                    f"{folder}/citation.bib",
                    citation
                )

            if include_metadata:
                import json
                metadata = {
                    "id": design_id,
                    "name": design.name,
                    "description": design.description,
                    "author": design.author.display_name,
                    "author_id": design.author.id,
                    "created_at": design.created_at.isoformat(),
                    "sequence_length": len(design.sequence),
                    "confidence_score": design.confidence_score,
                    "star_count": design.star_count,
                    "fork_count": design.fork_count,
                    "tags": [
                        {"type": t.tag_type, "value": t.tag}
                        for t in (design.tags or [])
                    ],
                }
                zf.writestr(
                    f"{folder}/metadata.json",
                    json.dumps(metadata, indent=2)
                )

        # Add a README
        readme = f"""# Boltz Studio Export
Exported: {datetime.utcnow().isoformat()}
Designs: {len(design_ids)}

## Contents
Each design folder contains:
- {safe_name}.pdb - Protein structure file
- {safe_name}.fasta - Sequence in FASTA format
- citation.bib - BibTeX citation
- metadata.json - Design metadata

## Citation
If you use these designs in your research, please cite:
1. The individual design authors (see citation.bib in each folder)
2. Boltz-2: The structure prediction model

## License
Designs on Boltz Studio are shared under their respective licenses.
Please check with individual authors for usage terms.
"""
        zf.writestr("README.md", readme)

    zip_buffer.seek(0)

    # Generate filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"boltz_export_{timestamp}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/collection/{collection_id}")
async def export_collection(
    collection_id: str,
    include_pdb: bool = Query(True),
    include_fasta: bool = Query(True),
    include_citation: bool = Query(True),
    include_metadata: bool = Query(True),
    user: RequiredUser = None,
    store: DesignStore = Depends(get_design_store),
) -> StreamingResponse:
    """Export all designs in a collection.

    Args:
        collection_id: Collection ID
        include_pdb: Include PDB structure files
        include_fasta: Include FASTA sequence files
        include_citation: Include citation files
        include_metadata: Include JSON metadata
        user: Optional authenticated user
        store: Design store

    Returns:
        ZIP file containing collection designs
    """
    from ..services.social_store import get_social_store

    social_store = get_social_store()

    # Get collection
    collection = social_store.get_collection(collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Get design IDs in collection
    designs = social_store.get_collection_designs(collection_id, 0, 100)
    design_ids = [d.id for d in designs.designs]

    if not design_ids:
        raise HTTPException(status_code=400, detail="Collection is empty")

    # Delegate to the bulk export
    return await export_designs(
        design_ids=design_ids,
        include_pdb=include_pdb,
        include_fasta=include_fasta,
        include_citation=include_citation,
        include_metadata=include_metadata,
        user=user,
        store=store,
    )
