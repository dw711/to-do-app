import sys
from pathlib import Path

# Make the `app` package importable regardless of where pytest is invoked
# from (bare `pytest`, `python -m pytest`, repo root, backend/, etc.).
# `models.py` imports `from app import db`, so the backend directory must
# be on sys.path for the test suite to collect.
sys.path.insert(0, str(Path(__file__).resolve().parent))
