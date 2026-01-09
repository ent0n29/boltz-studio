"""Parse Boltz output files."""

import json
from pathlib import Path


class OutputParser:
    """Parse Boltz prediction output files."""

    @staticmethod
    def parse_pdb(output_dir: Path) -> str:
        """Read PDB structure file."""
        pdb_files = list(output_dir.glob("*.pdb"))
        if pdb_files:
            return pdb_files[0].read_text()
        return ""

    @staticmethod
    def parse_confidence(output_dir: Path) -> dict:
        """Read confidence JSON file."""
        conf_files = list(output_dir.glob("confidence_*.json"))
        if conf_files:
            return json.loads(conf_files[0].read_text())
        return {}

    @staticmethod
    def parse_plddt(output_dir: Path) -> list[float]:
        """Read per-residue pLDDT from NPZ file."""
        import numpy as np

        plddt_files = list(output_dir.glob("plddt_*.npz"))
        if plddt_files:
            data = np.load(plddt_files[0])
            if "plddt" in data:
                return data["plddt"].tolist()
        return []
