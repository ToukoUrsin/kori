#!/usr/bin/env node
// The cut of Touko's voice take: which parts of the take are kept, and where each lands in the film.
//   node scripts/take-plan.mjs            -> src/data/take-plan.json  (read by src/Take.tsx and scenarios/t-*.mjs)
// Cuts sit in the silences of the take's own audio (ffmpeg silencedetect), never inside a word. Long pauses are
// tightened to PAUSE seconds; picture and sound are cut together, nothing is sped up.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const film = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WAV = process.env.TAKE_WAV || '/bulk3/runs/spankki/film2/take/take.wav';
const r = spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-i', WAV, '-af', 'silencedetect=noise=-38dB:d=0.25', '-f', 'null', '-'], {encoding: 'utf8'});
const starts = [...r.stderr.matchAll(/silence_start: ([\d.]+)/g)].map((m) => Number(m[1]));
const ends = [...r.stderr.matchAll(/silence_end: ([\d.]+)/g)].map((m) => Number(m[1]));
const silences = starts.map((s, i) => ({s, e: ends[i] ?? 1e9})).filter((x) => x.e - x.s >= 0.25);

// ---- what is kept (take seconds). Dropped: the hello (0 to 5.8), the false start (101.6 to 107.3), the tail.
const KEEP = [[5.6, 16.5], [21.4, 101.75], [107.3, 118.3]];
// pauses longer than LONG are tightened to this; the first line is left as spoken (it plays over the cold open)
const LONG = 0.62, PAUSE = 0.56, PAUSE_MID = 0.5;
const MID = [84.8, 88.5, 26.5, 46.1, 50.1, 9.5, 114.1];         // long pauses inside a sentence (take second, ±0.4)
const HOLD = {'65.1': 0.95};                                               // silence start (1 decimal) -> seconds to keep instead
const isMid = (s) => MID.some((m) => Math.abs(m - s) < 0.4);

const parts = [];     // {from, to} in take seconds, played back to back within a block
for (const [a, b] of KEEP) {
	let at = a;
	for (const sil of silences) {
		if (sil.e <= a || sil.s >= b) continue;
		const d = sil.e - sil.s;
		if (sil.s < a + 0.3 || sil.e > b - 0.3) continue;      // the edge of the block
		const want = HOLD[sil.s.toFixed(1)] ?? (a < 6 ? d : d > LONG ? (isMid(sil.s) ? PAUSE_MID : PAUSE) : d);
		if (want >= d - 0.04) continue;
		parts.push({from: at, to: sil.s + want / 2, block: KEEP.findIndex((k) => k[0] === a)});
		at = sil.e - want / 2;
	}
	parts.push({from: at, to: b, block: KEEP.findIndex((k) => k[0] === a)});
}
// block edges: start a breath before the first word, end a breath after the last
const firstWord = (a) => silences.find((x) => x.s <= a + 0.3 && x.e > a)?.e ?? a;
const lastWord = (b) => silences.find((x) => x.e >= b - 0.3 && x.s < b)?.s ?? b;
for (const [i, [a, b]] of KEEP.entries()) {
	const ps = parts.filter((p) => p.block === i);
	ps[0].from = Math.max(a, firstWord(a) - 0.12);
	ps.at(-1).to = Math.min(b, lastWord(b) + 0.2);
}
const out = {wav: WAV, silences, parts: parts.map((p) => ({from: +p.from.toFixed(3), to: +p.to.toFixed(3), block: p.block}))};
const len = (i) => out.parts.filter((p) => p.block === i).reduce((s, p) => s + p.to - p.from, 0);
out.blockSeconds = KEEP.map((_, i) => +len(i).toFixed(3));
out.cutSeconds = +KEEP.reduce((s, [a, b], i) => s + (out.parts.filter((p) => p.block === i).at(-1).to - out.parts.find((p) => p.block === i).from) - len(i), 0).toFixed(3);
fs.writeFileSync(path.join(film, 'src/data/take-plan.json'), JSON.stringify(out, null, 1));
console.log(`${out.parts.length} parts, blocks ${out.blockSeconds.join(' + ')} s, ${out.cutSeconds} s of pauses taken out`);
for (const p of out.parts) console.log(`  ${p.from.toFixed(2).padStart(7)} – ${p.to.toFixed(2).padStart(7)}  (${(p.to - p.from).toFixed(2)})`);
