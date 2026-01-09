"""Entry point for Boltz Studio."""

import threading
import time
import webbrowser

import uvicorn

from .config import settings


BANNER = """
    ██████╗  ██████╗ ██╗  ████████╗███████╗
    ██╔══██╗██╔═══██╗██║  ╚══██╔══╝╚══███╔╝
    ██████╔╝██║   ██║██║     ██║     ███╔╝
    ██╔══██╗██║   ██║██║     ██║    ███╔╝
    ██████╔╝╚██████╔╝███████╗██║   ███████╗
    ╚═════╝  ╚═════╝ ╚══════╝╚═╝   ╚══════╝ STUDIO
"""


def open_browser() -> None:
    """Open browser after short delay."""
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{settings.port}")


def main() -> None:
    """Run Boltz Studio server."""
    print(BANNER)
    print(f"Starting Boltz Studio on http://localhost:{settings.port}")
    print()
    print("Press Ctrl+C to stop")
    print()

    # Open browser
    threading.Thread(target=open_browser, daemon=True).start()

    # Run server
    uvicorn.run(
        "boltz_studio.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
