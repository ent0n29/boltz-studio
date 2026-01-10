"""PDB database routes for fetching structures from RCSB."""

import httpx
from fastapi import APIRouter, HTTPException

from ..logger import get_logger

logger = get_logger("routes.pdb")
router = APIRouter(prefix="/api/pdb", tags=["pdb"])

RCSB_BASE_URL = "https://data.rcsb.org"
RCSB_FILES_URL = "https://files.rcsb.org"


@router.get("/{pdb_id}")
async def get_pdb_info(pdb_id: str) -> dict:
    """Get PDB entry information from RCSB.

    Args:
        pdb_id: 4-character PDB ID (e.g., "1AKE")

    Returns:
        PDB entry info including title, sequence, and organism
    """
    pdb_id = pdb_id.upper().strip()

    if len(pdb_id) != 4:
        raise HTTPException(status_code=400, detail="PDB ID must be 4 characters")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Fetch entry info
            info_url = f"{RCSB_BASE_URL}/rest/v1/core/entry/{pdb_id}"
            info_response = await client.get(info_url)

            if info_response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"PDB entry {pdb_id} not found")

            info_response.raise_for_status()
            info = info_response.json()

            # Fetch polymer entities to get sequences
            polymer_url = f"{RCSB_BASE_URL}/rest/v1/core/polymer_entity/{pdb_id}/1"
            polymer_response = await client.get(polymer_url)
            polymer = polymer_response.json() if polymer_response.status_code == 200 else {}

            # Extract sequence
            sequence = ""
            if polymer and "entity_poly" in polymer:
                sequence = polymer["entity_poly"].get("pdbx_seq_one_letter_code_can", "")
                # Clean sequence (remove whitespace and newlines)
                sequence = "".join(sequence.split())

            return {
                "pdb_id": pdb_id,
                "title": info.get("struct", {}).get("title", "Unknown"),
                "sequence": sequence,
                "organism": _extract_organism(info),
                "resolution": info.get("rcsb_entry_info", {}).get("resolution_combined", [None])[0],
                "method": info.get("exptl", [{}])[0].get("method", "Unknown"),
                "release_date": info.get("rcsb_accession_info", {}).get("initial_release_date"),
            }

    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch PDB {pdb_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch PDB data: {e}")


@router.get("/{pdb_id}/structure")
async def get_pdb_structure(pdb_id: str) -> dict:
    """Download PDB structure file from RCSB.

    Args:
        pdb_id: 4-character PDB ID

    Returns:
        PDB file content
    """
    pdb_id = pdb_id.upper().strip()

    if len(pdb_id) != 4:
        raise HTTPException(status_code=400, detail="PDB ID must be 4 characters")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch PDB file
            pdb_url = f"{RCSB_FILES_URL}/download/{pdb_id}.pdb"
            response = await client.get(pdb_url)

            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"PDB file for {pdb_id} not found")

            response.raise_for_status()

            return {
                "pdb_id": pdb_id,
                "pdb_data": response.text,
            }

    except httpx.HTTPError as e:
        logger.error(f"Failed to download PDB {pdb_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to download PDB: {e}")


@router.get("/search/{query}")
async def search_pdb(query: str, limit: int = 10) -> dict:
    """Search RCSB PDB by text query.

    Args:
        query: Search query (protein name, organism, etc.)
        limit: Maximum results to return

    Returns:
        List of matching PDB entries
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # RCSB search API
            search_url = f"{RCSB_BASE_URL}/search/v2/query"
            search_query = {
                "query": {
                    "type": "terminal",
                    "service": "full_text",
                    "parameters": {"value": query}
                },
                "return_type": "entry",
                "request_options": {
                    "paginate": {"start": 0, "rows": limit},
                    "results_content_type": ["experimental"],
                    "sort": [{"sort_by": "score", "direction": "desc"}]
                }
            }

            response = await client.post(search_url, json=search_query)
            response.raise_for_status()
            data = response.json()

            results = []
            for result in data.get("result_set", []):
                pdb_id = result.get("identifier")
                if pdb_id:
                    results.append({"pdb_id": pdb_id, "score": result.get("score", 0)})

            return {"query": query, "total": data.get("total_count", 0), "results": results}

    except httpx.HTTPError as e:
        logger.error(f"PDB search failed for '{query}': {e}")
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")


def _extract_organism(info: dict) -> str:
    """Extract organism name from PDB info."""
    try:
        sources = info.get("rcsb_entry_info", {}).get("polymer_entity_count_protein", 0)
        if sources > 0:
            # Try to get from polymer entities
            entities = info.get("polymer_entities", [])
            if entities:
                return entities[0].get("rcsb_entity_source_organism", [{}])[0].get("scientific_name", "Unknown")
    except (KeyError, IndexError):
        pass
    return "Unknown"
