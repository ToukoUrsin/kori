import React from 'react';
import {Audio, Freeze, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Phone, Tick, WaitCut, phoneWidth} from './components';
import {caps, screenOf, type Said, type Word} from './data';
import {C, FPS, MONO, SANS, clamp, inOut} from './theme';

/** A part of a recording, played at real speed. Two parts of the same recording with a gap between them are a cut,
 *  and the cut is marked on screen (`cut: false` for an excerpt that is not a wait; the note then says "excerpt").
 *  `zoom`: camera moves, in the recording's own seconds. `note`: what this part is, shown beside the phone when
 *  there is no live strip ("Lesson · excerpt, real speed"). */
export type Zoom = {at: number; z: number; y: number; d?: number};
export type Clip = {cap: string; from: number; to: number; zoom?: Zoom[]; mute?: boolean; note?: string; cut?: boolean};
export type Placed = Omit<Clip, 'cut'> & {start: number; frames: number; cut: number};

// The stage: the phone stands in the left half, the words in the right half. The camera pushes in on the phone as a
// whole (the full width of the app stays in view, its top or bottom leaves the frame), so app text reads at 28 px.
export const PH = 940, PY = 28, PCX = 470;
export const X0 = 930;
export const phoneX = PCX - Math.round(phoneWidth(PH) / 2);

// every real voice sits level with the narrator (−23.2 LUFS): its gain comes from its own loudness, measured at import
const NARRATOR_LUFS = -23.2;
export const gainFor = (lufs?: number) => (lufs === undefined ? 1 : Math.pow(10, (NARRATOR_LUFS - lufs) / 20));

export const place = (clips: Clip[]): Placed[] => {
	let at = 0;
	return clips.map((c, i) => {
		const prev = clips[i - 1];
		const frames = Math.round((c.to - c.from) * FPS);
		const p = {...c, start: at, frames, cut: c.cut !== false && prev && prev.cap === c.cap && c.from - prev.to > 0.25 ? c.from - prev.to : 0};
		at += frames;
		return p;
	});
};
export const clipsFrames = (clips: Clip[]) => clips.reduce((a, c) => a + Math.round((c.to - c.from) * FPS), 0);

/** The clip and recording second on screen at scene frame `f` (the last frame holds after the end). */
export const recAt = (clips: Clip[], f: number) => {
	const ps = place(clips);
	const p = ps.find((x) => f >= x.start && f < x.start + x.frames) ?? (f < 0 ? ps[0] : ps[ps.length - 1]);
	const t = Math.min(p.to, Math.max(p.from, p.from + (f - p.start) / FPS));
	return {clip: p, t, cap: caps[p.cap]};
};
/** The scene second at which second `t` of recording `cap` is on screen (first time), or null. */
export const sceneSec = (clips: Clip[], cap: string, t: number): number | null => {
	for (const p of place(clips)) if (p.cap === cap && t >= p.from - 1e-6 && t <= p.to + 1e-6) return p.start / FPS + (t - p.from);
	return null;
};
/** What is said in the clips, in scene seconds (the parts of each utterance that are played). */
export const spoken = (clips: Clip[]): Said[] =>
	place(clips).flatMap((p) => {
		if (p.mute) return [];
		const shift = p.start / FPS - p.from;
		// a word belongs to the part it ends in (the transcriber's word starts can be half a second early)
		const ws = (w: Word[]) => w.filter((x) => x.e > p.from + 0.1 && x.e <= p.to + 0.05).map((x) => ({...x, s: Math.max(x.s, p.from) + shift, e: x.e + shift}));
		return caps[p.cap].said
			.filter((u) => u.e > p.from + 0.05 && u.s < p.to - 0.05)
			.map((u) => ({...u, s: Math.max(u.s, p.from) + shift, e: Math.min(u.e, p.to) + shift, words: ws(u.words)}))
			.filter((u) => u.words.length);
	});

const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
/** Where the camera is at scene frame `f`: every clip's moves on one track, so a cut does not reset it.
 *  z: how much larger than the whole phone; y: the app pixel (0 to 844) at the middle of the frame. */
export const camAt = (clips: Clip[], f: number) => {
	const keys = place(clips)
		.flatMap((p) => (p.zoom ?? []).map((k) => ({...k, at: p.start / FPS + (k.at - p.from)})))
		.sort((a, b) => a.at - b.at);
	const t = f / FPS;
	let st = {z: 1, y: 422};
	for (const k of keys) {
		if (t < k.at) break;
		const d = k.d ?? 0.7;
		const p = d <= 0 ? 1 : interpolate(t, [k.at, k.at + d], [0, 1], {...clamp, easing: inOut});
		st = {z: lerp(st.z, k.z, p), y: lerp(st.y, k.y, p)};
	}
	return st;
};
/** The phone's height and top-left corner on the 1920 × 1080 frame for a camera position. */
export const stageAt = (cam: {z: number; y: number}) => {
	const h = Math.round(PH * cam.z);
	const b = Math.round(h * 0.013);
	const k = (h - 2 * b) / 844;
	const lo = 1080 - PY - h;
	const top = h <= 1080 - 2 * PY ? PY : Math.min(PY, Math.max(lo, 540 - (b + cam.y * k)));
	return {h, left: PCX - Math.round(phoneWidth(h) / 2), top: Math.round(top)};
};

/** The calculation the coach picked and how many numbers were checked, as the recording logged them. */
const liveAt = (capName: string, t: number) => {
	const cap = caps[capName];
	const asked = cap.said.filter((u) => u.who === 'user' && u.s <= t).at(-1)?.s ?? screenOf(cap, 'user').filter((e) => e.at <= t).at(-1)?.at ?? 0;
	const status = screenOf(cap, 'status').filter((e) => e.at >= asked - 0.5 && e.at <= t);
	const done = screenOf(cap, 'done').filter((e) => e.at >= asked - 0.5 && e.at <= t).at(-1);
	return {tool: status[0]?.tool as string | undefined, toolAt: status[0]?.at as number | undefined, checked: done?.checked as number | undefined, doneAt: done?.at as number | undefined};
};

const Strip: React.FC<{clips: Clip[]; w: number}> = ({clips, w}) => {
	const frame = useCurrentFrame();
	const {clip, t} = recAt(clips, frame);
	const live = liveAt(clip.cap, t);
	const show = (at?: number) => (at === undefined ? 0 : interpolate(t, [at, at + 0.3], [0, 1], clamp));
	const hasLive = live.tool !== undefined;
	return (
		<div style={{width: w, display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 6, fontFamily: SANS, whiteSpace: 'nowrap'}}>
			{hasLive ? (
				<>
					<div style={{display: 'flex', alignItems: 'center', gap: 12, opacity: show(live.toolAt)}}>
						<span style={{fontSize: 32, fontWeight: 500, color: C.ink3}}>picked</span>
						<span style={{fontFamily: MONO, fontSize: 32, fontWeight: 500, color: C.brandStrong, background: C.brandSoft, border: `1.5px solid ${C.brandLine}`, borderRadius: 12, padding: '0 12px'}}>{live.tool}()</span>
					</div>
					{live.checked !== undefined ? (
						<div style={{display: 'flex', alignItems: 'center', gap: 10, opacity: show(live.doneAt)}}>
							<Tick size={32} p={show(live.doneAt)} />
							<span style={{fontSize: 36, fontWeight: 600, color: C.ink}}>{live.checked} numbers checked</span>
						</div>
					) : null}
				</>
			) : clip.note ? (
				<span style={{fontSize: 32, fontWeight: 500, color: C.ink2}}>{clip.note}</span>
			) : null}
		</div>
	);
};

/** The recordings of a scene in a phone: parts at real speed, cuts marked, the real sound, a live strip beside it. */
export const Footage: React.FC<{clips: Clip[]; strip?: boolean; stripOp?: number; audio?: boolean}> = ({clips, strip = true, stripOp = 1, audio = true}) => {
	const frame = useCurrentFrame();
	const ps = place(clips);
	const end = ps.length ? ps[ps.length - 1].start + ps[ps.length - 1].frames : 0;
	const last = ps[ps.length - 1];
	const st = stageAt(camAt(clips, frame));
	return (
		<>
			<div style={{position: 'absolute', left: st.left, top: st.top}}>
				{ps.map((p, i) => (
					<Sequence key={i} from={p.start} durationInFrames={p.frames} layout="none" name={`${p.cap} ${p.from.toFixed(1)}–${p.to.toFixed(1)}`}>
						<Phone h={st.h} cap={caps[p.cap]} from={p.from} />
					</Sequence>
				))}
				{last ? (
					<Sequence from={end} layout="none" name="hold">
						<Freeze frame={0}>
							<Phone h={st.h} cap={caps[last.cap]} from={last.to - 1 / FPS} taps={false} />
						</Freeze>
					</Sequence>
				) : null}
			</div>
			{ps.map((p, i) =>
				p.cut ? (
					<Sequence key={`cut${i}`} from={p.start} durationInFrames={60} layout="none">
						<div style={{position: 'absolute', left: PCX - 300, width: 600, top: 96, display: 'flex', justifyContent: 'center'}}>
							<WaitCut seconds={p.cut} />
						</div>
					</Sequence>
				) : null,
			)}
			{strip ? (
				<div style={{position: 'absolute', left: X0, top: 838, opacity: stripOp}}>
					<Strip clips={clips} w={880} />
				</div>
			) : null}
			{audio
				? ps.map((p, i) => (
						<Sequence key={`a${i}`} from={p.start} durationInFrames={p.frames} layout="none">
							<ClipSound clip={p} />
						</Sequence>
					))
				: null}
			{ps.map((p, i) => (p.cut ? (
				<Sequence key={`t${i}`} from={p.start - 1} durationInFrames={12} layout="none">
					<Audio src={staticFile('audio/tick.mp3')} volume={0.5} />
				</Sequence>
			) : null))}
		</>
	);
};

/** The real sound of one part: the coach's voice track and Aino's spoken questions, faded at the edges. */
const ClipSound: React.FC<{clip: Placed}> = ({clip}) => {
	const cap = caps[clip.cap];
	if (clip.mute) return null;
	const fade = (f: number) => interpolate(f, [0, 3, clip.frames - 4, clip.frames], [0, 1, 1, 0], clamp);
	const users = cap.said.filter((u) => u.who === 'user' && u.file && u.e > clip.from && u.s < clip.to);
	const coach = cap.coach;
	return (
		<>
			{coach ? (
				clip.from >= coach.start ? (
					<Audio src={staticFile(coach.file)} trimBefore={Math.round((clip.from - coach.start) * FPS)} volume={(f) => gainFor(coach.lufs) * fade(f)} />
				) : (
					<Sequence from={Math.round((coach.start - clip.from) * FPS)} layout="none">
						<Audio src={staticFile(coach.file)} volume={(f) => gainFor(coach.lufs) * fade(f + Math.round((coach.start - clip.from) * FPS))} />
					</Sequence>
				)
			) : null}
			{users.map((u, i) => {
				const off = Math.round((u.s - clip.from) * FPS);
				return off >= 0 ? (
					<Sequence key={i} from={off} layout="none">
						<Audio src={staticFile(u.file!)} volume={(f) => gainFor(u.lufs) * fade(f + off)} />
					</Sequence>
				) : (
					<Audio key={i} src={staticFile(u.file!)} trimBefore={-off} volume={(f) => gainFor(u.lufs) * fade(f)} />
				);
			})}
		</>
	);
};
