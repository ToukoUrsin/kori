import { useSyncExternalStore } from "react";
import type { Lang } from "./types";

export const BRIDGE_VERSION = 1 as const;

export interface HostConsent {
  transactions: boolean;
  other_bank: boolean;
}

export interface HostInit {
  v: typeof BRIDGE_VERSION;
  customer: string;
  lang: Lang;
  consent: HostConsent;
  theme?: "light";
}

export type HostToKori =
  | { type: "kori:init"; v: typeof BRIDGE_VERSION; customer: string; lang: Lang; consent: HostConsent; theme?: "light" }
  | { type: "kori:consent"; v: typeof BRIDGE_VERSION; consent: HostConsent }
  | { type: "kori:ask"; v: typeof BRIDGE_VERSION; question: string }
  | { type: "kori:open"; v: typeof BRIDGE_VERSION; screen: "coach" | "home" };

export type KoriToHost =
  | { type: "kori:ready"; v: typeof BRIDGE_VERSION }
  | { type: "kori:safe"; v: typeof BRIDGE_VERSION; amount: number; per_day: number; days_to_payday: number; next_payday: string; status: string }
  | { type: "kori:navigate"; v: typeof BRIDGE_VERSION; screen: "coach" | "home" }
  | { type: "kori:request"; v: typeof BRIDGE_VERSION; what: "link_other_bank" }
  | { type: "kori:event"; v: typeof BRIDGE_VERSION; name: string }
  | { type: "kori:close"; v: typeof BRIDGE_VERSION };

export type BridgeMessage = HostToKori | KoriToHost;

function isLang(v: unknown): v is Lang {
  return v === "en" || v === "fi";
}

function isConsent(v: unknown): v is HostConsent {
  return !!v && typeof v === "object" && typeof (v as HostConsent).transactions === "boolean" && typeof (v as HostConsent).other_bank === "boolean";
}

export function isEmbedMode(): boolean {
  return typeof window !== "undefined" && new URLSearchParams(window.location.search).get("embed") === "1";
}

export function isHostToKoriMessage(v: unknown): v is HostToKori {
  if (!v || typeof v !== "object" || (v as { v?: unknown }).v !== BRIDGE_VERSION) return false;
  const m = v as Record<string, unknown>;
  if (m.type === "kori:init") return typeof m.customer === "string" && isLang(m.lang) && isConsent(m.consent);
  if (m.type === "kori:consent") return isConsent(m.consent);
  if (m.type === "kori:ask") return typeof m.question === "string";
  return m.type === "kori:open" && (m.screen === "coach" || m.screen === "home");
}

export function isKoriToHostMessage(v: unknown): v is KoriToHost {
  if (!v || typeof v !== "object" || (v as { v?: unknown }).v !== BRIDGE_VERSION) return false;
  const m = v as Record<string, unknown>;
  if (m.type === "kori:ready") return true;
  if (m.type === "kori:safe") return typeof m.amount === "number" && typeof m.per_day === "number" && typeof m.days_to_payday === "number" && typeof m.next_payday === "string" && typeof m.status === "string";
  if (m.type === "kori:navigate") return m.screen === "coach" || m.screen === "home";
  if (m.type === "kori:request") return m.what === "link_other_bank";
  if (m.type === "kori:event") return typeof m.name === "string";
  return m.type === "kori:close";
}

let hostInit: HostInit | null = null;
const hostListeners = new Set<(m: HostToKori) => void>();
const hostSnapshotListeners = new Set<() => void>();

function receiveHostMessage(event: MessageEvent) {
  if (!isEmbedMode() || event.origin !== window.location.origin || event.source !== window.parent || !isHostToKoriMessage(event.data)) return;
  const message = event.data;
  if (message.type === "kori:init") hostInit = message;
  if (message.type === "kori:consent" && hostInit) hostInit = { ...hostInit, consent: message.consent };
  for (const listener of hostListeners) listener(message);
  for (const listener of hostSnapshotListeners) listener();
}

if (typeof window !== "undefined") window.addEventListener("message", receiveHostMessage);

export function getHostInit(): HostInit | null {
  return hostInit;
}

export function subscribeHost(listener: (m: HostToKori) => void): () => void {
  hostListeners.add(listener);
  return () => hostListeners.delete(listener);
}

export function useHostInit(): HostInit | null {
  return useSyncExternalStore(
    (listener) => {
      hostSnapshotListeners.add(listener);
      return () => hostSnapshotListeners.delete(listener);
    },
    () => hostInit,
    () => null,
  );
}

export function postToHost(message: KoriToHost): void {
  if (!isEmbedMode() || window.parent === window) return;
  window.parent.postMessage(message, window.location.origin);
}

export function postToKori(frame: Window | null, message: HostToKori): void {
  if (!frame) return;
  frame.postMessage(message, window.location.origin);
}

export function makeInit(customer: string, lang: Lang, consent: HostConsent): HostToKori {
  return { type: "kori:init", v: BRIDGE_VERSION, customer, lang, consent };
}

const CONSENT_PREFIX = "kori.host.consent.";

export function readLocalConsent(customer: string): HostConsent | null {
  try {
    const raw = localStorage.getItem(CONSENT_PREFIX + customer);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    return isConsent(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function writeLocalConsent(customer: string, consent: HostConsent): void {
  try {
    localStorage.setItem(CONSENT_PREFIX + customer, JSON.stringify(consent));
  } catch {
    /* private mode */
  }
}

export interface ConsentScope {
  key: "transactions" | "other_bank";
  granted: boolean;
  required?: boolean;
  simulated?: boolean;
  label?: string;
  detail?: string;
}

export interface ConsentResponse {
  scopes: ConsentScope[];
  partial_view?: boolean;
  note?: string;
}

export async function fetchConsent(customer: string, lang: Lang): Promise<ConsentResponse | null> {
  const response = await fetch(`/api/consent?customer=${encodeURIComponent(customer)}&lang=${lang}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Consent request failed (${response.status})`);
  return (await response.json()) as ConsentResponse;
}

export async function putConsent(customer: string, lang: Lang, otherBank: boolean): Promise<ConsentResponse | null> {
  const response = await fetch("/api/consent", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ customer, lang, other_bank: otherBank }),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Consent update failed (${response.status})`);
  return (await response.json()) as ConsentResponse;
}

export function consentFromResponse(response: ConsentResponse | null): HostConsent | null {
  if (!response) return null;
  const transactions = response.scopes.find((x) => x.key === "transactions");
  const other = response.scopes.find((x) => x.key === "other_bank");
  return transactions ? { transactions: transactions.granted, other_bank: !!other?.granted } : null;
}
