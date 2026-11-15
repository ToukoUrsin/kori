"""HTTP for the chat: the stream, the locked frame, the picture proxy."""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import time
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from .. import config, state as S
from ..engine.core import Money
from . import door

log = logging.getLogger("kori.lab")
router = APIRouter()
DEV = os.environ.get("KORI_LAB_DEV") == "1"

CSP = ("default-src 'none'; script-src 'unsafe-inline' 'self' {o}; style-src 'unsafe-inline' 'self' {o}; "
       "img-src 'self' {o} data: blob:; font-src 'self' {o} data:; media-src 'self' {o} blob:; connect-src 'none'; "
       "frame-src 'none'; form-action 'none'; base-uri {o}")


def _lab_dir() -> Path:
    """The frame runtime: straight from the source tree on a developer machine, from the built app when deployed."""
    src = config.ROOT / "web" / "public" / "lab"
    return src if src.is_dir() else config.WEB_DIST / "lab"


def _origin(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{proto}://{host}"


@router.get("/api/lab/frame")
def frame(request: Request):
    """The document every generated view runs in. Its policy allows no connection of any kind and no remote content;
    the iframe itself is sandboxed by the page that embeds it (scripts only, an opaque origin)."""
    f = _lab_dir() / "frame.html"
    if not f.is_file():
        raise HTTPException(404, "the frame runtime is not built yet")
    o = _origin(request)
    html = f.read_text()
    base = f'<base href="{o}/lab/">'
    html = html.replace("<head>", "<head>" + base, 1) if "<head>" in html else base + html
    return HTMLResponse(html, headers={"Content-Security-Policy": CSP.format(o=o), "Cache-Control": "no-cache",
                                       "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})


@router.get("/lab/{path:path}")
def lab_static(path: str):
    """The runtime's own files (script, styles, vendored libraries). Public and static, so any origin may load them:
    the frame's origin is opaque by design."""
    root = _lab_dir()
    f = (root / path).resolve()
    if path and f.is_file() and root.resolve() in f.parents:
        return FileResponse(f, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache" if DEV else "public, max-age=300"})
    return FileResponse(config.WEB_DIST / "index.html", headers={"Cache-Control": "no-cache"})


_IMG_DIR = config.STATE_DIR / "lab_img_v2"     # v1 kept the shops' originals, megabytes for a thumbnail
_IMG_EDGE = 480                                # the longest side a view ever shows, at phone density


def small(body: bytes, ctype: str) -> tuple[bytes, str]:
    """A shop's picture cut to what a phone shows: a 3000 px original becomes a few kilobytes. Anything that cannot be
    read as a picture (or is small already) passes through untouched."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(body))
        if max(im.size) <= _IMG_EDGE and len(body) <= 60_000:
            return body, ctype
        im.thumbnail((_IMG_EDGE, _IMG_EDGE))
        alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
        out = io.BytesIO()
        im.convert("RGBA" if alpha else "RGB").save(out, "WEBP", quality=82, method=4)
        return out.getvalue(), "image/webp"
    except Exception:   # noqa: BLE001 - an odd file is still better shown than dropped
        return body, ctype
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"


@router.get("/api/lab/img")
def img(k: str | None = None, u: str | None = None):
    """Pictures for generated views. Only a picture that a logged shop or web call returned can be asked for (by its key);
    the view never talks to the remote host and the remote host never sees the customer."""
    url = door.image_url(k) if k else None
    if not url and u and DEV and u.startswith("https://"):
        url, k = u, hashlib.sha1(u.encode()).hexdigest()[:20]
    if not url:
        raise HTTPException(404, "unknown picture")
    _IMG_DIR.mkdir(parents=True, exist_ok=True)
    body_f, type_f = _IMG_DIR / k, _IMG_DIR / f"{k}.type"
    if not body_f.is_file():
        try:
            with httpx.Client(timeout=8, follow_redirects=True, headers={"User-Agent": _UA, "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"}) as c:
                r = c.get(url)
            ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
            if r.status_code != 200 or not ctype.startswith("image/") or len(r.content) > 5_000_000:
                raise HTTPException(502, "the picture could not be loaded")
            body, ctype = small(r.content, ctype)
            body_f.write_bytes(body)
            type_f.write_text(ctype)
        except httpx.HTTPError as e:
            raise HTTPException(502, "the picture could not be loaded") from e
    return Response(body_f.read_bytes(), media_type=type_f.read_text() if type_f.is_file() else "image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*",
                             "Cross-Origin-Resource-Policy": "cross-origin"})


# ------------------------------------------------------------------- chat
class LabReq(BaseModel):
    customer: str
    lang: str = "en"
    session: str | None = None
    message: str
    turn: str | None = None
    after: int = 0
    fresh: bool = False          # build the view new, even for a question that has a kept one
    approved: bool = False       # the bank's switch: only answers whose code was reviewed, no model in the turn


class ResetReq(BaseModel):
    session: str


def _sse(n: int, event: str, data: dict) -> str:
    return f"id: {n}\nevent: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


_tasks: set[asyncio.Task] = set()


def _keep(sess, turn) -> None:
    """Every finished turn goes on disk as one line: the question, each cell and what it printed, the ledger, the answer
    and the view as written. A view's pieces are joined, so a line stays readable."""
    try:
        events, html, code = [], {}, {}
        for kind, data in turn.events.items:
            if kind == "run_code":
                code[data.get("id")] = code.get(data.get("id"), "") + (data.get("delta") or "")
            if kind in ("end", "run_code", "text"):
                continue
            if kind == "run_done" and code.get(data.get("id")):
                data = {**data, "code": code[data.get("id")]}
            if kind == "ui" and data.get("phase") == "delta":
                html[data.get("id")] = html.get(data.get("id"), "") + (data.get("html") or "")
                continue
            if kind == "ui" and data.get("phase") == "done":
                data = {**data, "html": html.get(data.get("id"), "")}
            events.append([kind, data])
        text = "".join(d.get("delta") or "" for k, d in turn.events.items if k == "text")
        line = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "session": sess.id, "turn": turn.id, "customer": sess.customer_id,
                "lang": sess.lang, "message": turn.message, "answer": text, "events": events}
        f = config.STATE_DIR / "lab_turns.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a") as out:
            out.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")
    except Exception:   # noqa: BLE001 - the record never breaks a turn
        log.exception("could not keep the turn")


@router.post("/api/lab/chat")
async def chat(req: LabReq, x_kori_device: str | None = Header(None)):
    """One turn as a stream of events (docs/LAB.md). The turn runs to its end even if the phone stops listening;
    sending the same `turn` id again with `after` picks the stream up where it broke."""
    from . import agent
    lang = "fi" if (req.lang or "en").lower().startswith("fi") else "en"
    if req.customer not in S.PERSONA_BY_ID:
        raise HTTPException(404, "unknown customer")
    device = (x_kori_device or "anon")[:64]
    sess = agent.session(req.session or uuid.uuid4().hex, device, req.customer, lang)
    turn = sess.turn(req.turn) if req.turn else None
    if turn is None:
        turn = sess.new_turn(req.message.strip()[:1500], req.turn)
        turn.fresh = bool(req.fresh) and not req.approved
        turn.approved = bool(req.approved)

        async def work():
            try:
                await agent.run_turn(sess, turn)
            except Exception as e:   # noqa: BLE001
                log.exception("lab turn failed")
                turn.emit("error", {"message": {"en": "Something broke on my side. Ask again and I will start over.",
                                                "fi": "Jokin meni pieleen minun päässäni. Kysy uudelleen, niin aloitan alusta."}[lang],
                                    "detail": f"{type(e).__name__}: {e}"[:300]})
            finally:
                turn.emit("end", {})
                _keep(sess, turn)

        t = asyncio.create_task(work())
        _tasks.add(t)
        t.add_done_callback(_tasks.discard)

    async def stream():
        n = max(0, req.after)
        if n == 0:
            yield _sse(0, "session", {"session": sess.id, "turn": turn.id})
        while True:
            got = await turn.events.after(n, 2)
            if not got:
                yield ": keep-alive\n\n"
            for n, kind, data in got:
                if kind == "end":
                    return
                yield _sse(n, kind, data)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class WarmReq(BaseModel):
    customer: str
    lang: str = "en"
    session: str


@router.post("/api/lab/warm")
async def warm(req: WarmReq, x_kori_device: str | None = Header(None)):
    """The chat just opened: start this session's sandbox now, so the first question does not wait for it."""
    from . import agent
    if req.customer not in S.PERSONA_BY_ID:
        raise HTTPException(404, "unknown customer")
    lang = "fi" if (req.lang or "en").lower().startswith("fi") else "en"
    device = (x_kori_device or "anon")[:64]
    sess = agent.session(req.session[:64], device, req.customer, lang)
    t = asyncio.create_task(agent._warm(sess, S.money(device, req.customer, lang)[0]))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return {"ok": True}


@router.get("/api/lab/session")
def session_get(session: str):
    from . import agent
    s = agent.get_session(session)
    if not s:
        return {"session": session, "turns": []}
    return {"session": s.id, "customer": s.customer_id, "lang": s.lang,
            "turns": [{"id": t.id, "message": t.message, "events": [{"event": k, "data": d} for k, d in t.events.items if k != "end"]}
                      for t in s.turns]}


@router.post("/api/lab/reset")
async def session_reset(req: ResetReq):
    from . import agent
    await agent.forget(req.session)
    return {"ok": True}


_STARTERS: dict[tuple[str, str, bool, bool], tuple[float, dict]] = {}     # the same for every visitor: worked out once


@router.get("/api/lab/starters")
def starters(customer: str, lang: str = "en"):
    from . import agent
    from .door import products_ready
    lang = "fi" if lang.lower().startswith("fi") else "en"
    if customer not in S.PERSONA_BY_ID:
        raise HTTPException(404, "unknown customer")
    key = (customer, lang, products_ready("shop"), products_ready("web"))      # the list changes once the shop shelves are in
    hit = _STARTERS.get(key)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    out = {"items": agent.starters(S.money("starters", customer, lang)[0])}
    _STARTERS[key] = (time.time(), out)
    return out


@router.get("/api/lab/approved")
def lab_approved(lang: str = "en"):
    """The bank's own list: every question with reviewed code, when it was approved and where the code is."""
    from . import kept
    return {"items": kept.approved("fi" if lang == "fi" else "en")}


@router.get("/api/lab/health")
def health():
    from . import kernel
    try:
        from . import designer
        ui = designer.model_used()
    except Exception:   # noqa: BLE001
        ui = None
    return {"isolation": kernel.isolation(), "analyst": config.GEMINI_MODEL, "modeller": config.GEMINI_MODEL_BACKGROUND,
            "designer": ui or config.UI_MODEL, "claude": bool(config.anthropic_key())}
