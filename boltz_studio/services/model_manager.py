"""Model manager for caching Boltz model in memory.

This module provides a singleton model manager that keeps the Boltz model
loaded in memory between predictions, avoiding cold start overhead.
"""

import importlib.util
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..config import settings
from ..logger import get_logger

logger = get_logger("model_manager")

# Check if Boltz is available
_BOLTZ_AVAILABLE = importlib.util.find_spec("boltz") is not None
_TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None
_DIRECT_API_AVAILABLE = _BOLTZ_AVAILABLE and _TORCH_AVAILABLE

if _DIRECT_API_AVAILABLE:
    logger.info("Boltz direct API available")
else:
    logger.info("Boltz direct API not available, using CLI mode")


@dataclass
class Boltz2DiffusionParams:
    """Diffusion process parameters for Boltz2."""

    gamma_0: float = 0.8
    gamma_min: float = 1.0
    noise_scale: float = 1.003
    rho: float = 7
    step_scale: float = 1.5
    sigma_min: float = 0.0001
    sigma_max: float = 160.0
    sigma_data: float = 16.0
    P_mean: float = -1.2
    P_std: float = 1.5
    coordinate_augmentation: bool = True
    alignment_reverse_diff: bool = True
    synchronize_sigmas: bool = True


@dataclass
class PairformerArgsV2:
    """Pairformer arguments for Boltz2."""

    num_blocks: int = 64
    num_heads: int = 16
    dropout: float = 0.0
    activation_checkpointing: bool = False
    offload_to_cpu: bool = False
    v2: bool = True


@dataclass
class MSAModuleArgs:
    """MSA module arguments."""

    msa_s: int = 64
    msa_blocks: int = 4
    msa_dropout: float = 0.0
    z_dropout: float = 0.0
    use_paired_feature: bool = True
    pairwise_head_width: int = 32
    pairwise_num_heads: int = 4
    activation_checkpointing: bool = False
    offload_to_cpu: bool = False
    subsample_msa: bool = False
    num_subsampled_msa: int = 1024


@dataclass
class BoltzSteeringParams:
    """Steering parameters."""

    fk_steering: bool = False
    num_particles: int = 3
    fk_lambda: float = 4.0
    fk_resampling_interval: int = 3
    physical_guidance_update: bool = False
    contact_guidance_update: bool = True
    num_gd_steps: int = 20


class ModelManager:
    """Singleton manager for Boltz model with lazy loading."""

    _instance: "ModelManager | None" = None
    _model: Any = None
    _device: str = "cpu"
    _trainer: Any = None

    def __new__(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def is_direct_api_available(self) -> bool:
        """Check if direct Boltz API is available."""
        return _DIRECT_API_AVAILABLE

    @property
    def device(self) -> str:
        """Get the device the model is loaded on."""
        return self._device

    @property
    def is_loaded(self) -> bool:
        """Check if model is currently loaded."""
        return self._model is not None

    def _detect_device(self) -> str:
        """Detect the best available device.

        Returns:
            Device string: 'mps', 'cuda', or 'cpu'
        """
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _get_accelerator(self) -> str:
        """Get PyTorch Lightning accelerator string."""
        device = self._detect_device()
        if device in ("mps", "cuda"):
            return "gpu"
        return "cpu"

    def get_cache_path(self) -> Path:
        """Get the Boltz cache directory."""
        import os
        env_cache = os.environ.get("BOLTZ_CACHE")
        if env_cache:
            return Path(env_cache).expanduser().resolve()
        return Path.home() / ".boltz"

    def load_model(
        self,
        recycling_steps: int = 3,
        sampling_steps: int = 200,
        diffusion_samples: int = 1,
    ) -> Any:
        """Load and cache the Boltz model.

        Args:
            recycling_steps: Number of recycling steps
            sampling_steps: Number of sampling steps
            diffusion_samples: Number of diffusion samples

        Returns:
            Loaded model instance

        Raises:
            RuntimeError: If direct API is not available
        """
        if not _DIRECT_API_AVAILABLE:
            raise RuntimeError(
                "Boltz direct API not available. Install boltz package."
            )

        if self._model is not None:
            logger.debug("Using cached model")
            return self._model

        logger.info("Loading Boltz model (first prediction will be slower)...")

        import torch
        from boltz.model.models.boltz2 import Boltz2

        # Set torch settings
        torch.set_grad_enabled(False)
        torch.set_float32_matmul_precision("highest")

        # Find checkpoint
        cache = self.get_cache_path()
        checkpoint_path = cache / "boltz2_conf.ckpt"
        if not checkpoint_path.exists():
            raise FileNotFoundError(
                f"Boltz checkpoint not found at {checkpoint_path}. "
                "Run 'boltz predict' once to download it."
            )

        # Detect device
        self._device = self._detect_device()
        logger.info(f"Using device: {self._device}")

        # Set up model parameters
        diffusion_params = Boltz2DiffusionParams()
        pairformer_args = PairformerArgsV2()
        msa_args = MSAModuleArgs(use_paired_feature=True)
        steering_args = BoltzSteeringParams()

        predict_args = {
            "recycling_steps": recycling_steps,
            "sampling_steps": sampling_steps,
            "diffusion_samples": diffusion_samples,
            "max_parallel_samples": 5,
            "write_confidence_summary": True,
            "write_full_pae": False,
            "write_full_pde": False,
        }

        # Load model
        self._model = Boltz2.load_from_checkpoint(
            str(checkpoint_path),
            strict=True,
            predict_args=predict_args,
            map_location="cpu",
            diffusion_process_args=asdict(diffusion_params),
            ema=False,
            use_kernels=True,
            pairformer_args=asdict(pairformer_args),
            msa_args=asdict(msa_args),
            steering_args=asdict(steering_args),
        )
        self._model.eval()

        logger.info("Model loaded successfully")
        return self._model

    def get_model(self) -> Any:
        """Get the cached model, loading if necessary.

        Returns:
            Model instance
        """
        if self._model is None:
            return self.load_model(
                recycling_steps=settings.default_recycling_steps,
                sampling_steps=settings.default_sampling_steps,
                diffusion_samples=settings.default_diffusion_samples,
            )
        return self._model

    def get_trainer(self, out_dir: Path) -> Any:
        """Get a PyTorch Lightning trainer for predictions.

        Args:
            out_dir: Output directory for predictions

        Returns:
            Trainer instance
        """
        from pytorch_lightning import Trainer
        from boltz.data.write.writer import BoltzWriter

        accelerator = self._get_accelerator()

        # Create prediction writer
        pred_writer = BoltzWriter(
            data_dir=out_dir / "processed" / "structures",
            output_dir=out_dir / "predictions",
            output_format="pdb",
            boltz2=True,
            write_embeddings=False,
        )

        # Create trainer
        trainer = Trainer(
            default_root_dir=out_dir,
            strategy="auto",
            callbacks=[pred_writer],
            accelerator=accelerator,
            devices=1,
            precision="bf16-mixed",
            logger=False,
            enable_progress_bar=False,
        )

        return trainer

    def unload_model(self) -> None:
        """Unload model from memory to free resources."""
        if self._model is not None:
            import torch

            del self._model
            self._model = None
            self._trainer = None

            if self._device == "cuda":
                torch.cuda.empty_cache()

            logger.info("Model unloaded")


# Singleton instance
_manager: ModelManager | None = None


def get_model_manager() -> ModelManager:
    """Get the singleton ModelManager instance.

    Returns:
        ModelManager instance
    """
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager
