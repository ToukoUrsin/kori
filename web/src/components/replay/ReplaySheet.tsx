import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { useApp } from "../../lib/store";
import type { ReplayStory } from "../../lib/types";
import { Button, IconButton } from "../ui/bits";
import { Sheet } from "../ui/Sheet";
import { ReplayCells, ReplayMissBlock } from "./ReplayStrip";

export function ReplaySheet({ story, open, onClose }: { story: ReplayStory | null; open: boolean; onClose: () => void }) {
  const { t, openCoach } = useApp();
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);

  useEffect(() => {
    if (open && story) setSelectedMonth(story.miss?.month || story.cells.find((c) => c.state !== "skipped")?.month || story.cells[0]?.month || null);
  }, [open, story]);

  if (!story) return null;
  const selected = story.cells.find((cell) => cell.month === selectedMonth) || story.cells[0];
  const selectedIsMiss = !!story.miss && selected?.month === story.miss.month;
  const ask = t("replay.ask");
  const heldPct = story.checked ? (story.held / story.checked) * 100 : 0;
  const balancePct = story.checked ? (story.balance_as_budget_held / story.checked) * 100 : 0;

  return (
    <Sheet open={open} onClose={onClose} label={t("replay.title")} size="full">
      <div className="flex min-h-0 flex-col">
        <div className="flex items-start justify-between gap-3 px-5 pb-2">
          <div className="min-w-0">
            <h2 className="text-[20px] font-semibold leading-6 tracking-[-0.02em] text-ink">{t("replay.title")}</h2>
            {story.partial_view && <p className="mt-1 text-[12px] leading-4 text-ink-3">{t("today.safePartialLabel")}</p>}
          </div>
          <IconButton label={t("common.close")} onClick={onClose} className="-mr-2 -mt-1"><X size={21} strokeWidth={2} aria-hidden /></IconButton>
        </div>
        <div className="scroll-y min-h-0 px-5 pb-[max(24px,var(--safe-b))]">
          <p className="text-[18px] font-semibold leading-6 tracking-[-0.015em] text-ink">{story.headline}</p>

          <section className="mt-5" aria-label={t("replay.months")}>
            <ReplayCells story={story} selected={selected?.month} onSelect={setSelectedMonth} large animate={open} />
            <p className="mt-3 text-[12px] leading-4 text-ink-3">{story.summary}</p>
          </section>

          {selected && <p className="mt-5 rounded-[10px] bg-sunk px-3.5 py-3 text-[14px] leading-5 text-ink-2">{selected.line}</p>}

          {selectedIsMiss && <ReplayMissBlock story={story} />}

          <section className="mt-6">
            <h3 className="text-[15px] font-semibold leading-5 text-ink">{t("replay.headToHead")}</h3>
            <div className="mt-3 space-y-3">
              <div>
                <div className="flex items-baseline justify-between gap-3 text-[13px] leading-[18px]">
                  <span className="text-ink-2">{t("replay.numberHeld")}</span>
                  <span className="num font-semibold text-ink">{story.held} / {story.checked}</span>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-line"><div className="h-full rounded-full bg-brand" style={{ width: `${heldPct}%` }} /></div>
              </div>
              <div>
                <div className="flex items-baseline justify-between gap-3 text-[13px] leading-[18px]">
                  <span className="text-ink-2">{t("replay.balanceHeld")}</span>
                  <span className="num font-semibold text-ink">{story.balance_as_budget_held} / {story.checked}</span>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-line"><div className="h-full rounded-full bg-ink-3" style={{ width: `${balancePct}%` }} /></div>
              </div>
            </div>
            <p className="mt-3 text-[13px] leading-[18px] text-ink-2">{story.versus}</p>
          </section>

          <section className="mt-6 border-t border-line pt-4">
            <h3 className="text-[15px] font-semibold leading-5 text-ink">{t("replay.everyoneTitle")}</h3>
            <p className="mt-1.5 text-[13px] leading-[18px] text-ink-2">{story.everyone}</p>
            <p className="mt-1.5 text-[12px] leading-[17px] text-ink-3">{t("replay.synthetic")}</p>
          </section>

          <p className="mt-5 text-[12px] leading-[17px] text-ink-3">{story.method}</p>
          <Button variant="primary" className="mt-5 w-full" onClick={() => openCoach({ ask })}>{ask}</Button>
        </div>
      </div>
    </Sheet>
  );
}

