import React from 'react';
import type {Word} from './data';
import {SANS} from './theme';

// Burned-in captions: the narrator, a few words at a time, timed by the speech itself.
export const chunks = (l: {words: Word[]}) => {
	type Wd = (typeof l.words)[number];
	const res: {text: string; s: number; e: number}[] = [];
	const len = (ws: Wd[]) => ws.map((w) => w.w).join(' ').length;
	const push = (ws: Wd[]) => ws.length && res.push({text: ws.map((w) => w.w).join(' '), s: ws[0].s, e: ws[ws.length - 1].e});
	const split = (ws: Wd[]) => {
		if (len(ws) <= 40 || ws.length < 4) return push(ws);
		let best = Math.floor(ws.length / 2), bestScore = 1e9;
		for (let i = 2; i <= ws.length - 2; i++) {
			const score = Math.abs(len(ws.slice(0, i)) - len(ws.slice(i))) - (/[,:;]$/.test(ws[i - 1].w) ? 14 : 0);
			if (score < bestScore) (bestScore = score), (best = i);
		}
		split(ws.slice(0, best));
		split(ws.slice(best));
	};
	let cur: Wd[] = [];
	for (const w of l.words) {
		cur.push(w);
		if (/[.?!]$/.test(w.w)) {
			split(cur);
			cur = [];
		}
	}
	split(cur);
	return res;
};
export const CaptionBox: React.FC<{text: string; op: number; x: [number, number]}> = ({text, op, x}) => (
	<div style={{position: 'absolute', left: x[0], width: x[1] - x[0], bottom: 39, display: 'flex', justifyContent: 'center', opacity: op}}>
		<div style={{fontFamily: SANS, fontSize: 44, fontWeight: 500, lineHeight: 1.2, color: 'oklch(0.972 0.006 95)', padding: '10px 28px', borderRadius: 16, background: 'oklch(0.22 0.02 160 / 0.92)', letterSpacing: '-0.012em', textAlign: 'center'}}>{text}</div>
	</div>
);
