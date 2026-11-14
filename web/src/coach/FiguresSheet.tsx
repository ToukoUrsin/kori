import { Calculator, ShieldCheck } from "lucide-react";
import { Sheet } from "../components/ui/Sheet";
import { useApp } from "../lib/store";

export interface Figure {
  /** the number as it stands in the answer */
  text: string;
  /** what it is */
  label: string;
  /** the calculation it came from */
  source: string;
  rounded?: boolean;
}

/** Figures in the order the answer used them, grouped under the calculation each came from. */
function bySource(figures: Figure[]): { source: string; rows: Figure[] }[] {
  const groups: { source: string; rows: Figure[] }[] = [];
  for (const f of figures) {
    const g = groups.find((x) => x.source === f.source);
    if (g) g.rows.push(f);
    else groups.push({ source: f.source, rows: [f] });
  }
  return groups;
}

/** The proof under an answer: every number in it, what it is, and which calculation produced it. */
export function FiguresSheet({ open, onClose, figures }: { open: boolean; onClose: () => void; figures: Figure[] }) {
  const { t } = useApp();
  const anyRounded = figures.some((f) => f.rounded);
  return (
    <Sheet open={open} onClose={onClose} label={t("coach.figuresTitle")} z={60}>
      <div className="scroll-y min-h-0 px-5 pb-[max(24px,var(--safe-b))] pt-2">
        <h2 className="text-[20px] font-semibold leading-7 tracking-[-0.02em] text-ink">{t("coach.figuresTitle")}</h2>

        {bySource(figures).map((g) => (
          <section key={g.source} className="mt-4">
            <h3 className="flex items-center gap-1.5 text-[13px] font-medium leading-[18px] text-ink-2">
              <Calculator size={14} strokeWidth={2} className="shrink-0 text-ink-3" aria-hidden />
              {g.source}
            </h3>
            <ul className="mt-2 divide-y divide-line rounded-card border border-line bg-surface">
              {g.rows.map((f, i) => (
                <li key={`${f.text}-${i}`} className="flex items-baseline gap-3 px-4 py-2.5">
                  <span className="num flex min-w-[84px] shrink-0 items-baseline text-[16px] font-semibold leading-[22px] text-ink">
                    <span className="w-4 shrink-0 text-[14px] font-normal text-ink-3" aria-hidden>
                      {f.rounded ? "≈" : ""}
                    </span>
                    {f.text}
                    {f.rounded && <span className="sr-only"> ({t("coach.rounded")})</span>}
                  </span>
                  <span className="min-w-0 flex-1 text-[14px] leading-5 text-ink-2">{f.label}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}

        {anyRounded && (
          <p className="mt-2.5 px-4 text-[12px] leading-4 text-ink-3">
            <span className="inline-block w-4" aria-hidden>
              ≈
            </span>
            {t("coach.rounded")}
          </p>
        )}
        <p className="mt-4 flex gap-2 text-[13px] leading-[18px] text-ink-2">
          <ShieldCheck size={15} strokeWidth={2} className="mt-px shrink-0 text-brand" aria-hidden />
          {t("coach.figuresFoot")}
        </p>
      </div>
    </Sheet>
  );
}
