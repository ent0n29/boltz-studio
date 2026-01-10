"""Entry point for Boltz Studio."""

import logging
import threading
import time
import warnings
import webbrowser

import uvicorn

from .config import settings
from .logger import get_logger

logger = get_logger("main")

BANNER = """
    ██████╗  ██████╗ ██╗  ████████╗███████╗
    ██╔══██╗██╔═══██╗██║  ╚══██╔══╝╚══███╔╝
    ██████╔╝██║   ██║██║     ██║     ███╔╝
    ██╔══██╗██║   ██║██║     ██║    ███╔╝
    ██████╔╝╚██████╔╝███████╗██║   ███████╗
    ╚═════╝  ╚═════╝ ╚══════╝╚═╝   ╚══════╝ STUDIO
"""


def suppress_harmless_warnings() -> None:
    """Suppress known harmless warnings from dependencies."""
    # Suppress MPS pin_memory warning (not supported but harmless)
    warnings.filterwarnings("ignore", message=".*pin_memory.*MPS.*")
    # Suppress CUDA autocast warning when using MPS
    warnings.filterwarnings("ignore", message=".*device_type.*cuda.*CUDA is not available.*")
    # Suppress PyTorch Lightning num_workers suggestion
    warnings.filterwarnings("ignore", message=".*does not have many workers.*")
    # Suppress PyTorch Lightning dataloader warnings
    logging.getLogger("pytorch_lightning").setLevel(logging.WARNING)


def open_browser() -> None:
    """Open browser after short delay."""
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{settings.port}")


def main() -> None:
    """Run Boltz Studio server."""
    # Suppress known harmless warnings
    suppress_harmless_warnings()

    # Print banner (decorative, ok to use print)
    print(BANNER)

    logger.info(f"Starting Boltz Studio on http://localhost:{settings.port}")
    logger.info("Press Ctrl+C to stop")

    # Open browser
    threading.Thread(target=open_browser, daemon=True).start()

    # Run server
    uvicorn.run(
        "boltz_studio.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
