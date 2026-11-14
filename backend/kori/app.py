"""Kori API. Run: PYTHONPATH=. uv run uvicorn kori.app:app --port 8811"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import date

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from . import config, state as S, voice
from .ai import agent, cards as C, tools as T
from .data import get_customer
from .engine import insights, lessons, persona
from .engine.core import Money
from .engine.query import month_label, query, tx_row
from .engine.whatif import what_if
from .taxonomy import BASKETS, CATEGORIES, cat_label
from .wording import adapt as W

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("kori.api")
app = FastAPI(title="Kori", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _lang(lang: str | None) -> str:
    return "fi" if (lang or "").lower().startswith("fi") else "en"


def _money(customer: str, lang: str | None, device: str | None) -> tuple[Money, dict, str]:
    device = (device or "anon")[:64]
    try:
        get_customer(customer)
    except KeyError:
        raise HTTPException(404, f"unknown customer {customer}")
    m, st = S.money(device, customer, _lang(lang))
    return m, st, device


def _persona(m: Money) -> dict:
    lang = m.prefs.lang
    p = S.PERSONA_BY_ID.get(m.customer_id)
    name = p["name"] if p else m.customer_id
    return {"id": m.customer_id, "name": name, "age": m.customer.age, "area": m.customer.area,
            "blurb": p["blurb"][lang] if p else "", "partial_view": m.partial_view}


@app.exception_handler(ValueError)
async def _bad(_, e: ValueError):
    return JSONResponse({"detail": str(e)}, status_code=400)


@app.get("/api/health")
def health():
    return {"ok": True, "today": config.DEMO_TODAY.isoformat(), "model": config.GEMINI_MODEL,
            "gemini": bool(config.gemini_key()), "elevenlabs": bool(config.ELEVENLABS_API_KEY),
            "voice_agent": bool(config.ELEVENLABS_AGENT_ID)}


@app.get("/api/personas")
def personas(lang: str = "en"):
    out = []
    for p in S.PERSONAS:
        m = Money(p["id"], prefs=S.Prefs(lang=_lang(lang)))
        out.append({**_persona(m), "safe": m.safe["amount"], "status": m.safe["status"]})
    return out


SUGGEST = {
    "en": ["How much did I spend on taxis last month?", "What is safe for me to spend this week?", "What kind of spender am I?",
           "How much could I save if I reduced eating out by 20%?", "Where does my money slip through my fingers?",
           "What if my washing machine breaks?"],
    "fi": ["Paljonko käytin takseihin viime kuussa?", "Paljonko voin turvallisesti käyttää tällä viikolla?", "Millainen kuluttaja olen?",
           "Paljonko säästäisin, jos söisin ulkona 20 % vähemmän?", "Mihin rahani valuvat sormien läpi?", "Entä jos pesukoneeni hajoaa?"],
}


def _goal(m: Money) -> dict | None:
    g = m.prefs.goal
    if not g:
        return None
    room = max(0.0, m.usual["left_over"])
    return {"name": g.get("name"), "amount": g.get("amount"), "monthly_room": room,
            "months": round(g["amount"] / room, 1) if room > 0 else None}


@app.get("/api/home")
def home(customer: str, lang: str = "en", x_kori_device: str | None = Header(None)):
    m, st, _ = _money(customer, lang, x_kori_device)
    L = lambda en, fi: en if m.prefs.lang == "en" else fi
    ls = lessons.build(m)
    done = st.get("lessons", {})
    nxt = next((x for x in ls if not done.get(x["id"], {}).get("done")), None)
    prof = persona.profile(m)
    fc = C.forecast_card(m)
    return W(m, {
        "persona": _persona(m), "today": m.today.isoformat(),
        "greeting": L(f"Hi {S.name_of(customer)}", f"Hei {S.name_of(customer)}"),
        "safe": {**m.safe, "cushion": m.cushion}, "forecast": fc["data"], "baskets": m.baskets(),
        "notices": insights.notices(m, 5), "save": m.safe_to_save,
        "profile": {"archetype": prof["archetype"], "fitness": prof["fitness"], "shape": prof["shape"]},
        "suggestions": SUGGEST[m.prefs.lang], "goal": _goal(m),
        "lessons": {"done": sum(1 for x in ls if done.get(x["id"], {}).get("done")), "total": len(ls),
                    "next": {"id": nxt["id"], "title": nxt["title"], "minutes": nxt["minutes"], "concept": nxt["concept"]} if nxt else None},
        "pins": len(st.get("pins", [])),
    })


class CardReq(BaseModel):
    customer: str
    lang: str = "en"
    tool: str
    args: dict = {}


@app.post("/api/card")
def card(req: CardReq, x_kori_device: str | None = Header(None)):
    m, _, _ = _money(req.customer, req.lang, x_kori_device)
    c = C.from_source(m, req.tool, req.args)
    if not c:
        raise HTTPException(400, f"unknown tool {req.tool}")
    return W(m, c)


@app.get("/api/baskets")
def baskets(customer: str, lang: str = "en", month: str | None = None, x_kori_device: str | None = Header(None)):
    m, _, _ = _money(customer, lang, x_kori_device)
    keys = (m.full_months + [m.this_month])[-13:]
    mt = m.monthly
    hist = [{"month": k, "label": month_label(k, m.prefs.lang, long=False), **{b: float(mt.loc[k, b]) for b in BASKETS},
             "income": float(mt.loc[k, "income"]), "spend": float(mt.loc[k, "spend"]), "partial": k == m.this_month}
            for k in keys if k in mt.index]
    cats = [{"category": c, "label": cat_label(c, m.prefs.lang), "icon": v["icon"], "basket": m._basket_of(c),
             "default_basket": v["basket"], "usual": m.usual["categories"][c]} for c, v in CATEGORIES.items()]
    return W(m, {"current": m.baskets(month), "history": hist, "usual": {b: m.usual[b] for b in BASKETS}, "income": m.usual["income"],
            "left_over": m.usual["left_over"], "categories": cats, "slips": insights.slips(m),
            "labels": {b: {"label": BASKETS[b][m.prefs.lang], "short": BASKETS[b]["short_" + m.prefs.lang],
                           "desc": BASKETS[b]["desc_" + m.prefs.lang]} for b in BASKETS}})


@app.get("/api/transactions")
def transactions(customer: str, lang: str = "en", month: str | None = None, category: str | None = None,
                 basket: str | None = None, limit: int = 60, x_kori_device: str | None = Header(None)):
    m, _, _ = _money(customer, lang, x_kori_device)
    d = m.df
    if month:
        d = d[d["month"] == month]
    if category:
        d = d[d["category"] == category]
    if basket:
        d = d[d["basket"] == basket]
    d = d.sort_values("ts", ascending=False).head(max(1, min(300, limit)))
    return [tx_row(r, m.prefs.lang) for r in d.itertuples()]


class WhatIfReq(BaseModel):
    customer: str
    lang: str = "en"
    changes: list[dict] = []
    months: int = 12
    goal_amount: float | None = None
    goal_name: str | None = None


@app.post("/api/whatif")
def whatif(req: WhatIfReq, x_kori_device: str | None = Header(None)):
    m, _, _ = _money(req.customer, req.lang, x_kori_device)
    return W(m, what_if(m, req.changes, req.months, req.goal_amount, req.goal_name))


@app.get("/api/plan")
def plan(customer: str, lang: str = "en", x_kori_device: str | None = Header(None)):
    m, st, _ = _money(customer, lang, x_kori_device)
    cats = [{"key": c, "label": cat_label(c, m.prefs.lang), "icon": v["icon"], "basket": m._basket_of(c),
             "usual": m.usual["categories"][c]} for c, v in CATEGORIES.items() if m.usual["categories"][c] > 0]
    cats.sort(key=lambda x: -x["usual"])
    return {"usual": {"income": m.usual["income"], **{b: m.usual[b] for b in BASKETS}, "saving": m.usual["invested"],
                      "left_over": m.usual["left_over"]},
            "categories": cats, "prefs": st["prefs"], "cushion": m.cushion, "savings_plan": m.savings_plan,
            "goal": _goal(m), "safe": {k: m.safe[k] for k in ("amount", "per_day", "days_to_payday", "status", "usual_per_day")},
            "save": m.safe_to_save, "balance": m.balance}


class PlanReq(BaseModel):
    customer: str
    lang: str = "en"
    cushion: float | None = None
    savings_goal_monthly: float | None = None
    goal: dict | None = None
    clear_goal: bool = False
    basket_overrides: dict[str, str] | None = None


@app.put("/api/plan")
def plan_put(req: PlanReq, x_kori_device: str | None = Header(None)):
    m, st, device = _money(req.customer, req.lang, x_kori_device)
    p = st["prefs"]
    if req.cushion is not None:
        p["cushion"] = max(0.0, req.cushion)
    if req.savings_goal_monthly is not None:
        p["savings_goal_monthly"] = max(0.0, req.savings_goal_monthly)
    if req.goal is not None:
        p["goal"] = {"name": str(req.goal.get("name") or "Goal")[:40], "amount": float(req.goal.get("amount") or 0)}
    if req.clear_goal:
        p["goal"] = None
    if req.basket_overrides is not None:
        p["basket_overrides"] = {k: v for k, v in req.basket_overrides.items() if k in CATEGORIES and v in BASKETS}
    S.save(device, req.customer, st)
    return plan(req.customer, req.lang, x_kori_device)


# ------------------------------------------------------------------ lessons
@app.get("/api/lessons")
def lessons_list(customer: str, lang: str = "en", x_kori_device: str | None = Header(None)):
    m, st, _ = _money(customer, lang, x_kori_device)
    done = st.get("lessons", {})
    return W(m, [{"id": x["id"], "title": x["title"], "concept": x["concept"], "minutes": x["minutes"],
                  "done": bool(done.get(x["id"], {}).get("done")), "slides": len(x["slides"])} for x in lessons.build(m)])


@app.get("/api/lessons/{lesson_id}")
def lesson_get(lesson_id: str, customer: str, lang: str = "en", x_kori_device: str | None = Header(None)):
    m, st, _ = _money(customer, lang, x_kori_device)
    le = lessons.get(m, lesson_id)
    if not le:
        raise HTTPException(404, "lesson not available")
    out = json.loads(json.dumps(le))
    for s in out["slides"]:
        if s.get("card"):
            s["card"] = C.slide_card(m, s["card"])
    out["done"] = bool(st.get("lessons", {}).get(lesson_id, {}).get("done"))
    return W(m, out)


class TeachReq(BaseModel):
    customer: str
    lang: str = "en"
    answer: str


@app.post("/api/lessons/{lesson_id}/teachback")
async def lesson_teachback(lesson_id: str, req: TeachReq, x_kori_device: str | None = Header(None)):
    m, st, device = _money(req.customer, req.lang, x_kori_device)
    le = lessons.get(m, lesson_id)
    if not le:
        raise HTTPException(404, "lesson not available")
    g = await agent.grade_teachback(m.prefs.lang, le, req.answer.strip())
    if g["passed"]:
        st.setdefault("lessons", {})[lesson_id] = {"done": True, "ts": time.time(), "answer": req.answer.strip()[:400]}
        S.save(device, req.customer, st)
    return g


class DoneReq(BaseModel):
    customer: str


@app.post("/api/lessons/{lesson_id}/done")
def lesson_done(lesson_id: str, req: DoneReq, x_kori_device: str | None = Header(None)):
    _, st, device = _money(req.customer, "en", x_kori_device)
    st.setdefault("lessons", {})[lesson_id] = {"done": True, "ts": time.time()}
    S.save(device, req.customer, st)
    return {"ok": True}


# --------------------------------------------------------------------- pins
@app.get("/api/pins")
def pins(customer: str, lang: str = "en", x_kori_device: str | None = Header(None)):
    m, st, _ = _money(customer, lang, x_kori_device)
    out = []
    for p in st.get("pins", []):
        try:
            c = C.from_source(m, p["tool"], p.get("args") or {})
        except Exception:   # noqa: BLE001 - a pin that no longer computes is skipped, not fatal
            c = None
        if c:
            c["pin_id"] = p["id"]
            out.append(c)
    return W(m, out)


class PinReq(BaseModel):
    customer: str
    tool: str
    args: dict = {}


@app.post("/api/pins")
def pin_add(req: PinReq, x_kori_device: str | None = Header(None)):
    m, st, device = _money(req.customer, "en", x_kori_device)
    if not C.from_source(m, req.tool, req.args):
        raise HTTPException(400, "cannot pin this")
    for p in st["pins"]:
        if p["tool"] == req.tool and p.get("args") == req.args:
            return {"id": p["id"], "count": len(st["pins"])}
    pid = S.new_id()
    st["pins"].insert(0, {"id": pid, "tool": req.tool, "args": req.args, "ts": time.time()})
    st["pins"] = st["pins"][:24]
    S.save(device, req.customer, st)
    return {"id": pid, "count": len(st["pins"])}


@app.delete("/api/pins/{pin_id}")
def pin_del(pin_id: str, customer: str, x_kori_device: str | None = Header(None)):
    _, st, device = _money(customer, "en", x_kori_device)
    st["pins"] = [p for p in st["pins"] if p["id"] != pin_id]
    S.save(device, customer, st)
    return {"count": len(st["pins"])}


@app.post("/api/reset")
def reset(req: DoneReq, x_kori_device: str | None = Header(None)):
    S.reset((x_kori_device or "anon")[:64], req.customer)
    return {"ok": True}


# --------------------------------------------------------------------- chat
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ChatReq(BaseModel):
    customer: str
    lang: str = "en"
    session: str | None = None
    text: str
    mode: str = "text"
    turn: str | None = None      # the phone's own id for this question: sending it again resumes, it does not ask twice
    after: int = 0               # how many events of this turn the phone already has


_chat_turns: dict[str, agent.EventLog] = {}     # recent chat turns, so a dropped connection can pick its answer up
_chat_tasks: set[asyncio.Task] = set()


@app.post("/api/chat")
async def chat(req: ChatReq, x_kori_device: str | None = Header(None)):
    """One coach turn as a stream of numbered events (status, cards, the answer, done, end).

    The turn runs to the end whether or not the phone is still listening. If the connection drops mid-answer the
    phone sends the same request again with the turn id and the number of the last event it got, and receives
    the rest: the question is never asked twice and the answer is never lost."""
    m, _, device = _money(req.customer, req.lang, x_kori_device)
    turn_id = (req.turn or uuid.uuid4().hex)[:64]
    key = f"{device}:{turn_id}"
    events = _chat_turns.get(key)
    if events is None:
        sess = agent.session(req.session or uuid.uuid4().hex, device, req.customer, m.prefs.lang)
        events = _chat_turns[key] = agent.EventLog()
        for old in list(_chat_turns)[:-300]:
            _chat_turns.pop(old, None)
        events.put_nowait(("session", {"session": sess.id, "turn": turn_id}))

        async def emit(kind: str, data: dict):
            events.put_nowait((kind, data))

        async def work():
            try:
                await agent.run_turn(sess, req.text.strip()[:1000], "voice" if req.mode == "voice" else "text", emit)
            except Exception as e:   # noqa: BLE001
                log.exception("chat turn failed")
                events.put_nowait(("error", {"message": {"en": "I couldn't reach my thinking engine. Please try again.",
                                                         "fi": "En saanut yhteyttä ajattelumoottoriini. Yritä uudelleen."}[sess.lang],
                                             "detail": str(e)[:200]}))
            finally:
                events.put_nowait(("end", {}))

        task = asyncio.create_task(work())
        _chat_tasks.add(task)
        task.add_done_callback(_chat_tasks.discard)

    async def stream():
        n = max(0, req.after)
        while True:
            got = await events.after(n, 10)
            if not got:
                yield ": keep-alive\n\n"
            for n, kind, data in got:
                yield f"id: {n}\n" + _sse(kind, data)
                if kind == "end":
                    return

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# -------------------------------------------------------------------- voice
@app.get("/api/voice/session")
async def voice_session(customer: str, lang: str = "en", session: str | None = None, transport: str = "webrtc",
                        x_kori_device: str | None = Header(None)):
    m, _, device = _money(customer, lang, x_kori_device)
    if not (config.ELEVENLABS_API_KEY and config.ELEVENLABS_AGENT_ID):
        raise HTTPException(503, "voice agent is not configured")
    sess = agent.session(session or uuid.uuid4().hex, device, customer, m.prefs.lang)
    try:
        tok = await voice.conversation_token(config.ELEVENLABS_AGENT_ID, transport)
    except voice.VoiceBusy as e:       # the app then offers hold-to-talk, which needs no live line
        log.warning("no live voice line: %s", e)
        raise HTTPException(503, "all voice lines are busy") from None
    return {"session": sess.id, "agent_id": config.ELEVENLABS_AGENT_ID, **tok, "first_message": voice.first_message(m),
            "voice_id": voice.VOICES[m.prefs.lang], "language": m.prefs.lang}


@app.get("/api/voice/events")
async def voice_events(session: str, request: Request, last_event_id: str | None = Header(None), since: int | None = None):
    """What the voice screen shows while the coach talks: the user's words, status, cards, the coach's words.

    Every event has a number. A phone that loses the connection for a moment (a lift, a tunnel, wifi to 4G)
    reconnects by itself with the number of the last event it got, and receives everything after it."""
    sess = agent.get_session(session)
    if not sess:
        raise HTTPException(404, "no such session")
    try:
        seen = int(last_event_id) if last_event_id is not None else since
    except ValueError:
        seen = None
    if seen is None or seen > len(sess.queue.items):
        seen = len(sess.queue.items)        # a first connection starts from now

    async def stream():
        n = seen
        yield f"retry: 500\nid: {n}\n" + _sse("ready", {"session": session})
        while not await request.is_disconnected():
            got = await sess.queue.after(n, 10)
            if not got:
                yield ": keep-alive\n\n"
            for n, kind, data in got:
                yield f"id: {n}\n" + _sse(kind, data)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _chunk(cid: str, model: str, delta: dict, finish: str | None = None) -> str:
    return "data: " + json.dumps({"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
                                  "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}, ensure_ascii=False) + "\n\n"


@app.post("/v1/chat/completions")
async def completions(request: Request, authorization: str | None = Header(None)):
    """OpenAI-compatible endpoint that ElevenLabs Agents calls as its "custom LLM".

    ElevenLabs does the listening and the speaking. The thinking happens here: the same Gemini tool loop
    and number check as the text chat. Only the words go back to ElevenLabs; cards go to the phone screen
    through the session's own event stream.
    """
    if (authorization or "").removeprefix("Bearer ").strip() != config.VOICE_LLM_SECRET:
        raise HTTPException(401, "bad key")
    body = await request.json()
    extra = body.get("elevenlabs_extra_body") or {}
    msgs = body.get("messages") or []
    user_text = next((x.get("content") for x in reversed(msgs) if x.get("role") == "user" and x.get("content")), "") or ""
    if isinstance(user_text, list):
        user_text = " ".join(p.get("text", "") for p in user_text if isinstance(p, dict))
    sid = str(extra.get("session") or body.get("user_id") or "voice-default")
    sess = agent.get_session(sid) or agent.session(sid, "voice", str(extra.get("customer") or S.PERSONAS[0]["id"]), _lang(extra.get("lang")))
    model = body.get("model") or "kori"
    cid = "chatcmpl-" + uuid.uuid4().hex[:12]
    q: asyncio.Queue = asyncio.Queue()

    # Speak within a second: if this sounds like a question about money, say a short "let me look" right away,
    # while the model picks its calculation. Greetings and thanks get no filler.
    early = T.early_filler(user_text, sess.lang, len(sess.turns))
    if isinstance(extra.get("filler"), str):          # test hook: try other buffer words without a deploy
        early = extra["filler"][:140] or None

    async def emit(kind: str, data: dict):
        if kind == "text":
            await q.put(("text", data["text"]))
            await sess.queue.put(("coach", {"text": data["text"]}))
        elif kind == "status":
            if data.get("first") and not early:
                filler = T.VOICE_FILLER.get(data["tool"])
                if filler:
                    await q.put(("text", filler[0 if sess.lang == "en" else 1]))
            await sess.queue.put((kind, data))
        else:
            await sess.queue.put((kind, data))

    # One question, one answer. If ElevenLabs calls again while we are still working (its own retry, or the user
    # spoke over the coach), the old turn stops; a repeat of the same words does not show up twice on screen.
    if sess.voice_task and not sess.voice_task.done():
        sess.voice_task.cancel()
    repeat = sess.voice_last[0] == user_text and time.time() - sess.voice_last[1] < 20
    sess.voice_last = (user_text, time.time())

    hold = float(extra.get("hold") or 0) if isinstance(extra.get("filler"), str) else 0.0   # test hook: a slow model

    async def work():
        try:
            if hold:
                await asyncio.sleep(min(hold, 12))
            if not repeat:
                await sess.queue.put(("user", {"text": user_text}))
            await agent.run_turn(sess, user_text.strip()[:1000] or "Hello", "voice", emit)
        except Exception:   # noqa: BLE001
            log.exception("voice turn failed")
            await q.put(("text", {"en": "Sorry, I lost the connection for a moment. Could you say that again?",
                                  "fi": "Anteeksi, yhteys katkesi hetkeksi. Sanoisitko uudelleen?"}[sess.lang]))
        finally:
            q.put_nowait((None, None))      # also when cancelled, so the stream that waits on it ends

    async def stream():
        task = sess.voice_task = asyncio.create_task(work())
        try:
            # the first chunk carries the buffer words themselves, long enough for ElevenLabs to start speaking at once
            yield _chunk(cid, model, {"role": "assistant", "content": early or ""})
            while True:
                kind, data = await q.get()
                if kind is None:
                    break
                yield _chunk(cid, model, {"content": data})
            yield _chunk(cid, model, {}, "stop")
            yield "data: [DONE]\n\n"
            await task
        finally:
            if not task.done():      # ElevenLabs hung up (the user interrupted): stop thinking about the old question
                task.cancel()

    if body.get("stream", True):
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    task = sess.voice_task = asyncio.create_task(work())
    parts = [early] if early else []
    while True:
        kind, data = await q.get()
        if kind is None:
            break
        parts.append(data)
    await task
    return {"id": cid, "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "".join(parts)}, "finish_reason": "stop"}]}


@app.get("/api/minute")
async def minute(customer: str, lang: str = "en", x_kori_device: str | None = Header(None)):
    m, _, _ = _money(customer, lang, x_kori_device)
    return await voice.minute(m)


@app.get("/api/audio/{name}")
def audio(name: str):
    p = config.AUDIO_DIR / name
    if "/" in name or ".." in name or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})


class TtsReq(BaseModel):
    text: str
    lang: str = "en"


@app.post("/api/tts")
async def tts(req: TtsReq):
    if not config.ELEVENLABS_API_KEY:
        raise HTTPException(503, "speech is not configured")
    try:
        return Response(await voice.tts_cached(req.text[:900], _lang(req.lang)), media_type="audio/mpeg")
    except Exception as e:   # noqa: BLE001 - out of credits or ElevenLabs down: the app shows the words instead
        log.warning("tts failed: %s", e)
        raise HTTPException(503, "speech is not available right now") from None


@app.post("/api/stt")
async def stt(file: UploadFile = File(...), lang: str = Form("en")):
    if not config.ELEVENLABS_API_KEY:
        raise HTTPException(503, "speech is not configured")
    data = await file.read()
    if len(data) > 8_000_000:
        raise HTTPException(413, "recording too long")
    try:
        return {"text": await voice.stt(data, file.filename or "speech.webm", _lang(lang))}
    except Exception as e:   # noqa: BLE001
        log.warning("stt failed: %s", e)
        raise HTTPException(503, "speech is not available right now") from None


# ---------------------------------------------------------------- static app
if config.WEB_DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=config.WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = config.WEB_DIST / path
        if path and f.is_file() and config.WEB_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(config.WEB_DIST / "index.html", headers={"Cache-Control": "no-cache"})
