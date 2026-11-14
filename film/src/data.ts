import capsJson from './data/caps.json';
import voJson from './data/vo.json';
import homeJson from './data/home.json';
import backtestJson from './data/backtest.json';

export type Word = {w: string; s: number; e: number};
export type Said = {who: 'user' | 'coach'; kind: string; text: string; file?: string; s: number; e: number; words: Word[]};
export type Box = {x: number; y: number; width: number; height: number};
export type Cap = {
	seconds: number;
	lang: string;
	video: string;
	events: {at: number; kind: string; label?: string; text?: string; box?: Box | null}[];
	screen: {at: number; name: string; data: string}[];
	said: Said[];
	coach?: {file: string; start: number};
};
export type VoLine = {scene: string; at: number; text: string; file: string; dur: number; words: Word[]};

export const caps = capsJson as unknown as Record<string, Cap>;
export const vo = voJson as unknown as {voice: string; lines: VoLine[]};
export const home = homeJson as unknown as {
	safe: {amount: number; per_day: number; this_week: number; days_to_payday: number; next_payday: string; balance: number; spoken_for: {key: string; label: string; amount: number}[]};
	baskets: {baskets: {key: string; label: string; amount: number; usual: number}[]};
};
export const backtest = backtestJson as unknown as {cases: number; customers: number; promise: {cases: number; safe_held_pct: number; balance_as_budget_held_pct: number}};

const norm = (w: string) => w.toLowerCase().replace(/[^a-z0-9]/g, '');
export const lines = (scene: string) => vo.lines.filter((l) => l.scene === scene);
/** when line `i` of a scene starts, in seconds from the scene start */
export const lineAt = (scene: string, i: number) => lines(scene)[i]?.at ?? 0;
/** when the narrator says a word (its first letters) in line `i` */
export const cue = (scene: string, i: number, word: string, nth = 0) => {
	const l = lines(scene)[i];
	if (!l) return 0;
	const w = l.words.filter((x) => norm(x.w).startsWith(word))[nth];
	if (!w) throw new Error(`"${word}" is not in: ${l.text}`);
	return l.at + w.s;
};
export const voEnd = (scene: string) => Math.max(0, ...lines(scene).map((l) => l.at + l.dur));
