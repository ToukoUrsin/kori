import { MotionConfig } from "motion/react";
import { useEffect } from "react";
import { CoachProvider } from "./coach/CoachProvider";
import { AppProvider } from "./lib/store";
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
  return (
    <div className="flex h-full w-full items-center justify-center overflow-hidden lg:gap-[72px] lg:px-10">
      {/* below 640px the app is the whole screen; above it sits in a quiet phone frame */}
      <div className="h-[var(--app-h,100dvh)] w-full shrink-0 sm:h-[min(864px,calc(100dvh-32px))] sm:w-[410px] sm:rounded-[54px] sm:bg-ink sm:p-[10px] sm:shadow-[0_30px_70px_-30px_oklch(0.22_0.02_160/0.55)]">
        <div className="relative h-full w-full overflow-hidden bg-ground sm:rounded-[44px]">
          <Shell />
        </div>
      </div>
      <JudgePanel />
    </div>
  );
}

export default function App() {
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
