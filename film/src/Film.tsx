import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {lines, vo, voEnd, type VoLine} from './data';
import {End, Hook, Title} from './scenes/Open';
import {Fit, MathScene, Proof, Teach} from './scenes/Explain';
import {Voice, voiceDur} from './scenes/Voice';
import {C, FPS, SANS, clamp} from './theme';

// The film (1920×1080, 30 fps, under two minutes). A scene lasts as long as its narration, plus a breath.
const after = (scene: string, tail: number, min = 0) => Math.max(Math.round(min * FPS), Math.ceil((voEnd(scene) + tail) * FPS));
export const SCENES: {id: string; dur: number; C: React.FC<{dur: number}>}[] = [
	{id: 'hook', dur: after('hook', 1.3), C: Hook},
	{id: 'title', dur: after('title', 0.7), C: Title},
	{id: 'voice', dur: voiceDur(), C: Voice},
	{id: 'math', dur: after('math', 1.0), C: MathScene},
	{id: 'proof', dur: after('proof', 1.1), C: Proof},
	{id: 'teach', dur: after('teach', 1.0), C: Teach},
	{id: 'fit', dur: after('fit', 1.0), C: Fit},
	{id: 'end', dur: after('end', 2.6, 6), C: End},
];
export const starts = () => {
	let t = 0;
	return SCENES.map((s) => {
		const o = {...s, from: t};
		t += s.dur;
		return o;
	});
};
export const TOTAL = SCENES.reduce((a, s) => a + s.dur, 0);
const lineFrom = (l: VoLine) => starts().find((s) => s.id === l.scene)!.from + Math.round(l.at * FPS);

// Burned-in captions: the narration, a few words at a time, timed by the speech itself.
const chunks = (l: VoLine) => {
	type Wd = (typeof l.words)[number];
	const res: {text: string; s: number; e: number}[] = [];
	const len = (ws: Wd[]) => ws.map((w) => w.w).join(' ').length;
	const push = (ws: Wd[]) => ws.length && res.push({text: ws.map((w) => w.w).join(' '), s: ws[0].s, e: ws[ws.length - 1].e});
	const split = (ws: Wd[]) => {
		if (len(ws) <= 46 || ws.length < 4) return push(ws);
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
// a line that is already the headline on screen is not captioned twice
const onScreen = (l: VoLine) => /balance is not your budget/.test(l.text);
const Captions: React.FC = () => {
	const frame = useCurrentFrame();
	for (const l of vo.lines) {
		if (onScreen(l)) continue;
		const from = lineFrom(l);
		for (const c of chunks(l)) {
			const a = from + c.s * FPS - 2, b = from + c.e * FPS + 7;
			if (frame >= a && frame < b) {
				const op = Math.min(interpolate(frame, [a, a + 4], [0, 1], clamp), interpolate(frame, [b - 4, b], [1, 0], clamp));
				return (
					<div style={{position: 'absolute', left: 0, right: 0, top: 986, display: 'flex', justifyContent: 'center', opacity: op}}>
						<div style={{fontFamily: SANS, fontSize: 34, fontWeight: 500, color: 'oklch(0.972 0.006 95)', padding: '10px 26px', borderRadius: 14, background: 'oklch(0.22 0.02 160 / 0.92)', letterSpacing: '-0.01em'}}>{c.text}</div>
					</div>
				);
			}
		}
	}
	return null;
};

// the music sits under the narrator and almost leaves for the real conversation
const musicVol = (f: number) => {
	const st = starts();
	const v = st.find((s) => s.id === 'voice')!;
	const fade = interpolate(f, [0, 20], [0, 1], clamp) * interpolate(f, [TOTAL - 80, TOTAL - 4], [1, 0], clamp);
	const talk = vo.lines.some((l) => f >= lineFrom(l) - 8 && f <= lineFrom(l) + l.dur * FPS + 8);
	const inVoice = interpolate(f, [v.from - 12, v.from + 10, v.from + v.dur - 14, v.from + v.dur + 6], [1, 0.16, 0.16, 1], clamp);
	return fade * (talk ? 0.1 : 0.22) * inVoice;
};

export const Film: React.FC<{audio?: boolean; captions?: boolean}> = ({audio = true, captions = true}) => (
	<AbsoluteFill style={{background: C.ground}}>
		{starts().map((s) => (
			<Sequence key={s.id} from={s.from} durationInFrames={s.dur} name={s.id}>
				<s.C dur={s.dur} />
			</Sequence>
		))}
		{captions ? <Captions /> : null}
		{audio
			? vo.lines.map((l, i) => (
					<Sequence key={i} from={lineFrom(l)} durationInFrames={Math.ceil(l.dur * FPS) + 6} name={`vo ${i}`}>
						<Audio src={staticFile(l.file)} />
					</Sequence>
				))
			: null}
		{audio ? <Audio src={staticFile('audio/music.mp3')} volume={musicVol} /> : null}
	</AbsoluteFill>
);

// every narrator line must end inside its scene
for (const s of starts()) {
	for (const l of lines(s.id)) if ((l.at + l.dur) * FPS > s.dur - 4) throw new Error(`"${l.text.slice(0, 40)}" runs past scene ${s.id}`);
}
if (TOTAL > 120 * FPS) throw new Error(`the film is ${(TOTAL / FPS).toFixed(1)} s: over two minutes`);
