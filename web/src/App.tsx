import { MotionConfig } from "motion/react";
import { useEffect, useRef } from "react";
import { CoachProvider } from "./coach/CoachProvider";
import { AppProvider, useApp } from "./lib/store";
import { isEmbedMode, postToHost, subscribeHost, useHostInit, type HostToKori } from "./lib/host";
import { JudgePanel } from "./shell/JudgePanel";
import { Shell } from "./shell/Shell";

/** iOS does not shrink the layout when the keyboard opens; follow the visual viewport so the composer stays above it. */
function useViewportHeight() {
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const set = () => {
      document.documentElement.style.setProperty("--app-h", `${Math.round(vv.height)}px`);
      if (vv.offsetTop > 0) window.scrollTo(0, 0);
    };
    set();
    vv.addEventListener("resize", set);
    vv.addEventListener("scroll", set);
    return () => {
      vv.removeEventListener("resize", set);
      vv.removeEventListener("scroll", set);
    };
  }, []);
}

function Stage() {
  useViewportHeight();
  const embed = isEmbedMode();
  return (
    <div className={embed ? "flex h-full w-full items-center justify-center overflow-hidden" : "flex h-full w-full items-center justify-center overflow-hidden lg:gap-14 lg:px-10 xl:gap-12"}>
      {!embed && <JudgePanel part="intro" className="hidden xl:flex" />}
      {/* below 640px the app is the whole screen; above it sits in a quiet phone frame */}
      <div className={embed ? "h-full w-full shrink-0" : "h-[var(--app-h,100dvh)] w-full shrink-0 sm:h-[min(864px,calc(100dvh-32px))] sm:w-[410px] sm:rounded-[54px] sm:bg-ink sm:p-[10px] sm:shadow-[0_30px_70px_-30px_oklch(0.22_0.02_160/0.55)]"}>
        <div className={embed ? "relative h-full w-full overflow-hidden bg-ground" : "relative h-full w-full overflow-hidden bg-ground sm:rounded-[44px]"}>
          <Shell />
        </div>
      </div>
      {!embed && <JudgePanel part="guide" className="hidden xl:flex" />}
      {!embed && <JudgePanel part="all" className="hidden lg:flex xl:hidden" />}
    </div>
  );
}

/** Before the bank app has said who the customer is. The language comes from the frame's own address. */
function EmbedWaiting() {
  const fi = new URLSearchParams(window.location.search).get("lang")?.toLowerCase().startsWith("fi");
  return (
    <div className="flex h-full w-full items-center justify-center bg-ground px-8 text-center">
      <div className="max-w-[280px]">
        <p className="text-[17px] font-semibold leading-6 text-ink">{fi ? "Odotetaan lupaa" : "Waiting for permission"}</p>
        <p className="mt-2 text-[15px] leading-[22px] text-ink-2">
          {fi ? "Kori avautuu, kun pankkisovelluksesi antaa sille luvan lukea tätä tiliä." : "Kori opens when your bank app allows it to read this account."}
        </p>
      </div>
    </div>
  );
}

function EmbedRuntime() {
  const init = useHostInit();
  const { home, coachOpen: sheetOpen, coachRequest, chatOpen, chatRequest, openCoach, openChat, setTab } = useApp();
  // the host sees one coach: the chat layer or the voice sheet, whichever is open
  const coachOpen = sheetOpen || chatOpen;
  const request = chatOpen ? chatRequest : coachRequest;
  const lastRequest = useRef(0);
  const wasOpen = useRef(false);
  const ready = !!init?.consent.transactions;

  useEffect(() => {
    if (!ready) return;
    postToHost({ type: "kori:ready", v: 1 });
  }, [ready]);

  useEffect(() => {
    if (!ready) return;
    const onMessage = (message: HostToKori) => {
      if (message.type === "kori:ask") {
        openCoach({ ask: message.question });
        postToHost({ type: "kori:event", v: 1, name: "question_received" });
      } else if (message.type === "kori:open") {
        if (message.screen === "coach") openChat();
        else setTab("today");
      }
    };
    return subscribeHost(onMessage);
  }, [openChat, openCoach, ready, setTab]);

  useEffect(() => {
    if (!ready || !home.data) return;
    const safe = home.data.safe;
    postToHost({ type: "kori:safe", v: 1, amount: safe.amount, per_day: safe.per_day, days_to_payday: safe.days_to_payday, next_payday: safe.next_payday, status: safe.status });
  }, [home.data, ready]);

  useEffect(() => {
    if (!ready) return;
    if (coachOpen) {
      wasOpen.current = true;
      postToHost({ type: "kori:navigate", v: 1, screen: "coach" });
      if (lastRequest.current !== request?.id) {
        lastRequest.current = request?.id || lastRequest.current;
        postToHost({ type: "kori:event", v: 1, name: request?.ask ? "question_sent" : "coach_opened" });
      }
    } else if (wasOpen.current) {
      wasOpen.current = false;
      postToHost({ type: "kori:close", v: 1 });
    }
  }, [coachOpen, request, ready]);

  return null;
}

function EmbeddedApp() {
  const init = useHostInit();
  useEffect(() => {
    if (!init) return;
    const q = new URLSearchParams(location.search);
    q.set("customer", init.customer);
    q.set("lang", init.lang);
    history.replaceState(null, "", `${location.pathname}?${q.toString()}${location.hash}`);
  }, [init]);
  if (!init?.consent.transactions) return <EmbedWaiting />;
  return (
    <AppProvider>
      <CoachProvider>
        <EmbedRuntime />
        <Stage />
      </CoachProvider>
    </AppProvider>
  );
}

function StandardApp() {
  return (
    <MotionConfig reducedMotion="user">
      <AppProvider>
        <CoachProvider>
          <Stage />
        </CoachProvider>
      </AppProvider>
    </MotionConfig>
  );
}

export default function App() {
  if (isEmbedMode()) {
    return <MotionConfig reducedMotion="user"><EmbeddedApp /></MotionConfig>;
  }
  return <StandardApp />;
}
