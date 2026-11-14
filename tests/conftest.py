"""Makes the scripts in ml/ and scraper/ importable from the tests."""

import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "ml"))
sys.path.insert(0, str(REPO_DIR / "scraper"))
