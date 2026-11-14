import { useEffect, useState } from "react";
import { strings } from "../lab/strings";
import type { Lang } from "./types";

/** The suggested questions: one list, one fetch per customer and language, shared by the chat, the ask bar and the stage. */
const cache = new Map<string, Promise<string[]>>();
const done = new Map<string, string[]>();

function load(customer: string, lang: Lang): Promise<string[]> {
  const key = `${customer}|${lang}`;
  let p = cache.get(key);
  if (!p) {
    p = fetch(`/api/lab/starters?customer=${encodeURIComponent(customer)}&lang=${lang}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("starters"))))
      .then((data: { items?: { text: string }[] }) => {
        const items = (data.items || []).map((item) => item.text).filter(Boolean);
        if (!items.length) throw new Error("starters");
        return items;
      })
      .catch(() => {
        cache.delete(key); // try again next time; the written list stands in meanwhile
        return strings[lang].starter;
      })
      .then((items) => {
        done.set(key, items);
        return items;
      });
    cache.set(key, p);
  }
  return p;
}

/** All suggested questions for this customer, or undefined while they load. */
export function useStarters(customer: string, lang: Lang): string[] | undefined {
  const key = `${customer}|${lang}`;
  const [state, setState] = useState<{ key: string; items?: string[] }>(() => ({ key, items: done.get(key) }));
  useEffect(() => {
    let alive = true;
    setState((s) => (s.key === key ? s : { key, items: done.get(key) }));
    void load(customer, lang).then((items) => alive && setState({ key, items }));
    return () => {
      alive = false;
    };
  }, [customer, lang, key]);
  return state.key === key ? state.items : done.get(key);
}
