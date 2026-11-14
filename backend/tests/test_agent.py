"""The tool loop with a scripted model: what reaches the user when the model gets a number wrong."""
import asyncio
import time

import pytest
from google.genai import types

from kori.ai import agent

HERO = "CUST00092"


def _reply(*parts):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))])


def _run(monkeypatch, script, question="What is safe for me to spend this week?", lang="en"):
    """script: list of model replies, served in order."""
    replies = iter(script)

    async def fake(contents, cfg, fast=False):
        return next(replies)

    monkeypatch.setattr(agent, "_generate", fake)
    events = []

    async def emit(kind, data):
        events.append((kind, data))

    sess = agent.Session(id="t", device="pytest-agent", customer_id=HERO, lang=lang)
    out = asyncio.run(agent.run_turn(sess, question, "text", emit))
    return out, events, sess


CALL = types.Part(function_call=types.FunctionCall(name="safe_to_spend", args={}))


def test_right_numbers_pass(monkeypatch):
    out, events, _ = _run(monkeypatch, [_reply(CALL), _reply(types.Part(text="You can safely spend about 1,094 euros until payday, about 46 euros a day."))])
    assert out["grounded"] and not out["withheld"] and out["checked"] == 2
    assert [k for k, _ in events] == ["status", "card", "text", "done"]


def test_wrong_number_is_rewritten_once(monkeypatch):
    out, events, sess = _run(monkeypatch, [
        _reply(CALL),
        _reply(types.Part(text="You can safely spend about 1,700 euros until payday.")),     # not in any tool result
        _reply(types.Part(text="You can safely spend about 1,094 euros until payday.")),
    ])
    assert out["grounded"] and not out["withheld"] and "1,094" in out["text"]
    shown = [d["text"] for k, d in events if k == "text"]
    assert shown == [out["text"]], "the rejected draft must never reach the user"
    assert not any("1,700" in (p.text or "") for c in sess.history() for p in c.parts), "nor stay in the model's memory"


def test_wrong_twice_is_withheld(monkeypatch):
    out, events, _ = _run(monkeypatch, [
        _reply(CALL),
        _reply(types.Part(text="You can safely spend about 1,700 euros until payday.")),
        _reply(types.Part(text="You can safely spend about 1,300 euros until payday.")),
    ])
    assert out["withheld"] and not out["grounded"]
    assert "1,300" not in out["text"] and "1,700" not in out["text"]
    assert out["text"] == agent.WITHHELD["en"][0]
    assert any(k == "card" for k, _ in events), "the engine's own card still shows the real figures"


def test_withheld_in_finnish(monkeypatch):
    out, _, _ = _run(monkeypatch, [_reply(types.Part(text="Voit käyttää 9 999 euroa.")), _reply(types.Part(text="Voit käyttää 8 888 euroa."))],
                     question="Paljonko voin käyttää?", lang="fi")
    assert out["withheld"] and out["text"] == agent.WITHHELD["fi"][1]


def test_follow_up_may_repeat_an_earlier_figure_but_not_invent_one(monkeypatch):
    """A second question answered from the first one's calculation is not withheld; a new wrong number still is."""
    out, _, sess = _run(monkeypatch, [_reply(CALL), _reply(types.Part(text="You can safely spend about 1,094 euros until payday."))])
    assert out["grounded"]

    async def emit(kind, data):
        pass

    replies = iter([_reply(types.Part(text="As I said, about 1,094 euros until payday."))])

    async def fake(contents, cfg, fast=False):
        return next(replies)

    monkeypatch.setattr(agent, "_generate", fake)
    again = asyncio.run(agent.run_turn(sess, "Say that again?", "text", emit))
    assert again["grounded"] and not again["withheld"] and again["tools"] == []
    assert again["figures"] and again["figures"][0]["source"] == "Safe to spend"

    replies = iter([_reply(types.Part(text="About 2,345 euros.")), _reply(types.Part(text="About 2,346 euros."))])
    wrong = asyncio.run(agent.run_turn(sess, "And now?", "text", emit))
    assert wrong["withheld"]


# ---------------------------------------------------------------- a slow model call does not hang the turn
class _FakeModels:
    def __init__(self, plan):
        self.plan, self.calls = plan, []

    async def generate_content(self, model, contents, config):
        n = len(self.calls)
        self.calls.append(model)
        wait, result = self.plan[n]
        await asyncio.sleep(wait)
        if isinstance(result, Exception):
            raise result
        return result


def _fake_client(monkeypatch, plan):
    models = _FakeModels(plan)
    fake = type("C", (), {"aio": type("A", (), {"models": models})()})()
    monkeypatch.setattr(agent, "client", lambda key=None: fake)
    monkeypatch.setattr(agent.config, "gemini_key", lambda: "k1")
    monkeypatch.setattr(agent.config, "gemini_fallback_key", lambda: None)
    monkeypatch.setattr(agent, "HEDGE", (0.0, 0.05, 0.1))
    return models


def test_a_slow_first_attempt_is_overtaken_by_a_second(monkeypatch):
    models = _fake_client(monkeypatch, [(5, "slow"), (0.01, "fast"), (5, "never")])
    t0 = time.time()
    assert asyncio.run(agent._generate([], None)) == "fast"
    assert time.time() - t0 < 1 and len(models.calls) == 2


def test_a_fast_first_attempt_starts_nothing_else(monkeypatch):
    models = _fake_client(monkeypatch, [(0.01, "first"), (0, "second"), (0, "third")])
    assert asyncio.run(agent._generate([], None)) == "first"
    assert len(models.calls) == 1


def test_a_failed_attempt_moves_on_at_once_and_all_failing_raises(monkeypatch):
    models = _fake_client(monkeypatch, [(0, RuntimeError("429")), (0, RuntimeError("503")), (0, "third time lucky")])
    assert asyncio.run(agent._generate([], None)) == "third time lucky"
    assert models.calls == [agent.config.GEMINI_MODEL, agent.config.GEMINI_MODEL_FAST, agent.config.GEMINI_MODEL]
    _fake_client(monkeypatch, [(0, RuntimeError("a")), (0, RuntimeError("b")), (0, RuntimeError("c"))])
    with pytest.raises(RuntimeError):
        asyncio.run(agent._generate([], None))


def test_the_first_step_goes_to_the_small_model_and_the_main_one_steps_in_if_it_is_slow(monkeypatch):
    models = _fake_client(monkeypatch, [(5, "slow small model"), (0.01, "main model"), (5, "never")])
    monkeypatch.setattr(agent, "HEDGE_FAST", (0.0, 0.05, 0.1))
    assert asyncio.run(agent._generate([], None, fast=True)) == "main model"
    assert models.calls == [agent.config.GEMINI_MODEL_FAST, agent.config.GEMINI_MODEL]


# ---------------------------------------------------------------- the voice screen misses nothing on a reconnect
def test_event_log_replays_what_a_reader_missed():
    async def go():
        log = agent.EventLog()
        await log.put(("user", {"text": "hi"}))
        await log.put(("card", {"card": 1}))
        first = await log.after(0, 0.01)
        assert [n for n, *_ in first] == [1, 2]
        assert await log.after(2, 0.01) == []                      # nothing new: a keep-alive, not a loss
        waiter = asyncio.create_task(log.after(2, 1))               # two readers wait on the same log
        other = asyncio.create_task(log.after(2, 1))
        await asyncio.sleep(0.01)
        await log.put(("coach", {"text": "there"}))
        assert [k for _, k, _ in await waiter] == ["coach"]
        assert [k for _, k, _ in await other] == ["coach"]          # one reader does not take it from the other
        assert [k for _, k, _ in await log.after(1, 0.01)] == ["card", "coach"]   # a reader that was behind catches up
    asyncio.run(go())


def test_voice_events_resume_from_the_last_event_the_phone_saw():
    from fastapi.testclient import TestClient
    from kori.app import app
    sess = agent.session("pytest-events", "pytest", "CUST00092", "en")
    sess.queue.items[:] = [("user", {"text": "one"}), ("coach", {"text": "two"}), ("card", {"card": {"type": "safe"}})]

    def read(headers):
        with TestClient(app) as c, c.stream("GET", "/api/voice/events", params={"session": "pytest-events"}, headers=headers) as r:
            out = []
            for line in r.iter_lines():
                if line.startswith("event:"):
                    out.append(line.split(": ", 1)[1])
                if len(out) == (3 if headers else 1):
                    return out
    assert read({}) == ["ready"]                                     # a first connection starts from now
    assert read({"Last-Event-ID": "1"}) == ["ready", "coach", "card"]
