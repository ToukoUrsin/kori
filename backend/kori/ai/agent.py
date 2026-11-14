"""The coach loop: Gemini picks tools, the engine computes, the answer is number-checked.

One turn = user text in, a stream of events out:
  status  {tool, label}            a tool started
  card    {card}                   a card for the screen
  effect  {type, ...}              plan changed / open a lesson
  text    {text}                   the final, checked answer
  done    {grounded, flagged, followups, tools, ms}
"""
from __future__ import annotations

import asyncio
import re
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from google import genai
from google.genai import types

from .. import config, state as S
from ..engine.core import Money
from . import grounding, prompts, tools as T
from ..wording import adapt, is_pensioner

log = logging.getLogger("kori.agent")
Emit = Callable[[str, dict], Awaitable[None]]

MAX_STEPS = 6
MAX_HISTORY_TURNS = 12
CARRY_TURNS = 3            # a follow-up may repeat figures from this many earlier turns' calculations

_clients: dict[str, genai.Client] = {}


def client(key: str | None = None) -> genai.Client:
    key = key or config.gemini_key()
    if not key:
        raise RuntimeError("no Gemini API key (JUNCTION_GEMINI_API_KEY or GEMINI_API_KEY)")
    if key not in _clients:
        _clients[key] = genai.Client(api_key=key)
    return _clients[key]


TOOLS = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=d["name"], description=d["description"], parameters_json_schema=d["parameters"])
    for d in T.DECLARATIONS])]


class EventLog:
    """Everything the voice screen should show, in order. Readers never take events away, so a phone whose
    connection drops for a second gets what it missed when it comes back."""

    def __init__(self):
        self.items: list[tuple[str, dict]] = []
        self._new = asyncio.Event()

    def put_nowait(self, item: tuple[str, dict]):
        self.items.append(item)
        waiting, self._new = self._new, asyncio.Event()
        waiting.set()

    async def put(self, item: tuple[str, dict]):
        self.put_nowait(item)

    async def after(self, n: int, timeout: float) -> list[tuple[int, str, dict]]:
        """Events number n+1 onwards as (number, kind, data); waits up to `timeout` seconds for the first."""
        if len(self.items) <= n:
            try:
                await asyncio.wait_for(self._new.wait(), timeout)
            except asyncio.TimeoutError:
                return []
        return [(i + 1, *self.items[i]) for i in range(n, len(self.items))]


@dataclass
class Session:
    id: str
    device: str
    customer_id: str
    lang: str = "en"
    turns: list[list] = field(default_factory=list)      # each turn = list of Content (user, model, tool legs)
    queue: EventLog = field(default_factory=EventLog)    # events for the voice screen
    used: float = field(default_factory=time.time)
    log: list[dict] = field(default_factory=list)        # plain transcript for the UI
    voice_task: asyncio.Task | None = None                # the voice turn being worked on, if any
    voice_last: tuple = ("", 0.0)                         # (what the user said, when) for the last voice turn
    recent: list[list[dict]] = field(default_factory=list)  # per turn: [{tool, result}], what the model still has in view

    def history(self) -> list:
        out = []
        for t in self.turns[-MAX_HISTORY_TURNS:]:
            out.extend(t)
        return out


_sessions: dict[str, Session] = {}


def session(sid: str, device: str, customer_id: str, lang: str = "en") -> Session:
    s = _sessions.get(sid)
    if not s or s.customer_id != customer_id:
        s = Session(sid, device, customer_id, lang)
        _sessions[sid] = s
        if len(_sessions) > 2000:
            for k in sorted(_sessions, key=lambda k: _sessions[k].used)[:500]:
                _sessions.pop(k, None)
    s.lang = lang
    s.used = time.time()
    return s


OPENING_NOTE = "[The user opened the voice coach."


def seed_opening(sess: Session, m: Money, st: dict, spoken: str) -> list[dict]:
    """The coach spoke first and asked the one question. Remember it, with the calculation behind it, so that a
    spoken answer ("it was unusual") sets the thing without asking again. Returns the cards that go with the line."""
    out = T.execute(m, st, "check_in", {"part": "both"})
    note = (OPENING_NOTE + " Kori spoke first: it said what it noticed and asked the one question from check_in. The check_in "
            "result was: " + json.dumps(out.result, ensure_ascii=False, default=str) + " If the user's next words answer that "
            "question, call set_action at once as how_to_offer says, then say it is set. If they ask something else, answer that.]")
    turn = [types.Content(role="user", parts=[types.Part(text=note)]), types.Content(role="model", parts=[types.Part(text=spoken)])]
    if sess.turns and sess.turns[-1][0].parts and (sess.turns[-1][0].parts[0].text or "").startswith(OPENING_NOTE):
        sess.turns.pop()            # voice opened twice in a row: one opening, not two
        if sess.recent:
            sess.recent.pop()
    sess.turns.append(turn)
    sess.recent = sess.recent[-CARRY_TURNS:] + [[{"tool": "check_in", "result": out.result}]]
    return out.cards


def get_session(sid: str) -> Session | None:
    return _sessions.get(sid)


def _config(m: Money, mode: str, action: dict | None = None) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=prompts.system_prompt(m, mode, action), tools=TOOLS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level="low"))


WITHHELD = {
    "en": ("I wrote an answer, but one figure in it did not match your account, so I am not showing it. "
           "The exact numbers are on the card.",
           "I wrote an answer, but one figure in it did not match your account, so I am not showing it. "
           "Ask me again and I will work it out from scratch."),
    "fi": ("Kirjoitin vastauksen, mutta yksi sen luvuista ei täsmännyt tilisi tietoihin, joten en näytä sitä. "
           "Tarkat luvut ovat kortissa.",
           "Kirjoitin vastauksen, mutta yksi sen luvuista ei täsmännyt tilisi tietoihin, joten en näytä sitä. "
           "Kysy uudelleen, niin lasken sen alusta."),
}

_CREDIT_WORDS = re.compile(r"\b(loan|credit|pay[- ]?later|installment|consumer loan|investment|stock|fund)s?\b|\b(luotto|kulutusluotto|osamaksu|luottokortti|sijoit|osake|rahasto)", re.I)
_BAD_TONE = {
    "en": re.compile(r"\b(comfortable|plenty|room|breathing room|more room)\b", re.I),
    "fi": re.compile(r"\b(mukavasti|paljon liikkumavaraa|enemmän liikkumavaraa|reilusti tilaa|hyvin varaa|tilaa)\b", re.I),
}


def credit_boundary(text: str, lang: str) -> str | None:
    """A fixed boundary keeps model wording from becoming credit or investment advice."""
    if not _CREDIT_WORDS.search(text or ""):
        return None
    return ({"en": "I cannot recommend for or against loans, credit cards, pay-later products or investments. I can show what a monthly payment would do to your safe-to-spend number in a simple scenario.",
             "fi": "En voi suositella lainaa, luottokorttia, osamaksua tai sijoitusta enkä niitä vastaan. Voin näyttää yksinkertaisella laskelmalla, miten tietty kuukausierä muuttaisi turvallista käyttövaraasi."}[lang])


def tone_violations(text: str, status: str, lang: str) -> list[str]:
    if status not in ("tight", "very_tight", "empty"):
        return []
    return _BAD_TONE["fi" if lang == "fi" else "en"].findall(text or "")


FAST_FIRST = True                # let the small model choose the calculation
HEDGE = (0.0, 4.5, 9.0)          # seconds after which the 1st, 2nd and 3rd attempt of a model call start
HEDGE_FAST = (0.0, 2.5, 6.0)     # the same for the quick first step


async def _generate(contents: list, cfg: types.GenerateContentConfig, fast: bool = False):
    """One model call that does not hang on a slow one.

    The main model usually answers in two or three seconds and now and then takes ten. So if it is still silent
    after a few seconds the small fast model starts beside it, and later one more attempt on the other key. The
    first good answer wins and the rest are dropped. A failed attempt starts the next one at once.

    fast=True is the first step of a turn, choosing which calculation to run: the small model does that in about
    a second, and the main model is the one that steps in if it is slow.
    """
    main, quick, other = config.GEMINI_MODEL, config.GEMINI_MODEL_FAST, config.gemini_fallback_key() or config.gemini_key()
    if fast:
        attempts, delays = [(config.gemini_key(), quick), (config.gemini_key(), main), (other, main)], HEDGE_FAST
    else:
        attempts, delays = [(config.gemini_key(), main), (config.gemini_key(), quick), (other, main)], HEDGE

    async def one(i: int):
        key, model = attempts[i]
        try:
            return await asyncio.wait_for(client(key).aio.models.generate_content(model=model, contents=contents, config=cfg), 40)
        except Exception as e:      # noqa: BLE001 - any provider error moves on to the next attempt
            log.warning("gemini attempt %s (%s) failed: %s", i, model, str(e)[:200])
            raise

    start, started, pending, last = time.time(), 0, set(), None
    try:
        while True:
            while started < len(attempts) and (not pending or time.time() - start >= delays[started]):
                if started:
                    log.info("gemini attempt %s (%s) starts after %.1fs", started, attempts[started][1], time.time() - start)
                pending.add(asyncio.create_task(one(started)))
                started += 1
            wait = max(0.05, delays[started] - (time.time() - start)) if started < len(attempts) else None
            done, pending = await asyncio.wait(pending, timeout=wait, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                if t.exception() is None:
                    return t.result()
                last = t.exception()
            if not pending and started >= len(attempts):
                raise last
    finally:
        for t in pending:
            t.cancel()


def _text_of(content) -> str:
    return "".join(p.text for p in (content.parts or []) if p.text and not p.thought).strip()


def _plain(text: str) -> str:
    """House style the model sometimes forgets: no dashes between clauses."""
    return re.sub(r"\s*[—–]\s*(?=\D)", ", ", text)


async def run_turn(sess: Session, text: str, mode: str, emit: Emit) -> dict:
    """Run one user turn. Returns {"text", "cards", "grounded", "flagged", "tools"}."""
    t0 = time.time()
    st = S.load(sess.device, sess.customer_id)
    m = Money(sess.customer_id, prefs=S.prefs_of(st, sess.lang))
    if is_pensioner(m.customer.age):       # words on screen and in speech say pension, not pay
        raw_emit = emit

        async def emit(kind: str, data: dict):
            await raw_emit(kind, adapt(m, data))
    cfg = _config(m, mode, st.get("action"))
    turn: list = [types.Content(role="user", parts=[types.Part(text=text)])]
    allowed: set[float] = grounding.collect(text)
    # A follow-up may repeat a figure the engine computed a turn or two ago: the model still has that result in view,
    # so it counts as checked. Results from before the plan or the one thing changed are dropped (see below).
    earlier = [x for t in sess.recent[-CARRY_TURNS:] for x in t]
    for x in earlier:
        grounding.collect(x["result"], allowed)
    changed = False
    used: list[str] = []
    cards: list[dict] = []
    results: list[dict] = []
    final = ""
    final_content = None
    retried = False
    failed = False          # the model gave nothing twice: the screen offers "try again" instead of an answer
    flagged: list[str] = []

    for step in range(MAX_STEPS + 2):
        content = None
        for _ in range(2):                              # an empty reply from the model gets one more try
            resp = await _generate(sess.history() + turn, cfg, fast=step == 0 and FAST_FIRST)
            cand = resp.candidates[0] if resp.candidates else None
            content = cand.content if cand and cand.content and cand.content.parts else None
            if content is not None:
                break
            log.warning("gemini returned nothing (%s)", getattr(cand, "finish_reason", None))
        if content is None:
            failed = True
            final = {"en": "Sorry, I lost my thread there. Could you ask that again?",
                     "fi": "Anteeksi, ajatukseni katkesi. Kysyisitkö uudelleen?"}[sess.lang]
            break
        calls = [p.function_call for p in content.parts if p.function_call]
        if calls and step < MAX_STEPS:
            turn.append(content)                       # untouched: carries the thought signature
            responses = []
            for fc in calls:
                name, args = fc.name, dict(fc.args or {})
                label = T.STATUS.get(name, ("Thinking", "Mietin"))[0 if sess.lang == "en" else 1]
                await emit("status", {"tool": name, "label": label, "first": not used})
                try:
                    out = T.execute(m, st, name, args, allowed=allowed)
                except Exception as e:   # noqa: BLE001 - the model gets the error and can fix its arguments
                    log.info("tool %s%s failed: %s", name, args, e)
                    out = T.ToolOut({"error": str(e)[:400]})
                used.append(name)
                results.append(out.result)
                grounding.collect(out.result, allowed)
                for c in out.cards:
                    cards.append(c)
                    await emit("card", {"card": c})
                for e in out.effects:
                    if e["type"] == "plan_changed":
                        changed = True
                        S.save(sess.device, sess.customer_id, st)
                        m = Money(sess.customer_id, prefs=S.prefs_of(st, sess.lang))
                        cfg = _config(m, mode, st.get("action"))
                        fresh = T.execute(m, st, "safe_to_spend", {})
                        out.result["safe_to_spend_now"] = {k: fresh.result[k] for k in ("amount", "per_day", "days_to_payday", "status")}
                        grounding.collect(out.result, allowed)
                        cards.append(fresh.cards[0])
                        await emit("card", {"card": fresh.cards[0]})
                    elif e["type"] in ("action_set", "action_cleared"):
                        changed = True
                        S.save(sess.device, sess.customer_id, st)
                        m = Money(sess.customer_id, prefs=S.prefs_of(st, sess.lang))
                        cfg = _config(m, mode, st.get("action"))
                    await emit("effect", e)
                responses.append(types.Part(function_response=types.FunctionResponse(id=fc.id, name=name, response={"result": out.result})))
            turn.append(types.Content(role="user", parts=responses))
            continue
        final = _plain(_text_of(content))
        final_content = content
        flagged = grounding.check(final, allowed, sess.lang) if used or any(ch.isdigit() for ch in final) else []
        flagged += [f"tone:{x}" for x in tone_violations(final, m.safe["status"], sess.lang)]
        if flagged and not retried:
            retried = True
            log.info("ungrounded numbers %s in: %s", flagged, final[:200])
            tone = [x.removeprefix("tone:") for x in flagged if x.startswith("tone:")]
            reason = ("Do not use comfortable, plenty, room or similar reassuring language for this tight status. State the constraint plainly."
                      if tone else
                      "These figures are not in any tool result: " + ", ".join(flagged) + ". Use only numbers that appear in the tool results.")
            turn_probe = [content, types.Content(role="user", parts=[types.Part(text=(
                "[automatic answer check] " + reason + " Call a tool if you need another number. Reply with the corrected answer only, in the same language."))])]
            turn.extend(turn_probe)
            continue
        break

    boundary = credit_boundary(text, sess.lang)
    if boundary:
        final = boundary
        final_content = types.Content(role="model", parts=[types.Part(text=final)])
        flagged = []
        retried = False
    withheld = bool(flagged)
    if withheld:
        # Second failure: the draft is not shown at all. The cards carry the engine's own figures.
        log.warning("answer withheld, ungrounded numbers %s in: %s", flagged, final[:200])
        final = WITHHELD[sess.lang][0 if cards else 1]
        final_content = types.Content(role="model", parts=[types.Part(text=final)])

    if retried and final_content is not None:
        # keep the history clean: drop the rejected draft and the check message
        idx = next((i for i, c in enumerate(turn) if c.role == "user" and c.parts and c.parts[0].text
                    and c.parts[0].text.startswith("[automatic answer check]")), None)
        if idx is not None:
            turn = turn[:idx - 1] + turn[idx + 1:]
    if final_content is not None and (not turn or turn[-1] is not final_content):
        turn.append(final_content)
    elif final_content is None:
        turn.append(types.Content(role="model", parts=[types.Part(text=final)]))
    sess.turns.append(turn)
    mine = [{"tool": t, "result": r} for t, r in zip(used, results)]
    sess.recent = ([] if changed else sess.recent[-CARRY_TURNS:]) + [mine]
    sess.log.append({"role": "user", "text": text})
    sess.log.append({"role": "coach", "text": final, "cards": [c["id"] for c in cards]})
    await emit("text", {"text": final})
    consistency = grounding.consistency_issues(results)
    done = {"grounded": not flagged, "flagged": flagged, "withheld": withheld, "error": failed,
            "checked": len(grounding.numbers_in_text(final, sess.lang)),
            "followups": T.followups(used, sess.lang), "tools": used, "ms": int((time.time() - t0) * 1000),
            "consistency": consistency,
            "figures": grounding.figures(final, mine + earlier, sess.lang)}
    await emit("done", done)
    return {"text": final, "cards": cards, **done}


async def grade_teachback(lang: str, lesson: dict, answer: str) -> dict:
    """Say-it-back check. Falls back to a keyword check if the model is unavailable."""
    prompt = prompts.TEACHBACK.format(title=lesson["title"], concept=lesson["concept"], prompt=lesson["teach_back"]["prompt"],
                                      rubric="\n".join("- " + r for r in lesson["teach_back"]["rubric"]),
                                      answer=answer.replace('"', "'")[:800], language="Finnish" if lang == "fi" else "English")
    schema = {"type": "object", "properties": {"passed": {"type": "boolean"}, "got": {"type": "string"},
                                               "missing": {"type": "string"}, "encouragement": {"type": "string"}},
              "required": ["passed", "got", "missing", "encouragement"]}
    cfg = types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema,
                                      thinking_config=types.ThinkingConfig(thinking_level="low"))
    try:
        resp = await _generate([types.Content(role="user", parts=[types.Part(text=prompt)])], cfg)
        out = json.loads(resp.text)
        result = {"passed": bool(out.get("passed")), "got": out.get("got", ""), "missing": out.get("missing", ""),
                  "encouragement": out.get("encouragement", ""), "by": "gemini"}
    except Exception as e:   # noqa: BLE001
        log.warning("teachback grading failed: %s", e)
        ok = len(answer.split()) >= 6
        result = {"passed": ok, "got": {"en": "Thanks for putting it in your own words.", "fi": "Kiitos, että sanoit sen omin sanoin."}[lang],
                  "missing": "" if ok else {"en": "Try a full sentence about the main idea.", "fi": "Kokeile kokonaista lausetta pääajatuksesta."}[lang],
                  "encouragement": "", "by": "fallback"}
    # The model's generous boolean is useful copy, but completion is gated by
    # a small deterministic concept check so the exact misconception cannot pass.
    text = (answer or "").lower()
    concept = lesson.get("id", "")
    groups = {
        "baskets": ([("fixed", "kiinte"), ("surprise", "ylläty"), ("everyday", "arki")], ("steer", "ohja", "control")),
        "safe": ([("bill", "lask", "rent", "vuokr", "reserve", "vara")], ("safe", "turvall", "budget", "budjet")),
        "surprise": ([("irregular", "epäsäänn", "unpredict", "arvaam")], ("reserve", "vara", "set aside", "sivuun")),
        "slips": ([("small", "pien", "tiny")], ("add", "sum", "year", "vuod")),
        "paycycle": ([("payday", "palkkapäiv", "income", "tulo")], ("before", "ennen", "rent", "asum")),
        "buffer": ([("month", "kuukaus")], ("must", "pakoll", "essential")),
        "payfirst": ([("payday", "palkkapäiv", "first", "ensin")], ("save", "sääst", "siir")),
        "whatif": ([("month", "kuukaus")], ("year", "vuod", "annual")),
    }
    req = groups.get(concept)
    if req:
        a, b = req
        has_a = all(any(k in text for k in group) for group in a)
        has_b = any(k in text for k in b)
        misconception = concept == "safe" and any(x in text for x in ("balance is what i can spend", "saldo on se mitä voin käyttää", "katson vain saldon"))
        if misconception:
            has_a = has_b = False
        grade = "got_it" if has_a and has_b and len(text.split()) >= 4 else "partly" if (has_a or has_b) and len(text.split()) >= 3 else "not_yet"
        result["passed"] = grade == "got_it"
        result["grade"] = grade
        if grade != "got_it":
            result["missing"] = {"en": "Mention the money already set aside and why the number lasts until payday.",
                                  "fi": "Mainitse jo varatut rahat ja miksi luku kestää palkkapäivään asti."}[lang] if concept == "safe" else result.get("missing") or {"en": "Add the main idea in one clear sentence.", "fi": "Lisää pääajatus yhteen selkeään lauseeseen."}[lang]
            result["hint"] = {"en": "Try again using the lesson's own words.", "fi": "Yritä uudelleen oppitunnin omilla sanoilla."}[lang]
        else:
            result["hint"] = ""
    else:
        result["grade"] = "got_it" if result["passed"] else "not_yet"
        result["hint"] = "" if result["passed"] else {"en": "Try again with the main idea.", "fi": "Yritä uudelleen pääajatuksella."}[lang]
    return result
