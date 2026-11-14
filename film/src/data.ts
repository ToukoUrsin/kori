import capsJson from './data/caps.json';
import voJson from './data/vo.json';
import homeJson from './data/home.json';
import backtestJson from './data/backtest.json';
import monthsJson from './data/backtest-months.json';

export type Word = {w: string; s: number; e: number};
export type Said = {who: 'user' | 'coach'; kind: string; text: string; file?: string; lufs?: number; s: number; e: number; words: Word[]};
export type Box = {x: number; y: number; width: number; height: number};
export type Cap = {
	seconds: number;
	lang: string;
	video: string;
	events: {at: number; kind: string; label?: string; text?: string; box?: Box | null}[];
	screen: {at: number; name: string; data: string}[];
	said: Said[];
	coach?: {file: string; start: number; lufs?: number};
};
export type VoLine = {scene: string; at: number; text: string; file: string | null; pending?: boolean; dur: number; words: Word[]};

export const caps = capsJson as unknown as Record<string, Cap>;
export const vo = voJson as unknown as {voice: string; lines: VoLine[]};
export const home = homeJson as unknown as {
	safe: {amount: number; per_day: number; this_week: number; days_to_payday: number; next_payday: string; balance: number; spoken_for: {key: string; label: string; amount: number}[]};
	baskets: {baskets: {key: string; label: string; amount: number; usual: number}[]};
};
export const backtest = backtestJson as unknown as {cases: number; customers: number; promise: {cases: number; safe_held_pct: number; balance_as_budget_held_pct: number}};

/** The backtest of docs/backtest.json, month by month (scripts/backtest-months.py). */
export const btMonths = monthsJson as unknown as {
	cases: number;
	customers: number;
	promise: {cases: number; safe_held_pct: number; balance_as_budget_held_pct: number};
	months: {month: string; cases: number; cases_total: number; customers_total: number; promise_cases_total: number; safe_held_pct_total: number; balance_held_pct_total: number}[];
};
/** JSON the recorder cut short (it keeps 600 characters of a card): the longest prefix that parses, closed. */
const parsePrefix = (s: string): any => {
	try {
		return JSON.parse(s);
	} catch {
		/* cut short: close it at the last complete value */
	}
	const stack: string[] = [];
	const cuts: {i: number; close: string}[] = [];
	let str = false;
	for (let i = 0; i < s.length; i++) {
		const ch = s[i];
		if (str) {
			if (ch === '\\') i++;
			else if (ch === '"') str = false;
			continue;
		}
		if (ch === '"') str = true;
		else if (ch === '{' || ch === '[') stack.push(ch === '{' ? '}' : ']');
		else if (ch === '}' || ch === ']') stack.pop();
		else if (ch === ',') cuts.push({i, close: [...stack].reverse().join('')});
	}
	for (let k = cuts.length - 1; k >= 0; k--) {
		try {
			return JSON.parse(s.slice(0, cuts[k].i) + cuts[k].close);
		} catch {
			/* try an earlier cut */
		}
	}
	return null;
};
/** The data of the first card of `type` a recording showed (as the app received it; the fields the log kept). */
export const cardOf = (cap: Cap, type: string): Record<string, any> | null => {
	for (const e of cap.screen) {
		if (e.name !== 'card') continue;
		const c = parsePrefix(e.data)?.card;
		if (c?.type === type) return {...c.data, at: e.at};
	}
	return null;
};
/** The screen events of a recording ("status": the calculation picked, "done": how many numbers were checked). */
export const screenOf = (cap: Cap, name: string) =>
	cap.screen.filter((e) => e.name === name).map((e) => {
		try {
			return {at: e.at, ...JSON.parse(e.data)};
		} catch {
			return {at: e.at};
		}
	});

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
