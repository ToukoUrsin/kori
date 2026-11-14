import { Calculator, ChevronDown, Pin, PinOff, Receipt } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useApp } from "../../lib/store";
import type {
  BasketsData,
  Card,
  ForecastData,
  LessonCardData,
  Notice,
  PeersData,
  ProfileData,
  QueryData,
  SafeData,
  SaveData,
  TrackData,
  WhatIfData,
} from "../../lib/types";
import { cx } from "../ui/bits";
import {
  BasketsBody,
  BreakdownBody,
  ForecastBody,
  LessonBody,
  NoticesBody,
  PeersBody,
  ProfileBody,
  SafeBody,
  SaveBody,
  StatBody,
  TrackBody,
  TrendBody,
  WhatIfBody,
} from "./bodies";

function Body({ card, open }: { card: Card; open: boolean }) {
  const { t } = useApp();
  switch (card.type) {
    case "safe":
      return <SafeBody d={card.data as SafeData} open={open} />;
    case "forecast":
      return <ForecastBody d={card.data as ForecastData} />;
    case "baskets":
      return <BasketsBody d={card.data as BasketsData} />;
    case "stat":
      return <StatBody d={card.data as QueryData} open={open} />;
    case "breakdown":
      return <BreakdownBody d={card.data as QueryData} open={open} />;
    case "trend":
      return <TrendBody d={card.data as QueryData} />;
    case "whatif":
      return <WhatIfBody d={card.data as WhatIfData} showChanges={(card.data as WhatIfData).changes.length > 1} />;
    case "peers":
      return <PeersBody d={card.data as PeersData} />;
    case "profile":
      return <ProfileBody d={card.data as ProfileData} />;
    case "save":
      return <SaveBody d={card.data as SaveData} />;
    case "notices":
      return <NoticesBody items={(card.data as { items: Notice[] }).items || []} />;
    case "track":
      return <TrackBody d={card.data as TrackData} />;
    case "lesson":
      return <LessonBody d={card.data as LessonCardData} />;
    default:
      return <p className="text-[13px] text-ink-3">{t("card.unknown")}</p>;
  }
}

function FootButton({ children, onClick, pressed, disabled, label }: { children: ReactNode; onClick: () => void; pressed?: boolean; disabled?: boolean; label?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={pressed}
      aria-label={label}
      disabled={disabled}
      className={cx(
        "relative inline-flex h-8 items-center gap-1.5 rounded-md px-1.5 text-[13px] font-medium transition-colors duration-150 after:absolute after:-inset-y-1.5 after:inset-x-0 disabled:opacity-50",
        pressed ? "text-brand" : "text-ink-2 hover:text-ink",
      )}
    >
      {children}
    </button>
  );
}

/**
 * One generated card. `pinned` is the My view variant (the action reads Unpin);
 * `bare` drops the frame for use inside a sheet.
 */
export function CardView({ card, pinned, bare, defaultOpen = false, className }: { card: Card; pinned?: boolean; bare?: boolean; defaultOpen?: boolean; className?: string }) {
  const { t, pinIdFor, togglePin } = useApp();
  const [open, setOpen] = useState(defaultOpen);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const isPinned = !!pinIdFor(card);

  useEffect(() => {
    if (!failed) return;
    const id = setTimeout(() => setFailed(false), 4000);
    return () => clearTimeout(id);
  }, [failed]);

  const data = card.data as QueryData;
  const txCount = card.type === "stat" || card.type === "breakdown" ? data.transactions?.length || 0 : 0;
  const expandable: "maths" | "tx" | null = card.type === "safe" ? "maths" : (card.type === "stat" && txCount > 3) || (card.type === "breakdown" && txCount > 0) ? "tx" : null;
  const canPin = !!card.source && card.type !== "lesson";

  const onPin = async () => {
    setBusy(true);
    setFailed(false);
    try {
      await togglePin(card);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className={cx(!bare && "rounded-card border border-line bg-surface px-4 pt-3.5", bare ? "pb-1" : expandable || canPin ? "pb-1.5" : "pb-4", className)}>
      <header className={cx("mb-3", bare && "pr-10")}>
        <h3 className={cx("font-semibold tracking-[-0.01em] text-ink", bare ? "text-[18px] leading-6" : "text-[15px] leading-5")}>{card.title}</h3>
        {card.subtitle && <p className="mt-0.5 text-[13px] leading-[18px] text-ink-3">{card.subtitle}</p>}
      </header>
      <Body card={card} open={open} />
      {card.note && <p className="mt-3 text-[12px] leading-4 text-ink-3">{card.note}</p>}
      {(expandable || canPin) && (
        <footer className="mt-3 flex min-h-11 flex-wrap items-center gap-x-3 border-t border-line pt-1.5">
          {canPin && (
            <FootButton onClick={onPin} pressed={!pinned && isPinned} disabled={busy}>
              {pinned ? <PinOff size={15} strokeWidth={2} aria-hidden /> : <Pin size={15} strokeWidth={2} fill={isPinned ? "currentColor" : "none"} aria-hidden />}
              {pinned ? t("card.unpin") : isPinned ? t("card.pinned") : t("card.pin")}
            </FootButton>
          )}
          {expandable && (
            <FootButton onClick={() => setOpen((v) => !v)}>
              {expandable === "maths" ? <Calculator size={15} strokeWidth={2} aria-hidden /> : <Receipt size={15} strokeWidth={2} aria-hidden />}
              {expandable === "maths" ? t(open ? "safe.mathsHide" : "safe.maths") : t(open ? "tx.hide" : "tx.show")}
              <ChevronDown size={14} strokeWidth={2} className={cx("transition-transform duration-200", open && "rotate-180")} aria-hidden />
            </FootButton>
          )}
          {failed && (
            <span role="alert" className="text-[12px] text-warn-ink">
              {t("card.pinFail")}
            </span>
          )}
        </footer>
      )}
    </article>
  );
}
