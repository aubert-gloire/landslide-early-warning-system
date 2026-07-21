import sys
from pathlib import Path

# backend/tests/conftest.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = _REPO_ROOT / "backend"

for p in (_REPO_ROOT, _BACKEND_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
