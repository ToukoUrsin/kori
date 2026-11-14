import { animate, useReducedMotion } from "motion/react";
import {
  Coffee,
  HeartPulse,
  House,
  Plane,
  RotateCcw,
  ShoppingBag,
  ShoppingBasket,
  Ticket,
  TramFront,
  Wrench,
  Zap,
  CircleDot,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { money, moneyParts } from "../../lib/format";
import { useApp } from "../../lib/store";
import type { BasketKey, Lang } from "../../lib/types";

export function cx(...a: (string | false | null | undefined)[]): string {
  return a.filter(Boolean).join(" ");
}

/* ------------------------------------------------------------------ buttons */

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "quiet";
  size?: "md" | "sm";
  block?: boolean;
};

export function Button({ variant = "secondary", size = "md", block, className, children, ...rest }: BtnProps) {
  return (
    <button
      type="button"
      {...rest}
      className={cx(
        "inline-flex select-none items-center justify-center gap-2 rounded-[10px] font-medium transition-[background-color,border-color,color,transform,opacity] duration-150 active:scale-[0.985] disabled:opacity-45 disabled:active:scale-100",
        size === "md" ? "h-11 px-4 text-[15px]" : "h-9 px-3 text-[13px] relative after:absolute after:-inset-y-1 after:inset-x-0",
        block && "w-full",
        variant === "primary" && "bg-brand text-white hover:bg-brand-strong",
        variant === "secondary" && "border border-line-strong bg-surface text-ink hover:border-ink-3",
        variant === "ghost" && "text-ink-2 hover:bg-sunk hover:text-ink",
        variant === "quiet" && "bg-sunk text-ink hover:bg-line",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function IconButton({
  label,
  children,
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      {...rest}
      className={cx(
        "inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-ink-2 transition-colors duration-150 hover:bg-sunk hover:text-ink active:bg-line disabled:opacity-40",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Chip({ children, className, wrap, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { /** long text may run to a second line */ wrap?: boolean }) {
  return (
    <button
      type="button"
      {...rest}
      className={cx(
        "relative inline-flex items-center gap-1.5 border border-line-strong bg-surface px-3.5 text-[13px] font-medium text-ink transition-[border-color,background-color,transform] duration-150 after:absolute after:-inset-y-1 after:inset-x-0 hover:border-ink-3 active:scale-[0.98] disabled:opacity-50",
        wrap ? "min-h-9 max-w-full rounded-[18px] py-1.5 text-left leading-[18px]" : "h-9 shrink-0 whitespace-nowrap rounded-full",
        className,
      )}
    >
      {children}
    </button>
  );
}

/** One of a few: a row of equal buttons, the chosen one raised. */
export function Segmented<K extends string>({
  options,
  value,
  onChange,
  label,
  disabled,
  className,
}: {
  options: { key: K; label: ReactNode }[];
  value: K | null;
  onChange: (k: K) => void;
  label: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <div role="group" aria-label={label} className={cx("flex rounded-[12px] bg-sunk p-[3px]", className)}>
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          aria-pressed={value === o.key}
          disabled={disabled}
          onClick={() => value !== o.key && onChange(o.key)}
          className={cx(
            "flex h-11 min-w-0 flex-1 items-center justify-center gap-1.5 rounded-[9px] px-2 text-[13px] font-medium transition-[background-color,color,box-shadow] duration-150 disabled:opacity-60",
            value === o.key ? "bg-surface text-ink shadow-[0_1px_2px_oklch(0.22_0.02_160/0.16)]" : "text-ink-2 hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- loading */

export function Skel({ className }: { className?: string }) {
  return <div className={cx("skel", className)} aria-hidden />;
}

export function ErrorInline({ onRetry, message, className }: { onRetry?: () => void; message?: string; className?: string }) {
  const { t } = useApp();
  return (
    <div role="alert" className={cx("flex items-center gap-3 rounded-card border border-line bg-surface px-4 py-3", className)}>
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-medium text-ink">{message || t("common.loadError")}</p>
        <p className="text-[13px] leading-[18px] text-ink-3">{t("common.loadErrorHint")}</p>
      </div>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          <RotateCcw size={14} strokeWidth={2} aria-hidden />
          {t("common.retry")}
        </Button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ money */

/** Tween a number when it changes. Returns the value to render. */
export function useTween(value: number, opts: { duration?: number; from?: number } = {}): number {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(opts.from ?? value);
  const cur = useRef(opts.from ?? value);
  useEffect(() => {
    if (reduce || cur.current === value) {
      cur.current = value;
      setShown(value);
      return;
    }
    const c = animate(cur.current, value, {
      duration: opts.duration ?? 0.45,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => {
        cur.current = v;
        setShown(v);
      },
    });
    return () => c.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, reduce]);
  return shown;
}

/** Money that ticks to its new value. Negative amounts turn red; nothing else does. */
export function Money({
  value,
  cents,
  sign,
  tween = true,
  className,
}: {
  value: number;
  cents?: boolean;
  sign?: boolean;
  tween?: boolean;
  className?: string;
}) {
  const { lang } = useApp();
  const v = useTween(value, { duration: tween ? 0.45 : 0 });
  return <span className={cx("num", value < -0.004 && "text-neg", className)}>{money(tween ? v : value, lang, { cents, sign })}</span>;
}

/** The hero figure: euros large, cents small. Counts up once. */
export function BigMoney({ value, lang, className, countUp }: { value: number; lang: Lang; className?: string; countUp?: boolean }) {
  const v = useTween(value, { duration: 0.9, from: countUp ? 0 : undefined });
  const p = moneyParts(v, lang, true);
  const neg = value < -0.004;
  return (
    <span className={cx("num inline-flex items-baseline", neg && "text-neg", className)} aria-label={money(value, lang, { cents: true })}>
      <span aria-hidden>
        {p.sign}
        {lang === "en" && "€"}
        {p.whole}
      </span>
      <span aria-hidden className="text-[0.46em] font-medium tracking-normal text-ink-3">
        {p.frac}
        {lang === "fi" && " €"}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------- baskets etc */

export const BASKET_BG: Record<string, string> = {
  fixed: "bg-fixed",
  surprise: "bg-surprise",
  everyday: "bg-everyday",
  saving: "bg-saving",
  cushion: "bg-cushion",
  safe: "bg-brand",
  buffer: "bg-brand-line",
};
export const BASKET_VAR: Record<string, string> = {
  fixed: "var(--color-fixed)",
  surprise: "var(--color-surprise)",
  everyday: "var(--color-everyday)",
  saving: "var(--color-saving)",
  cushion: "var(--color-cushion)",
  safe: "var(--color-brand)",
  buffer: "var(--color-brand-line)",
};
export const BASKET_SOFT: Record<BasketKey, string> = {
  fixed: "bg-fixed-soft",
  surprise: "bg-surprise-soft",
  everyday: "bg-everyday-soft",
};

export function Dot({ k, className }: { k: string; className?: string }) {
  return <span aria-hidden className={cx("inline-block h-2.5 w-2.5 shrink-0 rounded-[3px]", BASKET_BG[k] || "bg-ink-3", className)} />;
}

const ICONS: Record<string, LucideIcon> = {
  home: House,
  bolt: Zap,
  heart: HeartPulse,
  wrench: Wrench,
  basket: ShoppingBasket,
  cup: Coffee,
  tram: TramFront,
  ticket: Ticket,
  bag: ShoppingBag,
  plane: Plane,
};
export function CatIcon({ icon, size = 16, className }: { icon?: string; size?: number; className?: string }) {
  const I = (icon && ICONS[icon]) || CircleDot;
  return <I size={size} strokeWidth={1.75} className={className} aria-hidden />;
}

/* ------------------------------------------------------------------ layout */

export function SectionHead({ title, action, sub }: { title: string; action?: ReactNode; sub?: string }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <div className="min-w-0">
        {/* one step above the 15px titles inside cards, so a section never reads at the same level as its content */}
        <h2 className="text-[17px] font-semibold leading-[22px] tracking-[-0.015em] text-ink">{title}</h2>
        {sub && <p className="mt-0.5 text-[13px] leading-[18px] text-ink-2">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

/** The last non-empty value, so a sheet keeps its content while it slides away. */
export function useLast<T>(v: T | null | undefined): T | null {
  const ref = useRef<T | null>(v ?? null);
  if (v !== null && v !== undefined) ref.current = v;
  return v ?? ref.current;
}

/** Width of an element, for SVG charts drawn in real pixels. */
export function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.clientWidth);
    const ro = new ResizeObserver(() => setW(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

/** Expand/collapse without layout jumps. */
export function Collapse({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <div
      className="grid transition-[grid-template-rows,opacity] duration-[240ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
      style={{ gridTemplateRows: open ? "1fr" : "0fr", opacity: open ? 1 : 0 }}
      aria-hidden={!open}
      inert={!open}
    >
      <div className="min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}

export function LangToggle({ className }: { className?: string }) {
  const { lang, setLang, t } = useApp();
  return (
    <div role="group" aria-label={t("common.language")} className={cx("inline-flex h-9 items-center rounded-full bg-sunk p-0.5", className)}>
      {(["en", "fi"] as const).map((l) => (
        <button
          key={l}
          type="button"
          aria-pressed={lang === l}
          onClick={() => setLang(l)}
          className={cx(
            "relative h-8 min-w-11 rounded-full px-2.5 text-[12px] font-semibold uppercase tracking-[0.04em] transition-colors duration-150 after:absolute after:-inset-y-1.5 after:inset-x-0",
            lang === l ? "bg-surface text-ink shadow-[0_1px_2px_oklch(0.22_0.02_160/0.14)]" : "text-ink-3 hover:text-ink",
          )}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

/** The Kori mark: three bars. Also the voice mark; `levels` (0..1) make it move. */
export function Mark({ size = 20, className, levels }: { size?: number; className?: string; levels?: number[] }) {
  const h = [0.55, 1, 0.42];
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" className={className} aria-hidden>
      {h.map((v, i) => {
        const hh = 14 * (levels ? levels[i] ?? v : v);
        return <rect key={i} x={3.5 + i * 5} y={17 - hh} width={3} height={hh} rx={1.5} fill="currentColor" />;
      })}
    </svg>
  );
}
