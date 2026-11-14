import { motion, useReducedMotion } from "motion/react";
import { money } from "../../lib/format";
import { useApp } from "../../lib/store";
import type { SpokenFor } from "../../lib/types";
import { BASKET_BG, Dot, cx } from "../ui/bits";

/**
 * The whole balance as one bar, split into what it is already promised to.
 * This is Kori's signature: the same bar on Today, in the safe card and in the lesson.
 */
export function SpokenBar({ items, legend = true, animateIn = true }: { items: SpokenFor[]; legend?: boolean; animateIn?: boolean }) {
  const { lang } = useApp();
  const reduce = useReducedMotion();
  const shown = items.filter((s) => s.amount > 0.004);
  const total = shown.reduce((a, s) => a + s.amount, 0) || 1;
  const rows = items.filter((s) => s.amount > 0.004 || s.key === "safe");

  return (
    <div>
      <motion.div
        className="flex h-3.5 w-full gap-[2px] overflow-hidden rounded-[5px]"
        initial={animateIn && !reduce ? { clipPath: "inset(0 100% 0 0)" } : false}
        animate={{ clipPath: "inset(0 0% 0 0)" }}
        transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
        role="img"
        aria-label={rows.map((s) => `${s.label} ${money(s.amount, lang)}`).join(", ")}
      >
        {shown.map((s) => (
          <div
            key={s.key}
            className={cx("h-full min-w-[3px] first:rounded-l-[5px] last:rounded-r-[5px]", BASKET_BG[s.key] || "bg-ink-3")}
            style={{
              flexGrow: s.amount / total,
              flexBasis: 0,
              backgroundImage:
                s.key === "buffer"
                  ? "repeating-linear-gradient(135deg, transparent 0 3px, oklch(0.995 0.002 95 / 0.55) 3px 5px)"
                  : undefined,
            }}
          />
        ))}
      </motion.div>
      {legend && (
        <ul className="mt-3 space-y-1.5">
          {rows.map((s) => (
            <li key={s.key} className="flex min-w-0 items-center gap-2 text-[13px] leading-[18px]">
              <Dot k={s.key} />
              <span className={cx("min-w-0 flex-1", s.key === "safe" ? "font-semibold text-ink" : "text-ink-2")}>{s.label}</span>
              <span className={cx("num shrink-0", s.key === "safe" ? "font-semibold text-ink" : "text-ink")}>{money(s.amount, lang)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
