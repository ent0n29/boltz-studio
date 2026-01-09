"""Entry point for Boltz Studio."""

import threading
import webbrowser

import uvicorn

from .config import HOST, PORT


BANNER = """
    ██████╗  ██████╗ ██╗  ████████╗███████╗
    ██╔══██╗██╔═══██╗██║  ╚══██╔══╝╚══███╔╝
    ██████╔╝██║   ██║██║     ██║     ███╔╝
    ██╔══██╗██║   ██║██║     ██║    ███╔╝
    ██████╔╝╚██████╔╝███████╗██║   ███████╗
    ╚═════╝  ╚═════╝ ╚══════╝╚═╝   ╚══════╝ STUDIO
"""


def open_browser():
    """Open browser after short delay."""
    import time
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{PORT}")


def main():
    """Run Boltz Studio server."""
    print(BANNER)
    print(f"Starting Boltz Studio on http://localhost:{PORT}")
    print()
    print("Press Ctrl+C to stop")
    print()

    # Open browser
    threading.Thread(target=open_browser, daemon=True).start()

    # Run server
    uvicorn.run(
        "boltz_studio.app:create_app",
        factory=True,
        host=HOST,
        port=PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
