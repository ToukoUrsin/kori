"""Speak a recorded question into the real ElevenLabs agent and print what it heard and what it said back.

The one part scripts/voice_text_test.py leaves out: the ears. A sound file goes in as microphone audio; the test passes when
the agent writes the question down (user_transcript) and answers it aloud (audio bytes come back).

    python scripts/voice_audio_test.py https://kori-coach.fly.dev CUST01885 en question.mp3      # needs ffmpeg
"""
from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import sys
import time

import httpx
import websockets

RATE, CHUNK = 16000, 3200          # 16 kHz mono 16-bit, 100 ms a chunk


def pcm(path: str) -> bytes:
    return subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
                          check=True, capture_output=True).stdout


async def main(base: str, customer: str, lang: str, path: str) -> int:
    speech = pcm(path)
    async with httpx.AsyncClient(base_url=base, timeout=60) as cx:
        r = await cx.get("/api/voice/session", params={"customer": customer, "lang": lang, "transport": "websocket"})
        if r.status_code != 200:
            print("no session:", r.status_code, r.text[:200])
            return 1
        s = r.json()
    heard, said, audio_bytes, spoke = "", [], 0, False
    async with websockets.connect(s["signed_url"], max_size=None) as ws:
        await ws.send(json.dumps({
            "type": "conversation_initiation_client_data",
            "conversation_config_override": {"agent": {"first_message": s["first_message"], "language": s["language"]},
                                             "tts": {"voice_id": s["voice_id"]}, "conversation": {"text_only": False}},
            "custom_llm_extra_body": {"session": s["session"], "customer": customer, "lang": lang},
        }))

        async def mic() -> None:
            """The question once the greeting is over, then silence, 100 ms at a time like a microphone."""
            await asyncio.sleep(14)
            stream = speech + b"\0" * (RATE * 2 * 20)
            for i in range(0, len(stream), CHUNK):
                await ws.send(json.dumps({"user_audio_chunk": base64.b64encode(stream[i:i + CHUNK]).decode()}))
                await asyncio.sleep(0.1)

        task = asyncio.create_task(mic())
        deadline = time.time() + 70
        try:
            while time.time() < deadline:
                try:
                    m = json.loads(await asyncio.wait_for(ws.recv(), 20))
                except asyncio.TimeoutError:
                    break
                t = m.get("type")
                if t == "ping":
                    await ws.send(json.dumps({"type": "pong", "event_id": m["ping_event"]["event_id"]}))
                elif t == "audio":
                    if heard:
                        audio_bytes += len(m["audio_event"].get("audio_base_64", "")) * 3 // 4
                elif t == "user_transcript":
                    heard = m["user_transcription_event"]["user_transcript"]
                    print("HEARD:", heard)
                elif t == "agent_response":
                    txt = m["agent_response_event"]["agent_response"]
                    if heard:
                        said.append(txt)
                        print("KORI:", txt)
                        spoke = True
                    else:
                        print("greeting:", txt[:80])
                if spoke and audio_bytes > 20000:
                    await asyncio.sleep(2)
                    break
        finally:
            task.cancel()
    ok = bool(heard) and bool(said) and audio_bytes > 20000
    print(f"{'PASS' if ok else 'FAIL'}: heard={bool(heard)} answered={bool(said)} audio={audio_bytes} bytes")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(asyncio.run(main(a[0], a[1], a[2], a[3])))
