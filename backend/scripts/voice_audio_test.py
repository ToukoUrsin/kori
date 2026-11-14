"""Talk to the real voice agent with real audio, without a microphone.

Each question is synthesised to speech, streamed into the ElevenLabs agent as if it came from a mic
(16 kHz PCM, real-time pacing, silence between turns), and the agent's spoken reply is saved as WAV.
This exercises the whole voice loop: speech-to-text, turn-taking, our custom-LLM endpoint (Gemini tool loop and
number check), cards pushed to the screen, text-to-speech.

    ELEVENLABS_API_KEY=... python scripts/voice_audio_test.py https://kori-coach.fly.dev CUST00092 en out_dir \
        "What is safe for me to spend this week?" "How much did I spend on taxis last month?"

Writes out_dir/turn-N-user.wav, turn-N-kori.wav and timeline.json (latency per turn, transcripts, cards).
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

import httpx
import websockets

RATE = 16000
CHUNK_MS = 100
USER_VOICE = {"en": "cjVigY5qzO86Huf0OWal", "fi": "ESapivUCtGNuYKDCwzcI"}   # Eric / Aapo, so the user does not sound like the coach


def tts_pcm(text: str, lang: str) -> bytes:
    r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{USER_VOICE[lang]}",
                   params={"output_format": "pcm_16000"}, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
                   json={"text": text, "model_id": "eleven_multilingual_v2", "language_code": lang}, timeout=60)
    if r.status_code >= 400:   # some tiers reject language_code on this model
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{USER_VOICE[lang]}",
                       params={"output_format": "pcm_16000"}, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
                       json={"text": text, "model_id": "eleven_multilingual_v2"}, timeout=60)
    r.raise_for_status()
    return r.content


def save_wav(path: Path, pcm: bytes, rate: int = RATE) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


async def main(base: str, customer: str, lang: str, out: Path, questions: list[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    clips = [tts_pcm(q, lang) for q in questions]
    for i, c in enumerate(clips):
        save_wav(out / f"turn-{i + 1}-user.wav", c)
    timeline: list[dict] = []
    async with httpx.AsyncClient(base_url=base, timeout=60) as cx:
        s = (await cx.get("/api/voice/session", params={"customer": customer, "lang": lang, "transport": "websocket"})).json()
        screen: list[dict] = []
        t_start = time.time()

        async def events():
            async with cx.stream("GET", "/api/voice/events", params={"session": s["session"]}, timeout=None) as r:
                ev = None
                async for line in r.aiter_lines():
                    if line.startswith("event:"):
                        ev = line[6:].strip()
                    elif line.startswith("data:") and ev:
                        d = json.loads(line[5:])
                        item = {"t": round(time.time() - t_start, 2), "event": ev}
                        if ev == "card":
                            item |= {"type": d["card"]["type"], "title": d["card"]["title"]}
                        elif ev in ("user", "coach"):
                            item |= {"text": d.get("text")}
                        elif ev == "status":
                            item |= {"label": d.get("label")}
                        elif ev == "done":
                            item |= {"grounded": d.get("grounded"), "checked": d.get("checked"), "ms": d.get("ms")}
                        screen.append(item)

        ev_task = asyncio.create_task(events())
        await asyncio.sleep(0.4)
        async with websockets.connect(s["signed_url"], max_size=None) as ws:
            await ws.send(json.dumps({
                "type": "conversation_initiation_client_data",
                "conversation_config_override": {"agent": {"first_message": s["first_message"], "language": s["language"]},
                                                 "tts": {"voice_id": s["voice_id"]}},
                "custom_llm_extra_body": {"session": s["session"], "customer": customer, "lang": lang}
                | ({"filler": os.environ["KORI_TEST_FILLER"]} if "KORI_TEST_FILLER" in os.environ else {}),
            }))
            state = {"audio": bytearray(), "last_audio": 0.0, "agent_text": [], "user_text": None, "first_audio": None,
                     "speaking_until": 0.0, "fmt": None}
            send_q: asyncio.Queue = asyncio.Queue()

            async def reader():
                async for raw in ws:
                    m = json.loads(raw)
                    t = m.get("type")
                    if t == "ping":
                        await ws.send(json.dumps({"type": "pong", "event_id": m["ping_event"]["event_id"]}))
                    elif t == "conversation_initiation_metadata":
                        state["fmt"] = m["conversation_initiation_metadata_event"].get("agent_output_audio_format")
                    elif t == "audio":
                        b = base64.b64decode(m["audio_event"]["audio_base_64"])
                        if state["first_audio"] is None:
                            state["first_audio"] = time.time()
                        state["audio"].extend(b)
                        state["last_audio"] = time.time()
                    elif t == "agent_response":
                        state["agent_text"].append(m["agent_response_event"]["agent_response"])
                    elif t == "user_transcript":
                        state["user_text"] = m["user_transcription_event"]["user_transcript"]

            async def mic():
                """A microphone never stops: send silence unless a clip is queued."""
                silence = bytes(RATE * 2 * CHUNK_MS // 1000)
                buf = b""
                while True:
                    if not buf and not send_q.empty():
                        buf = send_q.get_nowait()
                    step = RATE * 2 * CHUNK_MS // 1000
                    chunk, buf = (buf[:step], buf[step:]) if buf else (silence, b"")
                    if len(chunk) < step:
                        chunk += bytes(step - len(chunk))
                    await ws.send(json.dumps({"user_audio_chunk": base64.b64encode(chunk).decode()}))
                    await asyncio.sleep(CHUNK_MS / 1000)

            rt, mt = asyncio.create_task(reader()), asyncio.create_task(mic())

            async def wait_reply(t0: float, limit: float = 45) -> None:
                """Wait until the agent has spoken and then been quiet for a moment."""
                while time.time() - t0 < limit:
                    await asyncio.sleep(0.2)
                    if state["agent_text"] and state["last_audio"] and time.time() - state["last_audio"] > 1.5:
                        dur = len(state["audio"]) / 2 / RATE
                        if time.time() - (state["first_audio"] or t0) > dur * 0.9:     # audio arrives faster than real time
                            return

            # greeting
            t0 = time.time()
            await wait_reply(t0, 30)
            rate = int((state["fmt"] or "pcm_16000").split("_")[-1]) if (state["fmt"] or "").startswith("pcm") else RATE
            save_wav(out / "turn-0-kori.wav", bytes(state["audio"]), rate)
            timeline.append({"turn": 0, "kori": " ".join(state["agent_text"]), "audio_s": round(len(state["audio"]) / 2 / rate, 1)})
            print("KORI:", timeline[-1]["kori"])

            for i, (q, clip) in enumerate(zip(questions, clips), 1):
                state.update(audio=bytearray(), last_audio=0.0, agent_text=[], user_text=None, first_audio=None)
                clip_s = len(clip) / 2 / RATE
                t_q = time.time()
                await send_q.put(clip)
                await asyncio.sleep(clip_s)                  # the user is still talking
                t_end_speech = time.time()
                await wait_reply(t_end_speech)
                first = round(state["first_audio"] - t_end_speech, 2) if state["first_audio"] else None
                save_wav(out / f"turn-{i}-kori.wav", bytes(state["audio"]), rate)
                item = {"turn": i, "asked": q, "heard": state["user_text"], "kori": " ".join(state["agent_text"]),
                        "question_s": round(clip_s, 1), "first_audio_after_user_stops_s": first,
                        "audio_s": round(len(state["audio"]) / 2 / rate, 1), "t_question": round(t_q - t_start, 2)}
                timeline.append(item)
                print(f"YOU : {q}\n      heard: {state['user_text']}\nKORI ({first}s to first sound): {item['kori']}")
            rt.cancel()
            mt.cancel()
        await asyncio.sleep(0.5)
        ev_task.cancel()
        (out / "timeline.json").write_text(json.dumps({"turns": timeline, "screen": screen, "audio_format": state["fmt"]},
                                                      indent=2, ensure_ascii=False))
        print("cards:", [x["type"] for x in screen if x["event"] == "card"])


if __name__ == "__main__":
    a = sys.argv[1:]
    asyncio.run(main(a[0], a[1], a[2], Path(a[3]), a[4:]))
