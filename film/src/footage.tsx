import React from 'react';
import {Audio, Freeze, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Phone, Tick, WaitCut, phoneWidth, type Zoom} from './components';
import {caps, screenOf, type Said, type Word} from './data';
import {C, FPS, MONO, SANS, clamp} from './theme';

/** A part of a recording, played at real speed. Two parts of the same recording with a gap between them are a cut,
 *  and the cut is marked on screen. `zoom`: punch-ins, in the recording's own seconds. `note`: what this part is,
 *  shown under the phone when there is no live strip ("Lesson · excerpt, real speed"). */
export type Clip = {cap: string; from: number; to: number; zoom?: Zoom[]; mute?: boolean; note?: string};
export type Placed = Clip & {start: number; frames: number; cut: number};

// every real voice sits level with the narrator (−23.2 LUFS): its gain comes from its own loudness, measured at import
const NARRATOR_LUFS = -23.2;
export const gainFor = (lufs?: number) => (lufs === undefined ? 1 : Math.pow(10, (NARRATOR_LUFS - lufs) / 20));

export const place = (clips: Clip[]): Placed[] => {
	let at = 0;
	return clips.map((c, i) => {
		const prev = clips[i - 1];
		const frames = Math.round((c.to - c.from) * FPS);
		const p = {...c, start: at, frames, cut: prev && prev.cap === c.cap && c.from - prev.to > 0.25 ? c.from - prev.to : 0};
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
		const ws = (w: Word[]) => w.filter((x) => x.s >= p.from - 0.05 && x.e <= p.to + 0.05).map((x) => ({...x, s: x.s + shift, e: x.e + shift}));
		return caps[p.cap].said
			.filter((u) => u.e > p.from + 0.05 && u.s < p.to - 0.05)
			.map((u) => ({...u, s: Math.max(u.s, p.from) + shift, e: Math.min(u.e, p.to) + shift, words: ws(u.words)}));
	});

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

/** The recordings of a scene in a phone: parts at real speed, cuts marked, the real sound, a live strip below. */
export const Footage: React.FC<{clips: Clip[]; h: number; x: number; y: number; strip?: boolean; audio?: boolean}> = ({clips, h, x, y, strip = true, audio = true}) => {
	const ps = place(clips);
	const end = ps.length ? ps[ps.length - 1].start + ps[ps.length - 1].frames : 0;
	const last = ps[ps.length - 1];
	const pw = phoneWidth(h);
	const SW = 640;
	return (
		<>
			<div style={{position: 'absolute', left: x, top: y}}>
				{ps.map((p, i) => (
					<Sequence key={i} from={p.start} durationInFrames={p.frames} layout="none" name={`${p.cap} ${p.from.toFixed(1)}–${p.to.toFixed(1)}`}>
						<Phone h={h} cap={caps[p.cap]} from={p.from} zoom={p.zoom} />
					</Sequence>
				))}
				{last ? (
					<Sequence from={end} layout="none" name="hold">
						<Freeze frame={0}>
							<Phone h={h} cap={caps[last.cap]} from={last.to - 1 / FPS} zoom={last.zoom} taps={false} />
						</Freeze>
					</Sequence>
				) : null}
				{ps.map((p, i) =>
					p.cut ? (
						<Sequence key={`cut${i}`} from={p.start} durationInFrames={60} layout="none">
							<div style={{position: 'absolute', left: 0, width: pw, top: Math.round(h * 0.075), display: 'flex', justifyContent: 'center'}}>
								<WaitCut seconds={p.cut} />
							</div>
						</Sequence>
					) : null,
				)}
			</div>
			{strip ? (
				<div style={{position: 'absolute', left: x + 4, top: y + h + 8}}>
					<Strip clips={clips} w={SW} />
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
