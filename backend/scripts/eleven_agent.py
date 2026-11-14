"""Create or update the ElevenLabs voice agent that speaks for Kori.

ElevenLabs does the ears and the voice (speech-to-text, turn-taking, text-to-speech, WebRTC).
The thinking stays on our server: the agent uses a "custom LLM" that points at Kori's own
OpenAI-compatible endpoint (/v1/chat/completions), which runs the Gemini tool loop and the number check.

    ELEVENLABS_API_KEY=... KORI_PUBLIC_URL=https://... KORI_VOICE_LLM_SECRET=... \
        python scripts/eleven_agent.py [--agent AGENT_ID]

Prints the agent id (put it in KORI_ELEVENLABS_AGENT_ID).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

API = "https://api.elevenlabs.io"
VOICE_EN = "cgSgspJ2msm6clMCkdW9"   # Jessica
VOICE_FI = "YSabzCJMvEHDduIDMdwV"   # Aurora

PROMPT = ("You are Kori, a personal economic trainer. The reasoning happens in the connected language model; "
          "speak its words naturally, warmly and briefly.")


def config(public_url: str, secret_id: str) -> dict:
    return {
        "name": "Kori money coach",
        "conversation_config": {
            "agent": {
                "first_message": "Hi, I'm Kori. What shall we look at?",
                "language": "en",
                "prompt": {
                    "prompt": PROMPT,
                    "llm": "custom-llm",
                    "temperature": None,
                    # our endpoint runs a tool loop (2 to 6 s). The default is to give up after 4 s and call again,
                    # which made the coach repeat itself: wait instead, and never fall back to another model.
                    "cascade_timeout_seconds": 15,
                    "backup_llm_config": {"preference": "disabled"},
                    "custom_llm": {"url": public_url.rstrip("/") + "/v1", "model_id": "kori-gemini",
                                   "api_key": {"secret_id": secret_id}, "api_type": "chat_completions"},
                },
            },
            "tts": {"model_id": "eleven_v4_turbo", "voice_id": VOICE_EN, "stability": 0.5, "similarity_boost": 0.8, "speed": 1.0},
            "asr": {"provider": "scribe_realtime", "keywords": ["S-Pankki", "Kori", "S-mobiili"]},
            "turn": {"turn_timeout": 8, "turn_eagerness": "normal", "speculative_turn": False,
                     # Kori says its own "let me look" within a second; this is only for a turn that takes unusually long
                     "soft_timeout_config": {"timeout_seconds": 8, "message": "Still working on it...", "use_llm_generated_message": False}},
            "conversation": {"text_only": False, "max_duration_seconds": 600,
                             "client_events": ["audio", "interruption", "user_transcript", "agent_response",
                                               "agent_response_correction", "vad_score", "agent_chat_response_part"]},
            "language_presets": {"fi": {"overrides": {"agent": {"first_message": "Hei, olen Kori. Mitä katsotaan?"},
                                                      "tts": {"voice_id": VOICE_FI}}}},
        },
        "platform_settings": {
            "overrides": {
                "custom_llm_extra_body": True,
                "conversation_config_override": {
                    "agent": {"first_message": True, "language": True},
                    "tts": {"voice_id": True},
                    "conversation": {"text_only": True},
                },
            },
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=os.environ.get("KORI_ELEVENLABS_AGENT_ID"))
    ap.add_argument("--secret-id", default=os.environ.get("KORI_ELEVENLABS_SECRET_ID"))
    a = ap.parse_args()
    key, url, secret = os.environ["ELEVENLABS_API_KEY"], os.environ["KORI_PUBLIC_URL"], os.environ["KORI_VOICE_LLM_SECRET"]
    with httpx.Client(base_url=API, headers={"xi-api-key": key}, timeout=60) as cx:
        secret_id = a.secret_id
        if not secret_id:
            r = cx.post("/v1/convai/secrets", json={"type": "new", "name": "kori-voice-llm", "value": secret})
            if r.status_code >= 400:
                sys.exit(f"secret: {r.status_code} {r.text[:400]}")
            secret_id = r.json()["secret_id"]
        body = config(url, secret_id)
        if a.agent:
            r = cx.patch(f"/v1/convai/agents/{a.agent}", json=body)
        else:
            r = cx.post("/v1/convai/agents/create", json=body)
        if r.status_code >= 400:
            sys.exit(f"agent: {r.status_code} {r.text[:1200]}")
        agent_id = r.json().get("agent_id") or a.agent
        print(json.dumps({"agent_id": agent_id, "secret_id": secret_id}))


if __name__ == "__main__":
    main()
