import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ComponentType, type ReactNode } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/store";
import type { Card, ChatDone } from "../lib/types";
import type { Conv } from "./VoiceBridge";

type BridgeProps = { onConv: (c: Conv) => void; onState: (s: { speaking: boolean; muted: boolean }) => void; onTranscript: (text: string, final: boolean) => void };

export interface Turn {
  id: string;
  role: "user" | "coach";
  text: string;
  via?: "voice";
  /** what the coach is doing right now, in its own words */
  status?: string;
  cards: Card[];
  done?: ChatDone;
  pending: boolean;
  error?: string;
  /** the question this turn answers, kept for retry */
  ask?: string;
  /** the text arrived while the user was watching: reveal it */
  fresh?: boolean;
}

/** off: text only. connecting/live: ElevenLabs session. fallback: hold-to-talk. */
export type VoicePhase = "off" | "connecting" | "live" | "fallback";

interface Coach {
  turns: Turn[];
  busy: boolean;
  send: (text: string, mode?: "text" | "voice") => Promise<{ id: string; text: string } | null>;
  retry: (turn: Turn) => void;
  stop: () => void;
  reset: () => void;
  speech: { id: string; state: "loading" | "playing" } | null;
  speak: (id: string, text: string) => void;
  stopSpeak: () => void;
  unlockAudio: () => void;
  voice: {
    phase: VoicePhase;
    note: string | null;
    setNote: (n: string | null) => void;
    speaking: boolean;
    muted: boolean;
    start: () => void;
    end: () => void;
    toggleMute: () => void;
    /** three bar heights 0..1 from the live audio, or null when there is nothing to read */
    levels: () => [number, number, number] | null;
  };
}

const Ctx = createContext<Coach | null>(null);

let seq = 0;
const nid = () => `t${Date.now().toString(36)}${(seq++).toString(36)}`;
const plain = (s: string) => s.replace(/\*\*/g, "");
const SILENCE = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

function closePending(ts: Turn[]): Turn[] {
  return ts.some((x) => x.pending) ? ts.map((x) => (x.pending ? { ...x, pending: false, status: undefined } : x)) : ts;
}

function Inner({ children }: { children: ReactNode }) {
  const { customer, lang, t, bump, openLesson, coachRequest, showToast } = useApp();
  // the voice SDK is most of the bundle, so it loads on the first tap of the microphone, not with the page
  const convRef = useRef<Conv | null>(null);
  const [Bridge, setBridge] = useState<ComponentType<BridgeProps> | null>(null);
  const [live, setLive] = useState({ speaking: false, muted: false });
  const bridge = useRef<{ ready: Promise<void>; ok: () => void } | null>(null);
  const needBridge = useCallback(async () => {
    if (!bridge.current) {
      let ok = () => {};
      const ready = new Promise<void>((r) => (ok = r));
      bridge.current = { ready, ok };
      try {
        const mod = await import("./VoiceBridge");
        setBridge(() => mod.default);
      } catch (e) {
        bridge.current = null;
        throw e;
      }
    }
    await bridge.current.ready;
  }, []);
  const onConv = useCallback((c: Conv) => {
    convRef.current = c;
    bridge.current?.ok();
  }, []);

  const [turns, setTurns] = useState<Turn[]>([]);
  const [phase, setPhaseState] = useState<VoicePhase>("off");
  const [note, setNote] = useState<string | null>(null);
  const [speech, setSpeech] = useState<Coach["speech"]>(null);

  const sessionRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const phaseRef = useRef<VoicePhase>("off");
  const esRef = useRef<EventSource | null>(null);
  const voiceTurn = useRef<string | null>(null);
  const voiceDraft = useRef<string | null>(null);
  const voiceTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const connectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const speakAbort = useRef<AbortController | null>(null);
  const tRef = useRef(t);
  tRef.current = t;
  const ctxRef = useRef({ customer, lang });
  ctxRef.current = { customer, lang };

  const setPhase = useCallback((p: VoicePhase) => {
    phaseRef.current = p;
    setPhaseState(p);
  }, []);

  const patch = useCallback((id: string, f: Partial<Turn> | ((x: Turn) => Partial<Turn>)) => {
    setTurns((ts) => ts.map((x) => (x.id === id ? { ...x, ...(typeof f === "function" ? f(x) : f) } : x)));
  }, []);

  const effect = useCallback(
    (type: string, lesson?: string) => {
      if (type === "open_lesson" && lesson) setTimeout(() => openLesson(lesson), 1100);
      else if (type === "plan_changed" || type === "action_set" || type === "action_cleared") bump();
    },
    [bump, openLesson],
  );

  /* ------------------------------------------------------------- speech */

  const audioEl = useCallback(() => (audioRef.current ??= new Audio()), []);

  const stopSpeak = useCallback(() => {
    speakAbort.current?.abort();
    speakAbort.current = null;
    const a = audioRef.current;
    if (a) {
      a.onended = null;
      a.pause();
    }
    setSpeech(null);
  }, []);

  const speak = useCallback(
    async (id: string, text: string) => {
      stopSpeak();
      const ac = new AbortController();
      speakAbort.current = ac;
      setSpeech({ id, state: "loading" });
      try {
        const blob = await api.tts(plain(text), ctxRef.current.lang, ac.signal);
        if (ac.signal.aborted) return;
        const url = URL.createObjectURL(blob);
        const a = audioEl();
        a.muted = false;
        a.src = url;
        a.onended = () => {
          URL.revokeObjectURL(url);
          setSpeech((s) => (s && s.id === id ? null : s));
        };
        await a.play();
        setSpeech({ id, state: "playing" });
      } catch {
        if (!ac.signal.aborted) {
          setSpeech(null);
          showToast(tRef.current("coach.speakFail"));
        }
      }
    },
    [audioEl, showToast, stopSpeak],
  );

  /** Browsers only let audio start from a tap. Call this in the tap so a later answer can be spoken. */
  const unlockAudio = useCallback(() => {
    const a = audioEl();
    if (!a.paused) return;
    a.muted = true;
    a.src = SILENCE;
    a.play()
      .then(() => a.pause())
      .catch(() => undefined)
      .finally(() => {
        a.muted = false;
      });
  }, [audioEl]);

  /* --------------------------------------------------------------- text */

  const send = useCallback(
    async (raw: string, mode: "text" | "voice" = "text") => {
      const text = raw.trim();
      if (!text) return null;
      if (phaseRef.current === "live") {
        // one conversation: while the voice session is open, typed and tapped questions go through it too
        convRef.current?.sendUserMessage(text);
        return null;
      }
      stopSpeak();
      setNote(null);
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      const cid = nid();
      setTurns((ts) => [
        ...closePending(ts),
        { id: nid(), role: "user", text, cards: [], pending: false, via: mode === "voice" ? "voice" : undefined },
        { id: cid, role: "coach", text: "", cards: [], pending: true, status: tRef.current("coach.thinking"), ask: text },
      ]);
      const out = { answer: "", failed: null as string | null, done: false };
      try {
        await api.chat(
          { customer: ctxRef.current.customer, lang: ctxRef.current.lang, session: sessionRef.current, text, mode },
          (e) => {
            if (ac.signal.aborted) return;
            switch (e.event) {
              case "session":
                sessionRef.current = e.data.session;
                break;
              case "status":
                patch(cid, { status: e.data.label });
                break;
              case "card":
                patch(cid, (x) => ({ cards: [...x.cards, e.data.card] }));
                break;
              case "effect":
                effect(e.data.type, e.data.lesson);
                break;
              case "text":
                out.answer = e.data.text;
                patch(cid, { text: e.data.text, fresh: true, status: undefined });
                break;
              case "done":
                out.done = true;
                if (e.data.error) {
                  // no answer from the model: show its apology as an error with "try again", not as an answer
                  out.failed = out.answer;
                  patch(cid, { text: "", pending: false, status: undefined });
                } else patch(cid, { done: e.data, pending: false, status: undefined });
                break;
              case "error":
                out.failed = e.data.message || "";
                break;
            }
          },
          ac.signal,
        );
      } catch {
        if (ac.signal.aborted) {
          patch(cid, (x) => ({ pending: false, status: undefined, error: x.text ? undefined : tRef.current("coach.stopped") }));
          return null;
        }
        if (!out.answer) out.failed = out.failed ?? "";
      }
      if (abortRef.current === ac) abortRef.current = null;
      if (out.failed !== null || !out.answer) {
        patch(cid, { pending: false, status: undefined, error: out.failed || tRef.current("coach.error") });
        return null;
      }
      patch(cid, { pending: false, status: undefined });
      return { id: cid, text: out.answer };
    },
    [effect, patch, stopSpeak],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const retry = useCallback(
    (turn: Turn) => {
      if (!turn.ask) return;
      setTurns((ts) => {
        const i = ts.findIndex((x) => x.id === turn.id);
        if (i < 1) return ts;
        return [...ts.slice(0, i - 1), ...ts.slice(i + 1)];
      });
      void send(turn.ask);
    },
    [send],
  );

  /* -------------------------------------------------------------- voice */

  const closeEvents = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    clearTimeout(voiceTimer.current);
    clearTimeout(connectTimer.current);
    voiceTurn.current = null;
    voiceDraft.current = null;
  }, []);

  const openEvents = useCallback(
    (session: string) => {
      closeEvents();
      const es = new EventSource(`/api/voice/events?session=${encodeURIComponent(session)}`);
      esRef.current = es;
      const on = <T,>(name: string, fn: (d: T) => void) =>
        es.addEventListener(name, (e) => {
          try {
            fn(JSON.parse((e as MessageEvent).data) as T);
          } catch {
            /* a malformed event is skipped */
          }
        });
      on<{ text: string }>("user", (d) => {
        clearTimeout(voiceTimer.current);
        const draft = voiceDraft.current;
        const cid = nid();
        voiceTurn.current = cid;
        voiceDraft.current = null;
        setTurns((ts) => {
          const base = closePending(ts);
          if (draft && base.some((x) => x.id === draft)) return [...base.map((x) => (x.id === draft ? { ...x, text: d.text } : x)), { id: cid, role: "coach", text: "", cards: [], pending: true, status: tRef.current("coach.thinking"), via: "voice" }];
          return [...base, { id: nid(), role: "user", text: d.text, cards: [], pending: false, via: "voice" }, { id: cid, role: "coach", text: "", cards: [], pending: true, status: tRef.current("coach.thinking"), via: "voice" }];
        });
      });
      on<{ label: string }>("status", (d) => voiceTurn.current && patch(voiceTurn.current, { status: d.label }));
      on<{ card: Card }>("card", (d) => voiceTurn.current && patch(voiceTurn.current, (x) => ({ cards: [...x.cards, d.card] })));
      on<{ type: string; lesson?: string }>("effect", (d) => effect(d.type, d.lesson));
      on<ChatDone>("done", (d) => {
        const id = voiceTurn.current;
        if (!id) return;
        patch(id, (x) => ({ done: d, pending: !x.text, status: x.text ? undefined : x.status }));
        // the spoken words follow as `coach`; if they never come, stop waiting
        voiceTimer.current = setTimeout(() => patch(id, { pending: false, status: undefined }), 8000);
      });
      on<{ text: string }>("coach", (d) => {
        clearTimeout(voiceTimer.current);
        const id = voiceTurn.current;
        if (id) patch(id, (x) => ({ text: d.text, fresh: true, status: undefined, pending: !x.done }));
        else setTurns((ts) => [...ts, { id: nid(), role: "coach", text: d.text, cards: [], pending: false, via: "voice", fresh: true }]);
        if (id) voiceTimer.current = setTimeout(() => patch(id, { pending: false, status: undefined }), 4000);
      });
    },
    [closeEvents, effect, patch],
  );

  const onVoiceTranscript = useCallback((text: string) => {
    if (phaseRef.current !== "live" || !text.trim()) return;
    const value = text.trim();
    setTurns((ts) => {
      const coachIndex = voiceTurn.current ? ts.findIndex((x) => x.id === voiceTurn.current) : -1;
      const userIndex = coachIndex > 0 ? [...ts.slice(0, coachIndex)].reverse().findIndex((x) => x.role === "user" && x.via === "voice") : -1;
      if (userIndex >= 0 && coachIndex > 0) {
        const i = coachIndex - 1 - userIndex;
        return ts.map((x, j) => (j === i ? { ...x, text: value } : x));
      }
      const id = voiceDraft.current || nid();
      voiceDraft.current = id;
      const existing = ts.findIndex((x) => x.id === id);
      if (existing >= 0) return ts.map((x) => (x.id === id ? { ...x, text: value } : x));
      return [...ts, { id, role: "user", text: value, cards: [], pending: false, via: "voice" }];
    });
  }, []);

  const endVoice = useCallback(
    (why?: string | null) => {
      const was = phaseRef.current;
      setPhase("off");
      closeEvents();
      setTurns(closePending);
      if (was === "live" || was === "connecting") {
        try {
          convRef.current?.endSession();
        } catch {
          /* already closed */
        }
      }
      setNote(why ?? null);
    },
    [closeEvents, setPhase],
  );

  const toFallback = useCallback(
    (why: string) => {
      const was = phaseRef.current;
      closeEvents();
      setTurns(closePending);
      if (was === "live" || was === "connecting") {
        try {
          convRef.current?.endSession();
        } catch {
          /* already closed */
        }
      }
      setPhase("fallback");
      setNote(why);
    },
    [closeEvents, setPhase],
  );

  const startVoice = useCallback(async () => {
    const now = (): VoicePhase => phaseRef.current;
    if (now() !== "off") return;
    stopSpeak();
    abortRef.current?.abort();
    setNote(null);
    setPhase("connecting");
    // 1. the microphone, asked for inside the tap
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new DOMException("no media devices", "NotFoundError");
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      s.getTracks().forEach((x) => x.stop());
    } catch (e) {
      const name = (e as DOMException)?.name;
      // without a microphone there is nothing to hold either: back to typing, with the reason
      if (now() === "connecting") endVoice(tRef.current(name === "NotAllowedError" || name === "SecurityError" ? "voice.micDenied" : "voice.noMic"));
      return;
    }
    if (now() !== "connecting") return;
    // 2. a session with the agent; without one, hold-to-talk does the same job
    let vs;
    try {
      vs = await api.voiceSession(ctxRef.current.customer, ctxRef.current.lang, sessionRef.current);
    } catch {
      if (now() === "connecting") toFallback(tRef.current("voice.fallback"));
      return;
    }
    if (now() !== "connecting") return;
    if (!vs.token && !vs.signed_url) return toFallback(tRef.current("voice.fallback"));
    sessionRef.current = vs.session;
    try {
      await needBridge();
    } catch {
      if (now() === "connecting") toFallback(tRef.current("voice.fallback"));
      return;
    }
    const conv = convRef.current;
    if (now() !== "connecting" || !conv) return;
    // 3. cards and status arrive on our own stream while the agent speaks
    openEvents(vs.session);
    const first = vs.first_message;
    const shared = {
      customLlmExtraBody: { session: vs.session, customer: ctxRef.current.customer, lang: ctxRef.current.lang },
      overrides: { agent: { firstMessage: first, language: vs.language as "en" | "fi" }, tts: { voiceId: vs.voice_id } },
      onConnect: () => {
        if (now() !== "connecting") return;
        clearTimeout(connectTimer.current);
        setPhase("live");
        if (first) setTurns((ts) => (ts.length && ts[ts.length - 1].text === first ? ts : [...ts, { id: nid(), role: "coach", text: first, cards: [], pending: false, via: "voice", fresh: true }]));
      },
      onDisconnect: () => {
        if (now() === "live") endVoice(tRef.current("voice.ended"));
        else if (now() === "connecting") toFallback(tRef.current("voice.fallback"));
      },
      onError: () => {
        if (now() === "live" || now() === "connecting") toFallback(tRef.current("voice.fallback"));
      },
    };
    try {
      if (vs.token) conv.startSession({ conversationToken: vs.token, connectionType: "webrtc", ...shared });
      else conv.startSession({ signedUrl: vs.signed_url as string, connectionType: "websocket", ...shared });
    } catch {
      return toFallback(tRef.current("voice.fallback"));
    }
    connectTimer.current = setTimeout(() => {
      if (now() === "connecting") toFallback(tRef.current("voice.fallback"));
    }, 15000);
  }, [endVoice, needBridge, openEvents, setPhase, stopSpeak, toFallback]);

  const levels = useCallback((): [number, number, number] | null => {
    if (phaseRef.current !== "live") return null;
    const c = convRef.current;
    if (!c) return null;
    try {
      const d = c.isSpeaking ? c.getOutputByteFrequencyData() : c.getInputByteFrequencyData();
      if (d && d.length >= 16) {
        const band = (a: number, b: number) => {
          let s = 0;
          const from = Math.max(1, Math.floor(d.length * a));
          const to = Math.max(from + 1, Math.floor(d.length * b));
          for (let i = from; i < to; i++) s += d[i];
          return s / (to - from) / 255;
        };
        const v: [number, number, number] = [band(0.01, 0.04), band(0.04, 0.1), band(0.1, 0.22)];
        if (v[0] + v[1] + v[2] > 0.01) return [Math.min(1, v[1] * 1.6), Math.min(1, v[0] * 1.5), Math.min(1, v[2] * 2.2)];
      }
      const vol = c.isSpeaking ? c.getOutputVolume() : c.getInputVolume();
      return [vol * 0.7, vol, vol * 0.55];
    } catch {
      return null;
    }
  }, []);

  const toggleMute = useCallback(() => convRef.current?.setMuted(!convRef.current.isMuted), []);

  /* ---------------------------------------------------------- lifecycle */

  const reset = useCallback(() => {
    abortRef.current?.abort();
    stopSpeak();
    endVoice();
    setTurns([]);
    sessionRef.current = null;
  }, [endVoice, stopSpeak]);

  // another customer is another conversation
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    reset();
  }, [customer, reset]);

  // the agent's voice and language are fixed when a session starts
  useEffect(() => {
    if (phaseRef.current === "live" || phaseRef.current === "connecting") endVoice();
  }, [lang, endVoice]);

  useEffect(
    () => () => {
      abortRef.current?.abort();
      esRef.current?.close();
      audioRef.current?.pause();
    },
    [],
  );

  // questions sent from outside the sheet: notices, chips, the judge panel
  const handled = useRef(0);
  useEffect(() => {
    if (!coachRequest || coachRequest.id === handled.current) return;
    handled.current = coachRequest.id;
    if (coachRequest.voice) void startVoice();
    else if (coachRequest.ask) void send(coachRequest.ask);
  }, [coachRequest, send, startVoice]);

  const busy = turns.some((x) => x.pending);
  const speaking = live.speaking;
  const muted = live.muted;
  const value = useMemo<Coach>(
    () => ({
      turns,
      busy,
      send,
      retry,
      stop,
      reset,
      speech,
      speak: (id, text) => void speak(id, text),
      stopSpeak,
      unlockAudio,
      voice: {
        phase,
        note,
        setNote,
        speaking,
        muted,
        start: () => void startVoice(),
        end: () => endVoice(),
        toggleMute,
        levels,
      },
    }),
    [turns, busy, send, retry, stop, reset, speech, speak, stopSpeak, unlockAudio, phase, note, speaking, muted, startVoice, endVoice, toggleMute, levels],
  );
  return (
    <Ctx.Provider value={value}>
      {Bridge && <Bridge onConv={onConv} onState={setLive} onTranscript={onVoiceTranscript} />}
      {children}
    </Ctx.Provider>
  );
}

export function CoachProvider({ children }: { children: ReactNode }) {
  return <Inner>{children}</Inner>;
}

export function useCoach(): Coach {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCoach outside CoachProvider");
  return v;
}
