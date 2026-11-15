import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

const cache = new Map<string, unknown>();
const inflight = new Map<string, Promise<void>>();

/** Fetch into the cache once; a second ask for the same key while it is on the way shares the first. */
export function warm<T>(key: string, fn: () => Promise<T>): Promise<void> {
  if (cache.has(key)) return Promise.resolve();
  let p = inflight.get(key);
  if (!p) {
    p = fn().then((data) => void cache.set(key, data), () => undefined).finally(() => inflight.delete(key));
    inflight.set(key, p);
  }
  return p;
}

export function prefetch<T>(key: string, scope: string, fn: () => Promise<T>): void {
  void scope;
  void warm(key, fn);
}

export function invalidate(prefix?: string) {
  if (!prefix) return cache.clear();
  for (const k of [...cache.keys()]) if (k.startsWith(prefix)) cache.delete(k);
}

export interface Query<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
  reload: () => void;
  setData: (d: T) => void;
}

/**
 * Tiny stale-while-revalidate fetch hook.
 * `key` identifies the request; `scope` is the part that makes old data wrong to show (the customer).
 * Within one scope the previous data stays on screen while the next loads, so nothing flashes.
 */
export function useQuery<T>(key: string | null, scope: string, fn: () => Promise<T>): Query<T> {
  const [state, setState] = useState<{ data?: T; error?: Error; loading: boolean; scope: string }>(() => ({
    data: key ? (cache.get(key) as T | undefined) : undefined,
    loading: !!key,
    scope,
  }));
  const [nonce, setNonce] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const keyRef = useRef(key);
  keyRef.current = key;

  useEffect(() => {
    if (!key) {
      setState({ loading: false, scope });
      return;
    }
    let alive = true;
    const cached = cache.get(key) as T | undefined;
    setState((s) => ({ data: cached ?? (s.scope === scope ? s.data : undefined), loading: true, scope, error: undefined }));
    let timer: ReturnType<typeof setTimeout> | undefined;
    const run = (attempt: number) => {
      fnRef.current().then(
        (d) => {
          cache.set(key, d);
          if (alive) setState({ data: d, loading: false, scope });
        },
        (e: unknown) => {
          if (!alive) return;
          // a dropped connection (not an answer from the API) gets one quiet second try; a request that hung
          // has had its second try already
          const hung = e instanceof Error && e.name === "AbortError";
          if (attempt === 0 && !(e instanceof ApiError) && !hung) {
            timer = setTimeout(() => run(1), 700);
            return;
          }
          setState((s) => ({ data: s.data, error: e instanceof Error ? e : new Error(String(e)), loading: false, scope }));
        },
      );
    };
    run(0);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [key, scope, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const setData = useCallback(
    (d: T) => {
      if (keyRef.current) cache.set(keyRef.current, d);
      setState((s) => ({ ...s, data: d, error: undefined }));
    },
    [],
  );

  // data from another scope must never render, even for one frame
  const data = state.scope === scope ? state.data : undefined;
  return { data, error: state.error, loading: state.loading || state.scope !== scope, reload, setData };
}
