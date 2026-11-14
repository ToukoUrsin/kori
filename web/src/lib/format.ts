import type { Lang } from "./types";

const NBSP = " ";
const MINUS = "−";

const nf: Record<string, Intl.NumberFormat> = {};
function fmt(lang: Lang, digits: number): Intl.NumberFormat {
  const k = lang + digits;
  return (nf[k] ??= new Intl.NumberFormat(lang === "fi" ? "fi-FI" : "en-GB", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }));
}

/** Split a money value into the parts the UI styles separately. */
export function moneyParts(v: number, lang: Lang, cents = false): { sign: string; whole: string; frac: string } {
  const abs = Math.abs(v);
  const s = fmt(lang, cents ? 2 : 0).format(abs).replace(/[   ]/g, NBSP);
  const sep = lang === "fi" ? "," : ".";
  const [whole, frac] = cents ? s.split(sep) : [s, ""];
  const isZero = cents ? abs < 0.005 : Math.round(abs) === 0;
  return { sign: v < 0 && !isZero ? MINUS : "", whole, frac: frac ? sep + frac : "" };
}

/** Finnish `1 094 €`, English `€1,094`. Cents only when asked. */
export function money(v: number | null | undefined, lang: Lang, opts: { cents?: boolean; sign?: boolean } = {}): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const p = moneyParts(v, lang, !!opts.cents);
  const sign = p.sign || (opts.sign && v > 0 ? "+" : "");
  return lang === "fi" ? `${sign}${p.whole}${p.frac}${NBSP}€` : `${sign}€${p.whole}${p.frac}`;
}

export function num(v: number, lang: Lang, digits = 0): string {
  return fmt(lang, digits).format(v).replace(/[  ]/g, NBSP).replace("-", MINUS);
}

export function pct(v: number, lang: Lang): string {
  return lang === "fi" ? `${num(v, lang)}${NBSP}%` : `${num(v, lang)}%`;
}

function parse(d: string): Date {
  // dates from the API are plain days; keep them in UTC so no timezone can shift them
  const [y, m, day] = d.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(y, (m || 1) - 1, day || 1));
}

const df: Record<string, Intl.DateTimeFormat> = {};
function dfmt(lang: Lang, key: string, o: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const k = lang + key;
  return (df[k] ??= new Intl.DateTimeFormat(lang === "fi" ? "fi-FI" : "en-GB", { ...o, timeZone: "UTC" }));
}

/** `15 Oct` / `15.10.` */
export function day(d: string, lang: Lang): string {
  if (lang === "fi") {
    const x = parse(d);
    return `${x.getUTCDate()}.${x.getUTCMonth() + 1}.`;
  }
  return dfmt(lang, "d", { day: "numeric", month: "short" }).format(parse(d));
}

/** `Mon 21 Sep` / `ma 21.9.` */
export function weekday(d: string, lang: Lang): string {
  const wd = dfmt(lang, "wd", { weekday: "short" }).format(parse(d));
  return `${wd} ${day(d, lang)}`;
}

/** `21 September 2026` / `21. syyskuuta 2026` */
export function longDate(d: string, lang: Lang): string {
  return dfmt(lang, "long", { day: "numeric", month: "long", year: "numeric" }).format(parse(d));
}

/** `September 2026` / `syyskuu 2026` from `2026-09` */
export function monthName(m: string, lang: Lang, withYear = true): string {
  const s = dfmt(lang, withYear ? "my" : "m", withYear ? { month: "long", year: "numeric" } : { month: "long" }).format(parse(m + "-01"));
  return lang === "fi" ? s : s.charAt(0).toUpperCase() + s.slice(1);
}

/** `Sep` / `syys` from `2026-09` */
export function monthShort(m: string, lang: Lang): string {
  const s = dfmt(lang, "ms", { month: "short" }).format(parse(m + "-01"));
  return s.replace(".", "");
}

export function daysBetween(a: string, b: string): number {
  return Math.round((parse(b).getTime() - parse(a).getTime()) / 86400000);
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** "fast_food" → "Fast food", for keys the API sends without a label. */
export function humanize(key: string): string {
  const s = key.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
