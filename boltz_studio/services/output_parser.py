"""Parse Boltz output files."""

import json
from pathlib import Path
from typing import Any

from ..logger import get_logger

logger = get_logger("output_parser")


class OutputParser:
    """Parse Boltz prediction output files."""

    @staticmethod
    def parse_pdb(output_dir: Path) -> str:
        """Read PDB structure file.

        Args:
            output_dir: Directory containing output files

        Returns:
            PDB file contents as string
        """
        pdb_files = list(output_dir.glob("*.pdb"))
        if pdb_files:
            logger.debug(f"Found PDB file: {pdb_files[0].name}")
            return pdb_files[0].read_text()
        logger.warning(f"No PDB file found in {output_dir}")
        return ""

    @staticmethod
    def parse_confidence(output_dir: Path) -> dict[str, Any]:
        """Read confidence JSON file.

        Args:
            output_dir: Directory containing output files

        Returns:
            Confidence metrics dictionary
        """
        conf_files = list(output_dir.glob("confidence_*.json"))
        if conf_files:
            logger.debug(f"Found confidence file: {conf_files[0].name}")
            return json.loads(conf_files[0].read_text())
        logger.warning(f"No confidence file found in {output_dir}")
        return {}

    @staticmethod
    def parse_plddt(output_dir: Path) -> list[float]:
        """Read per-residue pLDDT from NPZ file.

        Args:
            output_dir: Directory containing output files

        Returns:
            List of pLDDT values per residue
        """
        import numpy as np

        plddt_files = list(output_dir.glob("plddt_*.npz"))
        if plddt_files:
            logger.debug(f"Found pLDDT file: {plddt_files[0].name}")
            data = np.load(plddt_files[0])
            if "plddt" in data:
                return data["plddt"].tolist()
        logger.warning(f"No pLDDT file found in {output_dir}")
        return []

    @staticmethod
    def parse_affinity(output_dir: Path) -> dict[str, Any]:
        """Read binding affinity JSON file.

        Args:
            output_dir: Directory containing output files

        Returns:
            Affinity metrics dictionary with keys:
            - affinity_pred_value: Raw affinity prediction
            - affinity_probability_binary: Binding probability (0-1)
        """
        affinity_files = list(output_dir.glob("affinity_*.json"))
        if affinity_files:
            logger.debug(f"Found affinity file: {affinity_files[0].name}")
            return json.loads(affinity_files[0].read_text())
        logger.debug(f"No affinity file found in {output_dir}")
        return {}
