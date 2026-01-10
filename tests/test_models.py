"""Tests for Pydantic models and validation."""

import pytest
from pydantic import ValidationError

from boltz_studio.models import PredictionRequest, SequenceInput


class TestSequenceInput:
    """Tests for SequenceInput validation."""

    def test_valid_sequence(self):
        """Test valid amino acid sequence."""
        seq = SequenceInput(sequence="MKLAVLKAGIAQGEVLVN")
        assert seq.sequence == "MKLAVLKAGIAQGEVLVN"
        assert seq.id == "A"
        assert seq.type == "protein"

    def test_sequence_uppercase(self):
        """Test that sequences are uppercased."""
        seq = SequenceInput(sequence="mklavlkagiaqgevlvn")
        assert seq.sequence == "MKLAVLKAGIAQGEVLVN"

    def test_sequence_stripped(self):
        """Test that sequences are stripped."""
        seq = SequenceInput(sequence="  MKLAVLK  ")
        assert seq.sequence == "MKLAVLK"

    def test_invalid_amino_acids(self):
        """Test rejection of invalid amino acids."""
        with pytest.raises(ValidationError) as exc_info:
            SequenceInput(sequence="MKXAVLK")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "Invalid amino acids" in str(errors[0]["msg"])

    def test_sequence_too_short(self):
        """Test rejection of sequences shorter than minimum."""
        with pytest.raises(ValidationError) as exc_info:
            SequenceInput(sequence="MKLV")  # 4 residues, min is 5

        errors = exc_info.value.errors()
        assert "too short" in str(errors[0]["msg"]).lower()

    def test_custom_chain_id(self):
        """Test custom chain ID."""
        seq = SequenceInput(id="B", sequence="MKLAVLK")
        assert seq.id == "B"

    def test_molecule_types(self):
        """Test different molecule types."""
        # Protein/DNA/RNA use sequence field
        for mol_type in ["protein", "dna", "rna"]:
            seq = SequenceInput(sequence="MKLAVLK", type=mol_type)
            assert seq.type == mol_type

        # Ligand uses smiles field
        ligand = SequenceInput(smiles="CC(=O)O", type="ligand")
        assert ligand.type == "ligand"
        assert ligand.smiles == "CC(=O)O"

    def test_invalid_molecule_type(self):
        """Test rejection of invalid molecule type."""
        with pytest.raises(ValidationError):
            SequenceInput(sequence="MKLAVLK", type="invalid")

    def test_ligand_requires_smiles(self):
        """Test that ligand type requires smiles field."""
        with pytest.raises(ValidationError) as exc_info:
            SequenceInput(sequence="MKLAVLK", type="ligand")

        errors = exc_info.value.errors()
        assert "smiles" in str(errors[0]["msg"]).lower()

    def test_protein_requires_sequence(self):
        """Test that protein type requires sequence field."""
        with pytest.raises(ValidationError) as exc_info:
            SequenceInput(smiles="CC(=O)O", type="protein")

        errors = exc_info.value.errors()
        assert "sequence" in str(errors[0]["msg"]).lower()

    def test_valid_ligand_smiles(self):
        """Test valid ligand with SMILES."""
        # Aspirin
        ligand = SequenceInput(id="L", smiles="CC(=O)Oc1ccccc1C(=O)O", type="ligand")
        assert ligand.id == "L"
        assert ligand.smiles == "CC(=O)Oc1ccccc1C(=O)O"
        assert ligand.type == "ligand"


class TestPredictionRequest:
    """Tests for PredictionRequest validation."""

    def test_valid_request(self):
        """Test valid prediction request."""
        request = PredictionRequest(
            sequences=[SequenceInput(sequence="MKLAVLKAGIAQGEVLVN")],
            name="test_prediction",
        )
        assert len(request.sequences) == 1
        assert request.name == "test_prediction"
        assert request.recycling_steps == 1
        assert request.sampling_steps == 50
        assert request.diffusion_samples == 1

    def test_multiple_sequences(self):
        """Test request with multiple sequences."""
        request = PredictionRequest(
            sequences=[
                SequenceInput(id="A", sequence="MKLAVLK"),
                SequenceInput(id="B", sequence="GIAQGEV"),
            ],
        )
        assert len(request.sequences) == 2

    def test_custom_parameters(self):
        """Test custom prediction parameters."""
        request = PredictionRequest(
            sequences=[SequenceInput(sequence="MKLAVLK")],
            recycling_steps=3,
            sampling_steps=100,
            diffusion_samples=2,
        )
        assert request.recycling_steps == 3
        assert request.sampling_steps == 100
        assert request.diffusion_samples == 2

    def test_empty_sequences(self):
        """Test rejection of empty sequences list."""
        with pytest.raises(ValidationError):
            PredictionRequest(sequences=[])

    def test_invalid_name_characters(self):
        """Test rejection of invalid name characters."""
        with pytest.raises(ValidationError):
            PredictionRequest(
                sequences=[SequenceInput(sequence="MKLAVLK")],
                name="test prediction!",  # spaces and special chars not allowed
            )

    def test_valid_name_with_underscore(self):
        """Test valid name with underscore and hyphen."""
        request = PredictionRequest(
            sequences=[SequenceInput(sequence="MKLAVLK")],
            name="test_prediction-1",
        )
        assert request.name == "test_prediction-1"

    def test_recycling_steps_bounds(self):
        """Test recycling_steps bounds."""
        # Valid bounds
        PredictionRequest(
            sequences=[SequenceInput(sequence="MKLAVLK")],
            recycling_steps=1,
        )
        PredictionRequest(
            sequences=[SequenceInput(sequence="MKLAVLK")],
            recycling_steps=10,
        )

        # Invalid: too low
        with pytest.raises(ValidationError):
            PredictionRequest(
                sequences=[SequenceInput(sequence="MKLAVLK")],
                recycling_steps=0,
            )

        # Invalid: too high
        with pytest.raises(ValidationError):
            PredictionRequest(
                sequences=[SequenceInput(sequence="MKLAVLK")],
                recycling_steps=11,
            )

    def test_sampling_steps_bounds(self):
        """Test sampling_steps bounds."""
        # Valid bounds
        PredictionRequest(
            sequences=[SequenceInput(sequence="MKLAVLK")],
            sampling_steps=10,
        )
        PredictionRequest(
            sequences=[SequenceInput(sequence="MKLAVLK")],
            sampling_steps=500,
        )

        # Invalid: too low
        with pytest.raises(ValidationError):
            PredictionRequest(
                sequences=[SequenceInput(sequence="MKLAVLK")],
                sampling_steps=5,
            )

        # Invalid: too high
        with pytest.raises(ValidationError):
            PredictionRequest(
                sequences=[SequenceInput(sequence="MKLAVLK")],
                sampling_steps=501,
            )

    def test_protein_ligand_complex(self):
        """Test request with protein and ligand."""
        request = PredictionRequest(
            sequences=[
                SequenceInput(id="A", sequence="MKLAVLK"),
                SequenceInput(id="L", smiles="CC(=O)Oc1ccccc1C(=O)O", type="ligand"),
            ],
            name="docking_test",
        )
        assert len(request.sequences) == 2
        assert request.sequences[0].type == "protein"
        assert request.sequences[1].type == "ligand"
        assert request.sequences[1].smiles == "CC(=O)Oc1ccccc1C(=O)O"
