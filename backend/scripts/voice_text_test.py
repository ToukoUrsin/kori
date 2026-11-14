"""Drive the real ElevenLabs agent as text (no microphone) and print what comes back.

Checks the whole voice path except the audio itself: ElevenLabs agent -> our custom-LLM endpoint -> Gemini tool loop ->
words back to ElevenLabs, cards to the app's event stream.

    python scripts/voice_text_test.py https://kori-coach.fly.dev CUST00092 en "What is safe for me to spend this week?"
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

import httpx
import websockets


async def main(base: str, customer: str, lang: str, questions: list[str], audio: bool) -> None:
    async with httpx.AsyncClient(base_url=base, timeout=60) as cx:
        s = (await cx.get("/api/voice/session", params={"customer": customer, "lang": lang, "transport": "websocket"})).json()
        print("session", s["session"], "| first:", s["first_message"])
        cards: list[str] = []

        async def events():
            async with cx.stream("GET", "/api/voice/events", params={"session": s["session"]}, timeout=None) as r:
                ev = None
                async for line in r.aiter_lines():
                    if line.startswith("event:"):
                        ev = line[6:].strip()
                    elif line.startswith("data:") and ev:
                        d = json.loads(line[5:])
                        if ev == "card":
                            cards.append(d["card"]["type"])
                            print(f"   [screen] card {d['card']['type']}: {d['card']['title']}")
                        elif ev in ("status", "user", "done"):
                            print(f"   [screen] {ev}: {json.dumps(d, ensure_ascii=False)[:160]}")

        ev_task = asyncio.create_task(events())
        await asyncio.sleep(0.5)
        async with websockets.connect(s["signed_url"], max_size=None) as ws:
            await ws.send(json.dumps({
                "type": "conversation_initiation_client_data",
                "conversation_config_override": {"agent": {"first_message": s["first_message"], "language": s["language"]},
                                                 "tts": {"voice_id": s["voice_id"]},
                                                 "conversation": {"text_only": not audio}},
                "custom_llm_extra_body": {"session": s["session"], "customer": customer, "lang": lang},
            }))
            pending = list(questions)
            t0 = None
            got_first = False
            audio_bytes = 0
            first_audio = None
            deadline = time.time() + 40 + 25 * len(questions)
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), 25)
                except asyncio.TimeoutError:
                    break
                m = json.loads(raw)
                t = m.get("type")
                if t == "ping":
                    await ws.send(json.dumps({"type": "pong", "event_id": m["ping_event"]["event_id"]}))
                elif t == "conversation_initiation_metadata":
                    print("connected", m["conversation_initiation_metadata_event"].get("conversation_id"))
                elif t == "audio":
                    if first_audio is None and t0:
                        first_audio = time.time() - t0
                    audio_bytes += len(m["audio_event"].get("audio_base_64", "")) * 3 // 4
                elif t == "agent_response":
                    txt = m["agent_response_event"]["agent_response"]
                    dt = f"{time.time() - t0:.1f}s" if t0 else "-"
                    print(f"KORI ({dt}, first audio {first_audio and round(first_audio, 1)}): {txt}")
                    if not got_first:
                        got_first = True
                    if pending:
                        await asyncio.sleep(1.0 if not audio else 4.0)
                        q = pending.pop(0)
                        print("YOU:", q)
                        t0, first_audio = time.time(), None
                        await ws.send(json.dumps({"type": "user_message", "text": q}))
                    else:
                        await asyncio.sleep(3 if audio else 1)
                        break
                elif t in ("agent_response_correction", "interruption", "client_tool_call"):
                    print(" ", t, json.dumps(m, ensure_ascii=False)[:200])
            print(f"audio received: {audio_bytes} bytes; cards on screen: {cards}")
        ev_task.cancel()


if __name__ == "__main__":
    a = sys.argv[1:]
    audio = "--audio" in a
    a = [x for x in a if x != "--audio"]
    asyncio.run(main(a[0], a[1], a[2], a[3:], audio))
