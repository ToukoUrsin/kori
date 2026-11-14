from __future__ import annotations

import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("KORI_DATA_DIR", ROOT / "data"))
BUILD_DIR = DATA_DIR / "build"
BENCH_DIR = DATA_DIR / "benchmarks"
STATE_DIR = Path(os.environ.get("KORI_STATE_DIR", DATA_DIR / "state"))
AUDIO_DIR = Path(os.environ.get("KORI_AUDIO_DIR", DATA_DIR / "audio"))
WEB_DIST = Path(os.environ.get("KORI_WEB_DIST", ROOT / "web" / "dist"))

# The dataset covers 2024-10-01 .. 2026-09-30. The app pretends it is this day,
# so there is a real "rest of the month" to plan for and to check forecasts against.
DATA_START = date(2024, 10, 1)
DATA_END = date(2026, 9, 30)
DEMO_TODAY = date.fromisoformat(os.environ.get("KORI_TODAY", "2026-09-21"))

GEMINI_MODEL = os.environ.get("KORI_GEMINI_MODEL", "gemini-4-hydrogen")
# The first step of a turn (choosing the calculation) and the stand-in when a call is slow: the same frontier model.
GEMINI_MODEL_FAST = os.environ.get("KORI_GEMINI_MODEL_FAST", "gemini-4-hydrogen")
GEMINI_MODEL_FALLBACK = GEMINI_MODEL_FAST
# Work nobody is waiting for (anything prepared ahead of a question) runs on the larger model.
GEMINI_MODEL_BACKGROUND = os.environ.get("KORI_GEMINI_MODEL_BACKGROUND", "gemini-4-carbon")


def gemini_key() -> str | None:
    return os.environ.get("JUNCTION_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")


def gemini_fallback_key() -> str | None:
    a, b = os.environ.get("JUNCTION_GEMINI_API_KEY"), os.environ.get("GEMINI_API_KEY")
    return b if a and b and a != b else None


ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_AGENT_ID = os.environ.get("KORI_ELEVENLABS_AGENT_ID")
# shared secret ElevenLabs sends to our custom-LLM endpoint
VOICE_LLM_SECRET = os.environ.get("KORI_VOICE_LLM_SECRET", "dev-secret")
PUBLIC_URL = os.environ.get("KORI_PUBLIC_URL", "http://localhost:8811")
