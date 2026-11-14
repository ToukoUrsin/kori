import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {lines, vo, type VoLine} from './data';
import type {Clip} from './footage';
import {clipsFrames, sceneSec, spoken} from './footage';
import {Balance, End, Talk} from './scenes/Open';
import {Host, MathScene, Proof, Teach} from './scenes/Explain';
import {C, FPS, clamp} from './theme';
import {CaptionBox, chunks} from './captions';

// ================================================================ the recordings: part B edits only this table
// Each slot is the footage of one scene, by recording name (src/data/caps.json, from scripts/import-caps.mjs).
//   clips  parts of a recording, in its own seconds, played at real speed. Two parts of the same recording with a
//          gap between them are a cut: the film marks it ("4 s wait cut"). Real answers are never cut inside.
//   zoom   punch-ins: {at: recording second, z: 2, y (and x): the point to centre, in app pixels (390 × 844)}.
//   note   what a part is, under the phone where there is no live strip.
// Until the new recordings exist, the slots point at the old ones (voice2, chat, lesson, track, fi, today).
export const SLOTS: {
	voice3: {clips: Clip[]; big: {cap: string; card: string}};
	loop: {clips: Clip[]; vo: {cap: string; at: number}; beats: {cap: string; at: number}[]};
	figures: {clips: Clip[]};
	teach: {clips: Clip[]};
	lesson2: {clips: Clip[]};
	peers: {clips: Clip[]};
	host: {clips: Clip[]; beats: {cap: string; at: number; label: string}[]};
} = {
	// 1. Cold open. PART B: voice3, "Can I afford a six hundred and fifty euro phone this month?", the wait cut, the
	//    whole answer; big = the "afford" card (per_day before → after). Now: voice2's first question.
	voice3: {
		clips: [
			{cap: 'voice2', from: 15.15, to: 17.85},
			{cap: 'voice2', from: 22.35, to: 35.5, zoom: [{at: 22.35, z: 2, x: 100, y: 360}, {at: 34.9, z: 1, y: 422}]},
		],
		big: {cap: 'voice2', card: 'safe'},
	},
	// 3. The habit loop. PART B: voice3 from "How did my last pay cycle go?" (look-back card punched in), "It was
	//    unusual", the answer that sets the one thing, then the home screen with [data-loop="active"] (or `loop`).
	//    beats: when each step is seen: noticed, asked, one thing set, tracked. vo: where the narrator starts.
	loop: {
		clips: [
			{cap: 'voice2', from: 37.45, to: 40.15},
			{cap: 'voice2', from: 45.3, to: 57.7, zoom: [{at: 45.3, z: 2, x: 100, y: 390}]},
			{cap: 'today', from: 0.2, to: 4.2, mute: true, zoom: [{at: 0.2, z: 1.8, x: 100, y: 230}], note: 'The home screen · real speed'},
		],
		vo: {cap: 'today', at: 0.45},
		beats: [{cap: 'voice2', at: 37.3}, {cap: 'voice2', at: 45.4}, {cap: 'voice2', at: 50.2}, {cap: 'today', at: 0.3}],
	},
	// 4. Why the numbers are right: 3 s of "numbers checked" opened (PART B: figures). Now: the chat's checked line.
	figures: {
		clips: [{cap: 'chat', from: 25.8, to: 28.9, mute: true, zoom: [{at: 25.8, z: 2, x: 100, y: 610}], note: 'Typed answer · real speed'}],
	},
	// 6. It teaches: the baskets, then the typed eating-out what-if (both kept in part B).
	teach: {
		clips: [
			{cap: 'today', from: 9.9, to: 13.0, mute: true, zoom: [{at: 9.9, z: 1.8, x: 100, y: 190}], note: 'Three baskets, this month · real speed'},
			{cap: 'chat', from: 32.6, to: 34.9, mute: true, zoom: [{at: 32.6, z: 1.8, x: 100, y: 330}], note: 'Typed what-if · excerpt, real speed'},
		],
	},
	// PART B: lesson2, the sorting step (one wrong on purpose) and say-it-back: "Not yet", then a pass.
	lesson2: {
		clips: [
			{cap: 'lesson', from: 12.7, to: 14.9, mute: true, zoom: [{at: 12.7, z: 1.7, x: 100, y: 300}], note: 'Lesson · excerpt, real speed'},
			{cap: 'lesson', from: 21.8, to: 25.9, mute: true, zoom: [{at: 21.8, z: 1.7, x: 100, y: 330}], note: 'Lesson · excerpt, real speed'},
		],
	},
	// PART B: peers, the "people like you" card with the Statistics Finland comparison. Now: the spender profile.
	peers: {
		clips: [{cap: 'chat', from: 14.7, to: 17.9, mute: true, zoom: [{at: 14.7, z: 1.7, x: 100, y: 420}], note: 'Typed answer · real speed'}],
	},
	// 7. Inside the bank app. PART B: host, the host home, the consent sheet (2.5 s or more), Allow, Kori inside, the
	//    host's "Safe to spend" tile, one beat of Finnish. beats (each lights a line on the right when it is seen):
	//    "The bank's own home screen", "Asks before it reads anything", "Opens inside the app",
	//    "Safe to spend on the bank's home", "Suomeksi". Now: Kori's Finnish home, which shows none of the host.
	host: {
		clips: [{cap: 'fi', from: 0.3, to: 9.9, mute: true, note: 'Suomeksi · real speed'}],
		beats: [{cap: 'fi', at: 0.3, label: 'Kori in Finnish'}, {cap: 'fi', at: 1.6, label: 'Opens the coach'}, {cap: 'fi', at: 4.5, label: 'Talks in Finnish too'}],
	},
};
// ================================================================

// a scene lasts as long as its footage and its narration, plus a breath
const voEndIn = (scene: string) => Math.max(0, ...lines(scene).map((l) => l.at + l.dur));
const sec = (s: number) => Math.round(s * FPS);
const talkVo = {open: clipsFrames(SLOTS.voice3.clips) / FPS, loop: sceneSec(SLOTS.loop.clips, SLOTS.loop.vo.cap, SLOTS.loop.vo.at) ?? 0};
export const teachClips = [SLOTS.teach.clips[0], SLOTS.teach.clips[1], ...SLOTS.lesson2.clips, ...SLOTS.peers.clips];

type SceneDef = {id: string; dur: number; vo: number; C: React.FC<{dur: number}>; capX?: [number, number]};
const RIGHT: [number, number] = [860, 1824]; // clear of the live strip under the phone
export const SCENES: SceneDef[] = [
	{id: 'open', vo: talkVo.open, dur: Math.max(clipsFrames(SLOTS.voice3.clips), sec(talkVo.open + voEndIn('open') + 0.3)), C: (p) => <Talk {...p} kind="open" clips={SLOTS.voice3.clips} big={SLOTS.voice3.big} voAt={talkVo.open} />, capX: RIGHT},
	{id: 'balance', vo: 0, dur: sec(voEndIn('balance') + 0.3), C: Balance},
	{id: 'loop', vo: talkVo.loop, dur: Math.max(clipsFrames(SLOTS.loop.clips), sec(talkVo.loop + voEndIn('loop') + 0.3)), C: (p) => <Talk {...p} kind="loop" clips={SLOTS.loop.clips} beats={SLOTS.loop.beats} voAt={talkVo.loop} />, capX: RIGHT},
	{id: 'math', vo: 0, dur: sec(voEndIn('math') + 1.9), C: (p) => <MathScene {...p} figures={SLOTS.figures.clips} />, capX: RIGHT},
	{id: 'proof', vo: 0, dur: sec(voEndIn('proof') + 0.5), C: Proof},
	{id: 'teach', vo: 0, dur: Math.max(clipsFrames(teachClips), sec(voEndIn('teach') + 0.3)), C: (p) => <Teach {...p} clips={teachClips} />, capX: RIGHT},
	{id: 'host', vo: 0, dur: Math.max(clipsFrames(SLOTS.host.clips), sec(voEndIn('host') + 0.3)), C: (p) => <Host {...p} clips={SLOTS.host.clips} beats={SLOTS.host.beats} />, capX: RIGHT},
	{id: 'end', vo: 0, dur: sec(6), C: (p) => <End {...p} clips={SLOTS.host.clips} />},
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
const sceneOf = (id: string) => starts().find((s) => s.id === id)!;
const lineFrom = (l: VoLine) => sceneOf(l.scene).from + sec(sceneOf(l.scene).vo + l.at);

// what is said, when, in film frames: the narrator and the real voices (for the captions and the music)
const realSpeech = () =>
	starts().flatMap((s) => {
		const clips = s.id === 'open' ? SLOTS.voice3.clips : s.id === 'loop' ? SLOTS.loop.clips : s.id === 'teach' ? teachClips : s.id === 'host' ? SLOTS.host.clips : [];
		return spoken(clips).map((u) => ({...u, a: s.from + sec(u.s), b: s.from + sec(u.e)}));
	});
const SPEECH = [...vo.lines.filter((l) => !l.pending).map((l) => ({a: lineFrom(l), b: lineFrom(l) + sec(l.dur)})), ...realSpeech()];

// words that are already the headline on screen are not captioned twice
const ON_SCREEN = [/balance is not your budget/i, /never does the math/i, /only picks the calculation/i, /number any good/i, /money coach for young adults/i, /^kori\.?$/i];
const onScreen = (text: string) => ON_SCREEN.some((r) => r.test(text));
const CAPTIONS = (() => {
	const out: {a: number; b: number; text: string; x: [number, number]}[] = [];
	for (const l of vo.lines) {
		const sc = sceneOf(l.scene);
		const from = lineFrom(l);
		for (const c of chunks(l)) if (!onScreen(c.text)) out.push({a: from + Math.round(c.s * FPS) - 2, b: from + Math.round(c.e * FPS) + 7, text: c.text, x: sc.capX ?? [0, 1920]});
	}
	return out;
})();
const Captions: React.FC = () => {
	const frame = useCurrentFrame();
	const c = CAPTIONS.find((x) => frame >= x.a && frame < x.b);
	if (!c) return null;
	const op = Math.min(interpolate(frame, [c.a, c.a + 4], [0, 1], clamp), interpolate(frame, [c.b - 4, c.b], [1, 0], clamp));
	return <CaptionBox text={c.text} op={op} x={c.x} />;
};

// The music: about 18 dB under speech, up when nobody talks, a lift into the proof, its own ending at the film's end.
// The track's last hit is at 111.0 s and it has died away by 112.4 s: it is placed so that the hit lands 1.2 s before
// the end (if the film is longer than that, the music starts a little late instead).
const MUSIC_HIT = 111.0;
const musicStart = MUSIC_HIT - (TOTAL / FPS - 1.2);
const musicVol = (f: number) => {
	const film = f + Math.max(0, -sec(musicStart));
	const proof = sceneOf('proof');
	const fade = interpolate(f, [0, 12], [0, 1], clamp) * interpolate(film, [TOTAL - 30, TOTAL - 2], [1, 0], clamp);
	const talking = SPEECH.some((s) => film >= s.a - 6 && film <= s.b + 6);
	const lift = interpolate(film, [proof.from - 30, proof.from - 6, proof.from + 8, proof.from + proof.dur], [1, 1.9, 1.35, 1], clamp);
	return fade * (talking ? 0.05 : 0.16) * lift;
};

export const Film: React.FC<{audio?: boolean; captions?: boolean}> = ({audio = true, captions = true}) => {
	const frame = useCurrentFrame();
	return (
		<AbsoluteFill style={{background: C.ground}}>
			{starts().map((s) => (
				<Sequence key={s.id} from={s.from} durationInFrames={s.dur} name={s.id}>
					<s.C dur={s.dur} />
				</Sequence>
			))}
			{captions ? <Captions /> : null}
			{audio
				? vo.lines.map((l, i) =>
						l.file ? (
							<Sequence key={i} from={lineFrom(l)} durationInFrames={Math.ceil(l.dur * FPS) + 6} name={`vo ${i}`}>
								<Audio src={staticFile(l.file)} />
							</Sequence>
						) : null,
					)
				: null}
			{audio ? (
				<Sequence from={Math.max(0, -sec(musicStart))} name="music">
					<Audio src={staticFile('audio/music.mp3')} trimBefore={Math.max(0, sec(musicStart))} volume={musicVol} />
				</Sequence>
			) : null}
			{/* the last half second goes to black with the music */}
			<AbsoluteFill style={{background: 'black', opacity: interpolate(frame, [TOTAL - 15, TOTAL - 1], [0, 1], clamp), pointerEvents: 'none'}} />
		</AbsoluteFill>
	);
};

// every narrator line must end inside its scene, and the film stays under 116 s
for (const s of starts()) {
	for (const l of lines(s.id)) if (sec(s.vo + l.at + l.dur) > s.dur - 4) throw new Error(`"${l.text.slice(0, 40)}" runs past scene ${s.id}`);
}
if (TOTAL > 116 * FPS) throw new Error(`the film is ${(TOTAL / FPS).toFixed(1)} s: over 116 s`);
