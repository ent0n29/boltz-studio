"""Model manager for caching Boltz model in memory.

This module provides a singleton model manager that keeps the Boltz model
loaded in memory between predictions, avoiding cold start overhead.

When Boltz is not available, falls back to CLI mode.
"""

import importlib.util
from pathlib import Path
from typing import Any

from ..config import settings
from ..logger import get_logger

logger = get_logger("model_manager")

# Check if Boltz is available using importlib
_DIRECT_API_AVAILABLE = (
    importlib.util.find_spec("boltz") is not None
    and importlib.util.find_spec("torch") is not None
)

if _DIRECT_API_AVAILABLE:
    logger.info("Boltz direct API available")
else:
    logger.info("Boltz direct API not available, using CLI mode")


class ModelManager:
    """Singleton manager for Boltz model with lazy loading."""

    _instance: "ModelManager | None" = None
    _model: Any = None
    _device: str = "cpu"

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

    def load_model(self) -> Any:
        """Load and cache the Boltz model.

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

        from boltz.main import Boltz2

        # Find checkpoint
        checkpoint_path = Path.home() / ".boltz" / "boltz2.ckpt"
        if not checkpoint_path.exists():
            raise FileNotFoundError(
                f"Boltz checkpoint not found at {checkpoint_path}. "
                "Run 'boltz predict' once to download it."
            )

        # Detect device
        self._device = self._detect_device()
        logger.info(f"Using device: {self._device}")

        # Load model
        self._model = Boltz2.load_from_checkpoint(
            str(checkpoint_path),
            strict=True,
            map_location="cpu",
            predict_args={
                "recycling_steps": settings.default_recycling_steps,
                "sampling_steps": settings.default_sampling_steps,
                "diffusion_samples": settings.default_diffusion_samples,
            }
        )
        self._model.eval()

        # Move to device
        if self._device == "mps":
            self._model.to("mps")
        elif self._device == "cuda":
            self._model.cuda()

        logger.info("Model loaded successfully")
        return self._model

    def get_model(self) -> Any:
        """Get the cached model, loading if necessary.

        Returns:
            Model instance
        """
        if self._model is None:
            return self.load_model()
        return self._model

    def unload_model(self) -> None:
        """Unload model from memory to free resources."""
        if self._model is not None:
            import torch

            del self._model
            self._model = None

            if self._device == "cuda":
                torch.cuda.empty_cache()
            elif self._device == "mps":
                # MPS doesn't have explicit cache clearing
                pass

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
