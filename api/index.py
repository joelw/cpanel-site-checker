"""Vercel entry point for the cPanel Site Checker web interface."""

import sys
import os
from pathlib import Path

# Add project root and web_interface to path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "web_interface"))

# Point the app at the bundled database
os.environ.setdefault("SITE_CHECKER_DB", str(root / "site_checker.db"))
os.environ.setdefault("SITE_CHECKER_OUTPUT_DIR", str(root))

from web_interface.app import app  # noqa: F401, E402 — re-exported for Vercel
