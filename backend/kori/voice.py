"""ElevenLabs: the voice agent session, the narrated "money minute", plain speech in and out."""
from __future__ import annotations

import asyncio

import base64
import hashlib
import json
import logging

import httpx

from . import config
from .engine import insights
from .engine.core import Money
from .engine.insights import eur, whole
from .engine.query import MONTHS_LONG
from .state import name_of
from .wording import adapt

log = logging.getLogger("kori.voice")
API = "https://api.elevenlabs.io"
VOICES = {"en": "cgSgspJ2msm6clMCkdW9", "fi": "YSabzCJMvEHDduIDMdwV"}       # Jessica, Aurora
TTS_MODEL = "eleven_multilingual_v2"


def _headers() -> dict:
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    return {"xi-api-key": config.ELEVENLABS_API_KEY}


def spoken_eur(v: float, lang: str) -> str:
    n = whole(v)
    return f"{n:,} euros" if lang == "en" else f"{n} euroa"


def spoken_day(d, lang: str) -> str:
    if lang == "en":
        suf = "th" if 11 <= d.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10, "th")
        return f"the {d.day}{suf} of {MONTHS_LONG['en'][d.month - 1]}"
    return f"{d.day}. {MONTHS_LONG['fi'][d.month - 1]}ta"


VERDICT_SPOKEN = {"on_track": ("is on track", "on hyvässä vauhdissa"), "at_risk": ("needs attention", "vaatii huomiota"),
                  "over": ("has gone over", "on ylittynyt"), "done": ("is done", "on tehty")}


def _aloud(text: str, lang: str) -> str:
    """Written money ("€520", "520 €") the way it is said."""
    import re
    if lang == "en":
        return re.sub(r"€([\d,]+(?:\.\d+)?)", r"\1 euros", text)
    return text.replace(" €", " euroa").replace("\u00a0€", " euroa")


def opening(m: Money, action: dict | None = None) -> dict:
    """Opening line of a voice session, built from the engine, so it is grounded by construction.

    The coach speaks first. With nothing set and a last cycle that went over, it says what it noticed and asks the
    one question (``asks`` is true: the session then remembers the question, so a spoken answer sets the thing).
    With one thing set, it says how that is going.
    """
    from .engine import loop
    s, lang, name = m.safe, m.prefs.lang, name_of(m.customer_id)
    L = lambda en, fi: en if lang == "en" else fi
    hello = L(f"Hi {name}, it's Kori.", f"Hei {name}, Kori tässä.")
    full = L(f"You have {spoken_eur(s['amount'], 'en')} that's safe to spend until payday, about {spoken_eur(s['per_day'], 'en')} a day.",
             f"Sinulla on {spoken_eur(s['amount'], 'fi')} turvallista käyttövaraa palkkapäivään asti, eli noin "
             f"{spoken_eur(s['per_day'], 'fi')} päivässä.")
    ask = L("What shall we look at?", "Mitä katsotaan?")
    if action:
        p = loop.progress(m, action)
        title = _aloud(p["title"], lang)
        title = title[:1].lower() + title[1:]
        v = VERDICT_SPOKEN.get(p["verdict"], VERDICT_SPOKEN["on_track"])[0 if lang == "en" else 1]
        thing = L(f"Your one thing, {title}, {v}.", f"Yksi asiasi, {title}, {v}.")
        return {"text": adapt(m, f"{hello} {full} {thing} {ask}"), "asks": False}
    if m.partial_view:
        full = L(f"On this account you have {spoken_eur(s['amount'], 'en')} free until payday, about {spoken_eur(s['per_day'], 'en')} a day.",
                 f"Tällä tilillä sinulla on {spoken_eur(s['amount'], 'fi')} vapaana palkkapäivään asti, eli noin "
                 f"{spoken_eur(s['per_day'], 'fi')} päivässä.")
        return {"text": adapt(m, f"{hello} {full} {ask}"), "asks": False}
    sug = loop.suggest(m)
    q = sug.get("question") or {}
    if s["amount"] <= 0 and sug["kind"] == "pause_category":
        title = _aloud(sug["title"], lang)
        title = title[:1].lower() + title[1:]
        used = L(f"Your everyday money for this pay cycle is used up, with {s['days_to_payday']} days to payday.",
                 f"Arjen rahasi tältä palkkajaksolta on käytetty, ja palkkapäivään on {s['days_to_payday']} päivää.")
        offer = L(f"One thing to try: {title}. Shall I set it?", f"Yksi asia kokeiltavaksi: {title}. Asetanko sen?")
        return {"text": adapt(m, f"{hello} {used} {offer}"), "asks": True}
    if q.get("spoken"):
        short = L(f"You have {spoken_eur(s['per_day'], 'en')} a day until payday.",
                  f"Sinulla on {spoken_eur(s['per_day'], 'fi')} päivässä palkkapäivään asti.")
        return {"text": adapt(m, f"{hello} {short} {q['spoken']}"), "asks": True}
    ci = loop.check_in(m)
    row = ci.get("cycle") or {}
    held = ""
    if ci.get("available") and row.get("within") and row.get("difference", 0) >= 20:
        held = L(f" Last pay cycle held, with {spoken_eur(row['difference'], 'en')} left over.",
                 f" Viime palkkajakso piti, ja {spoken_eur(row['difference'], 'fi')} jäi yli.")
    return {"text": adapt(m, f"{hello} {full}{held} {ask}"), "asks": False}


def first_message(m: Money, action: dict | None = None) -> str:
    return opening(m, action)["text"]


def minute_script(m: Money) -> list[dict]:
    """The money minute: today's briefing in four short beats. Every figure comes straight from the engine."""
    from datetime import date
    s, lang, name = m.safe, m.prefs.lang, name_of(m.customer_id)
    pay = date.fromisoformat(s["next_payday"])
    notes = [n for n in insights.notices(m, 6) if n["id"] != "runway"]
    f = m.forecast("usual")
    L = lambda en, fi: en if lang == "en" else fi
    if m.partial_view:
        # the same reason Today gives: most of the pay moves to another bank, and only what stays here is counted
        opening_beat = L(
            f"Good morning {name}. This account shows {spoken_eur(m.balance, 'en')}, but most of your salary moves to another bank, "
            f"so I count only what stays here. Of that, {spoken_eur(s['amount'], 'en')} is safe to spend on this account before payday "
            f"on {spoken_day(pay, 'en')}.",
            f"Huomenta {name}. Tällä tilillä on {spoken_eur(m.balance, 'fi')}, mutta suurin osa palkastasi siirtyy toiseen pankkiin, "
            f"joten lasken vain sen, mikä jää tänne. Siitä on {spoken_eur(s['amount'], 'fi')} turvallista käyttää tältä tililtä ennen "
            f"palkkapäivää, joka on {spoken_day(pay, 'fi')}.")
    else:
        opening_beat = L(
            f"Good morning {name}. Your account shows {spoken_eur(m.balance, 'en')}. After housing, bills and a reserve for surprises, "
            f"{spoken_eur(s['amount'], 'en')} of that is safe to spend before payday on {spoken_day(pay, 'en')}.",
            f"Huomenta {name}. Tililläsi on {spoken_eur(m.balance, 'fi')}. Asumisen, laskujen ja yllätysvaran jälkeen siitä on "
            f"{spoken_eur(s['amount'], 'fi')} turvallista käyttää ennen palkkapäivää, joka on {spoken_day(pay, 'fi')}.")
        if m.linked_view:
            opening_beat = L(
                f"Good morning {name}. With the simulated account at your other bank counted in, you have {spoken_eur(m.balance, 'en')}. "
                f"After housing, bills and a reserve for surprises, {spoken_eur(s['amount'], 'en')} of that is safe to spend before payday "
                f"on {spoken_day(pay, 'en')}.",
                f"Huomenta {name}. Kun toisen pankkisi simuloitu tili lasketaan mukaan, sinulla on {spoken_eur(m.balance, 'fi')}. "
                f"Asumisen, laskujen ja yllätysvaran jälkeen siitä on {spoken_eur(s['amount'], 'fi')} turvallista käyttää ennen "
                f"palkkapäivää, joka on {spoken_day(pay, 'fi')}.")
    beats = [
        {"key": "balance", "focus": "safe", "text": opening_beat},
        {"key": "pace", "focus": "forecast",
         "text": L(f"That is {spoken_eur(s['per_day'], 'en')} a day. Your usual pace is {spoken_eur(s['usual_per_day'], 'en')} a day, "
                   f"which would leave you with {spoken_eur(f['before_payday'], 'en')} when your pay lands."
                   if not m.partial_view and f["lowest"]["balance"] >= 0 else
                   f"That is {spoken_eur(s['per_day'], 'en')} a day for the next {s['days_to_payday']} days.",
                   f"Se on {spoken_eur(s['per_day'], 'fi')} päivässä. Tavallinen tahtisi on {spoken_eur(s['usual_per_day'], 'fi')} päivässä, "
                   f"ja sillä tilillesi jäisi {spoken_eur(f['before_payday'], 'fi')}, kun palkkasi tulee."
                   if not m.partial_view and f["lowest"]["balance"] >= 0 else
                   f"Se on {spoken_eur(s['per_day'], 'fi')} päivässä seuraavien {s['days_to_payday']} päivän ajan.")},
    ]
    if notes:
        n = notes[0]
        beats.append({"key": "notice", "focus": "notice:" + n["id"], "text": f"{n['title']}. {n['body']}"})
    beats.append({"key": "close", "focus": "ask",
                  "text": L("That's your money minute. Ask me anything about your own spending, or try a what-if.",
                            "Se oli rahaminuuttisi. Kysy minulta mitä vain omasta kulutuksestasi tai kokeile entä jos -laskelmaa.")})
    for b in beats:   # written symbols read badly aloud
        t = b["text"].replace(" ", " ")
        if lang == "en":
            import re
            t = re.sub(r"€([\d,]+(?:\.\d+)?)", r"\1 euros", t).replace("−", "minus ")
        else:
            t = t.replace(" €", " euroa").replace("−", "miinus ")
        b["text"] = t
    return adapt(m, beats)


async def tts(text: str, lang: str, with_timestamps: bool = False) -> dict:
    """Speech for a text. Returns {"audio": bytes, "words": [{w, start, end}]}."""
    voice = VOICES.get(lang, VOICES["en"])
    body = {"text": text, "model_id": TTS_MODEL, "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "speed": 1.0}}
    async with httpx.AsyncClient(timeout=60) as cx:
        if not with_timestamps:
            r = await cx.post(f"{API}/v1/text-to-speech/{voice}?output_format=mp3_44100_128", headers=_headers(), json=body)
            r.raise_for_status()
            return {"audio": r.content, "words": []}
        r = await cx.post(f"{API}/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128", headers=_headers(), json=body)
        r.raise_for_status()
        j = r.json()
        al = j.get("alignment") or {}
        chars, st, en = al.get("characters") or [], al.get("character_start_times_seconds") or [], al.get("character_end_times_seconds") or []
        words, cur, w0 = [], "", None
        for ch, a, b in zip(chars, st, en):
            if ch.isspace():
                if cur:
                    words.append({"w": cur, "start": round(w0, 3), "end": round(prev_end, 3)})
                cur, w0 = "", None
            else:
                if w0 is None:
                    w0 = a
                cur += ch
                prev_end = b
        if cur:
            words.append({"w": cur, "start": round(w0, 3), "end": round(prev_end, 3)})
        return {"audio": base64.b64decode(j["audio_base64"]), "words": words}


async def tts_cached(text: str, lang: str) -> bytes:
    """Speech for a reply, kept on disk: the same sentence is never paid for twice."""
    key = hashlib.sha1(f"say:{lang}:{TTS_MODEL}:{text}".encode()).hexdigest()[:16]
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    f = config.AUDIO_DIR / f"{key}.mp3"
    if not f.exists():
        f.write_bytes((await tts(text, lang))["audio"])
    return f.read_bytes()


async def minute(m: Money) -> dict:
    """Script + narrated audio with word timings; cached on disk per script text."""
    beats = minute_script(m)
    lang = m.prefs.lang
    text = " ".join(b["text"] for b in beats)
    key = hashlib.sha1(f"{lang}:{TTS_MODEL}:{text}".encode()).hexdigest()[:16]
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    meta, mp3 = config.AUDIO_DIR / f"{key}.json", config.AUDIO_DIR / f"{key}.mp3"
    out = {"beats": beats, "text": text, "audio": None, "words": []}
    if meta.exists() and mp3.exists():
        out.update(json.loads(meta.read_text()))
        out["audio"] = f"/api/audio/{key}.mp3"
    elif config.ELEVENLABS_API_KEY:
        try:
            r = await tts(text, lang, with_timestamps=True)
            mp3.write_bytes(r["audio"])
            meta.write_text(json.dumps({"words": r["words"]}))
            out["words"], out["audio"] = r["words"], f"/api/audio/{key}.mp3"
        except Exception as e:   # noqa: BLE001 - the script still shows as text
            log.warning("minute tts failed: %s", e)
    # where each beat starts, in words, so the app can move the highlight
    idx = 0
    for b in beats:
        b["word_from"] = idx
        idx += len(b["text"].split())
        b["word_to"] = idx
    return out


async def stt(audio: bytes, filename: str, lang: str | None) -> str:
    data = {"model_id": "scribe_v2"}
    if lang:
        data["language_code"] = lang
    async with httpx.AsyncClient(timeout=60) as cx:
        r = await cx.post(f"{API}/v1/speech-to-text", headers=_headers(), data=data, files={"file": (filename, audio)})
        r.raise_for_status()
        return (r.json().get("text") or "").strip()


_credits: tuple[float, bool] = (0.0, True)


async def has_credits() -> bool:
    """False when the speech account has used its month and may not go over: a call would connect and drop at once, and
    speech-to-text would fail too. Asked at most once a minute; if the question itself fails, the answer is yes."""
    global _credits
    import time
    if time.time() - _credits[0] < 60:
        return _credits[1]
    ok = True
    try:
        async with httpx.AsyncClient(timeout=6) as cx:
            r = await cx.get(f"{API}/v1/user/subscription", headers=_headers())
        if r.status_code == 200:
            d = r.json()
            used, limit = d.get("character_count"), d.get("character_limit")
            if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
                ok = used < limit or bool(d.get("can_extend_character_limit"))
    except Exception as e:   # noqa: BLE001 - not knowing is not a reason to refuse
        log.warning("speech credit check failed: %s", e)
    if not ok:
        log.error("speech account is out of credits: live voice, the microphone and new narration are off until it is topped up")
    _credits = (time.time(), ok)
    return ok


class VoiceBusy(Exception):
    """ElevenLabs has no free line for this workspace right now (or the credential call failed)."""


async def conversation_token(agent_id: str, transport: str = "webrtc") -> dict:
    """One credential per call: a WebRTC token for the app, or a signed websocket URL for tests.

    Asking for both reserved two lines per visitor and ran the workspace into its concurrency limit.
    """
    path, key = (("get-signed-url", "signed_url") if transport == "websocket" else ("token", "token"))
    async with httpx.AsyncClient(timeout=20) as cx:
        for wait in (0.0, 0.8):
            if wait:
                await asyncio.sleep(wait)
            r = await cx.get(f"{API}/v1/convai/conversation/{path}", params={"agent_id": agent_id}, headers=_headers())
            if r.status_code == 200 and r.json().get(key):
                return {key: r.json()[key]}
        raise VoiceBusy(f"{r.status_code} {r.text[:200]}")