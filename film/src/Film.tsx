import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {lines, vo, type VoLine} from './data';
import type {Clip} from './footage';
import {clipsFrames, sceneSec, spoken} from './footage';
import {Balance, End, Talk} from './scenes/Open';
import {Host, MathScene, Proof, Teach} from './scenes/Explain';
import {C, FPS, clamp} from './theme';
import {CaptionBox, chunks} from './captions';

// ================================================================ the recordings
// Each slot is the footage of one scene, by recording name (src/data/caps.json, from scripts/import-caps.mjs).
//   clips  parts of a recording, in its own seconds, played at real speed. Two parts of the same recording with a
//          gap between them are a cut: the film marks it ("5 s wait cut"), unless the part is an excerpt (`cut: false`,
//          and its note says so). A spoken answer is only ever ended at the end of a sentence.
//   zoom   camera moves: {at: recording second, z: 1.75, y: the app pixel (0 to 844) to centre, d: seconds (0 = cut)}.
//          The camera keeps its place over a cut.
//   note   what a part is, beside the phone where there is no live strip.
const IN = 1.75;
export const SLOTS: {
	voice3: {clips: Clip[]; big: {cap: string; card: string}};
	loop: {clips: Clip[]; vo: {cap: string; at: number}; beats: {cap: string; at: number}[]};
	figures: {clips: Clip[]};
	teach: {clips: Clip[]};
	lesson2: {clips: Clip[]};
	peers: {clips: Clip[]};
	host: {clips: Clip[]; beats: {cap: string; at: number; label: string}[]};
} = {
	// 1. Cold open: "Can I afford a six hundred and fifty euro phone this month?", the wait cut, the first sentence of
	//    the answer with the camera on its card, then back out for the name. big = the "afford" card (per_day).
	voice3: {
		clips: [
			{cap: 'voice3', from: 39.6, to: 43.6},
			{cap: 'voice3', from: 48.75, to: 54.8, zoom: [{at: 48.75, z: IN, y: 330}, {at: 54.85, z: 1, y: 422, d: 0.9}]},
		],
		big: {cap: 'voice3', card: 'afford'},
	},
	// 3. The habit loop, from the same session: Kori speaks first (what it noticed and the one question), "It was
	//    unusual", the answer that sets the one thing, then the home screen that keeps count (the `loop` recording).
	//    beats: when each step is seen: noticed, asked, one thing set, tracked. vo: where the narrator starts.
	loop: {
		clips: [
			{cap: 'voice3', from: 10.2, to: 21.6, zoom: [{at: 10.2, z: IN, y: 300, d: 0}]},
			{cap: 'voice3', from: 25.5, to: 29.95},
			{cap: 'voice3', from: 65.9, to: 69.2, mute: true, cut: false, note: 'The home screen · real speed'},
			{cap: 'loop', from: 8.7, to: 11.8, mute: true, zoom: [{at: 8.95, z: IN, y: 400}], note: 'The home screen · real speed'},
		],
		vo: {cap: 'voice3', at: 65.95},
		beats: [{cap: 'voice3', at: 10.4}, {cap: 'voice3', at: 15.6}, {cap: 'voice3', at: 25.7}, {cap: 'voice3', at: 66.0}],
	},
	// 4. Why the numbers are right: "numbers checked" tapped, and the sheet that says where each figure came from.
	figures: {
		// The text chat answer makes the proof legible at 1080p: the card, the source numbers and the check all land together.
		clips: [{cap: 'chat', from: 23.5, to: 27.0, mute: true, zoom: [{at: 23.5, z: IN, y: 500, d: 0}], note: 'Chat answer · real speed'}],
	},
	// 6. It teaches: the three baskets on the Baskets tab.
	teach: {
		clips: [{cap: 'teach', from: 0.15, to: 6.2, mute: true, zoom: [{at: 0.15, z: 1.32, y: 380, d: 0}, {at: 0.3, z: 1.5, y: 350, d: 5.6}], note: 'Baskets tab · real speed'}],
	},
	// The first lesson: the sorting step (one wrong on purpose) and say-it-back graded "Not yet".
	lesson2: {
		clips: [
			{cap: 'lesson2', from: 11.3, to: 13.65, mute: true, zoom: [{at: 11.3, z: IN, y: 570, d: 0}], note: 'Lesson · excerpts, real speed'},
			{cap: 'lesson2', from: 42.95, to: 45.25, mute: true, cut: false, zoom: [{at: 42.95, z: IN, y: 300, d: 0}], note: 'Lesson · excerpts, real speed'},
		],
	},
	// The "people like you" card with the Statistics Finland comparison.
	peers: {
		clips: [{cap: 'peers', from: 10.4, to: 14.7, mute: true, zoom: [{at: 10.4, z: IN, y: 560, d: 0}], note: 'Typed answer · real speed'}],
	},
	// 7. Inside the bank app: the host home, the consent sheet, Allow, Kori inside, the host's own "Safe to spend"
	//    tile, one beat of Finnish. Each beat lights a line on the right when it is seen.
	host: {
		clips: [
			{cap: 'host', from: 2.1, to: 9.6, mute: true, zoom: [{at: 4.2, z: IN, y: 620}, {at: 7.7, z: IN, y: 330}], note: 'Stand-in bank app · excerpts, real speed'},
			{cap: 'host', from: 11.3, to: 13.2, mute: true, cut: false, note: 'Stand-in bank app · excerpts, real speed'},
			{cap: 'host', from: 14.5, to: 16.9, mute: true, cut: false, zoom: [{at: 15.95, z: 1, y: 422, d: 0.85}], note: 'Stand-in bank app · excerpts, real speed'},
		],
		beats: [
			{cap: 'host', at: 2.1, label: 'The bank’s own home screen'},
			{cap: 'host', at: 4.14, label: 'Asks before it reads anything'},
			{cap: 'host', at: 7.9, label: 'Opens inside the bank app'},
			{cap: 'host', at: 11.5, label: 'Her number on the bank’s home'},
			{cap: 'host', at: 14.67, label: 'Suomeksi'},
		],
	},
};
// ================================================================

// a scene lasts as long as its footage and its narration, plus a breath
const voEndIn = (scene: string) => Math.max(0, ...lines(scene).map((l) => l.at + l.dur));
const sec = (s: number) => Math.round(s * FPS);
const talkVo = {open: clipsFrames(SLOTS.voice3.clips) / FPS, loop: sceneSec(SLOTS.loop.clips, SLOTS.loop.vo.cap, SLOTS.loop.vo.at) ?? 0};
export const teachClips = [...SLOTS.teach.clips, ...SLOTS.lesson2.clips, ...SLOTS.peers.clips];

type SceneDef = {id: string; dur: number; vo: number; C: React.FC<{dur: number}>; capX?: [number, number]};
const RIGHT: [number, number] = [910, 1844]; // the right half: clear of the phone
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
