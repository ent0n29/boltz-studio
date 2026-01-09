"""Configuration settings."""

import os
from pathlib import Path

PORT = int(os.getenv("BOLTZ_STUDIO_PORT", "8000"))
HOST = os.getenv("BOLTZ_STUDIO_HOST", "0.0.0.0")
PACKAGE_ROOT = Path(__file__).parent
