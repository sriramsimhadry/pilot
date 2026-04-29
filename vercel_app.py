"""
Vercel FastAPI serverless entrypoint.
"""

import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app  # noqa: E402,F401

__all__ = ["app"]

