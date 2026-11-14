import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("KORI_STATE_DIR", tempfile.mkdtemp(prefix="kori-state-"))
os.environ.setdefault("KORI_TODAY", "2026-09-21")

HERO = "CUST00092"
