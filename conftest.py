"""Rend le paquet `cosmo` importable dans les tests (import cosmo...)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
