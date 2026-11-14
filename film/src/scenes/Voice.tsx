import React from 'react';
import {Audio, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Chip, Eyebrow, Mark, Phone, Scene, Spoken, Tick, phoneWidth} from '../components';
import {caps, type Cap, type Said} from '../data';
import {C, FPS, MONO, clamp, prog} from '../theme';

// The conversation is shown as it was recorded: nothing sped up, nothing cut inside a question and its answer.
export const VOICE_CAP = 'voice2';
type Seg = {from: number; to: number; q: Said; filler?: Said; answer: Said; tool: string; checked: number; tUser: number; tTool: number; tDone: number};
export const voiceSegs = (cap: Cap): Seg[] => {
	const qs = cap.said.filter((u) => u.who === 'user');
	const answeredAt = cap.events.filter((e) => e.kind === 'coach answered').map((e) => e.at);
	return qs.map((q, i) => {
		const next = qs[i + 1]?.s ?? 1e9;
		const mine = cap.said.filter((u) => u.who === 'coach' && u.s > q.s && u.s < next);
		const answer = mine.find((u) => u.kind === 'answer')!;
		const scr = cap.screen.filter((e) => e.at > q.s && e.at < next);
		const parse = (name: string) => {
			const e = scr.find((x) => x.name === name);
			try {
				return e ? {at: e.at, ...JSON.parse(e.data)} : null;
			} catch {
				return e ? {at: e.at} : null;
			}
		};
		const st = parse('status'), dn = parse('done'), us = parse('user');
		const done = answeredAt.find((a) => a > q.s) ?? answer.e + 1.5;
		const end = Math.min(answer.e, done - 1.3) + 0.55;
		return {
			from: q.s - 0.45, to: Math.min(end, next - 0.5), q, filler: mine.find((u) => u.kind === 'filler'), answer,
			tool: st?.tool ?? '', checked: dn?.checked ?? 0, tUser: us?.at ?? q.e + 0.5, tTool: st?.at ?? q.e + 1.5, tDone: dn?.at ?? q.e + 3.5,
		};
	});
};
export const voiceDur = () => voiceSegs(caps[VOICE_CAP]).reduce((a, s) => a + Math.round((s.to - s.from) * FPS), 0);

const PH = 1000;
const Step: React.FC<{n: number; on: number; title: string; children?: React.ReactNode}> = ({on, title, children}) => (
	<div style={{display: 'flex', alignItems: 'center', gap: 20, height: 62, opacity: interpolate(on, [0, 1], [0.38, 1])}}>
		<div style={{width: 34, height: 34, flex: 'none', position: 'relative'}}>
			<div style={{position: 'absolute', inset: 3, borderRadius: 99, border: `2.5px solid ${C.lineStrong}`, opacity: 1 - on}} />
			<div style={{position: 'absolute', inset: 0, opacity: on, transform: `scale(${interpolate(on, [0, 1], [0.6, 1])})`}}>
				<Tick size={34} p={on} />
			</div>
		</div>
		<div style={{fontSize: 33, fontWeight: 600, letterSpacing: '-0.02em', color: C.ink}}>{title}</div>
		<div style={{opacity: on, display: 'flex', alignItems: 'center', gap: 12}}>{children}</div>
	</div>
);

const Part: React.FC<{cap: Cap; seg: Seg; dur: number; op: number}> = ({cap, seg, dur, op}) => {
	const frame = useCurrentFrame();
	const t = seg.from + frame / FPS;
	const inAnswer = t >= seg.answer.s - 0.25;
	const swap = interpolate(t, [seg.answer.s - 0.35, seg.answer.s - 0.05], [0, 1], clamp);
	const speaking = cap.said.some((u) => u.who === 'coach' && t >= u.s && t <= u.e);
	const lv = [0, 1, 2].map((i) => (speaking ? 0.45 + 0.5 * Math.abs(Math.sin(t * (7 + i * 2.3) + i)) : [0.3, 0.42, 0.3][i]));
	const on = (at: number) => interpolate(t, [at, at + 0.35], [0, 1], clamp);
	const x0 = 150 + phoneWidth(PH) + 110;
	return (
		<>
			<div style={{position: 'absolute', left: 150, top: 40}}>
				<Phone h={PH} cap={cap} from={seg.from} />
			</div>
			<div style={{position: 'absolute', left: x0, right: 96, top: 84, opacity: op}}>
				<div style={{display: 'flex', alignItems: 'center', gap: 14}}>
					<div style={{width: 16, height: 16, borderRadius: 9, background: C.neg, opacity: 0.55 + 0.45 * Math.abs(Math.sin(t * 2.4))}} />
					<Eyebrow>Recorded live · real voices · nothing sped up</Eyebrow>
				</div>
				{/* the question */}
				<div style={{marginTop: 44, display: 'flex', alignItems: 'baseline', gap: 18}}>
					<div style={{fontSize: 30, fontWeight: 600, color: C.ink3, width: 86, flex: 'none'}}>Aino</div>
					<Spoken words={seg.q.words} t={t} size={46} weight={500} color={C.ink2} dim={0.16} />
				</div>
				{/* the coach */}
				<div style={{marginTop: 34, display: 'flex', gap: 18, opacity: interpolate(t, [seg.q.e + 0.1, seg.q.e + 0.5], [0, 1], clamp)}}>
					<div style={{width: 86, flex: 'none', paddingTop: 6}}>
						<Mark size={60} levels={lv} />
					</div>
					<div style={{position: 'relative', flex: 1, height: 400}}>
						{seg.filler ? (
							<div style={{position: 'absolute', inset: 0, opacity: 1 - swap}}>
								<Spoken words={seg.filler.words} t={t} size={54} weight={500} color={C.ink3} dim={0.12} />
							</div>
						) : null}
						<div style={{position: 'absolute', inset: 0, opacity: inAnswer ? swap : 0}}>
							<Spoken words={seg.answer.words} t={t} size={54} dim={0.14} />
						</div>
					</div>
				</div>
			</div>
			{/* what happens between her question and the answer */}
			<div style={{position: 'absolute', left: x0, right: 96, bottom: 70, opacity: op}}>
				<div style={{height: 2, background: C.line, marginBottom: 22}} />
				<Step n={1} on={on(seg.tUser - 0.35)} title="ElevenLabs hears her">
					<Chip size={22}>speech to text</Chip>
				</Step>
				<Step n={2} on={on(seg.tTool)} title="Gemini picks the calculation">
					<Chip size={22} mono tone="brand">{seg.tool}()</Chip>
				</Step>
				<Step n={3} on={on(seg.tTool + 0.45)} title="The engine does the math">
					<Chip size={22}>her own transactions</Chip>
				</Step>
				<Step n={4} on={on(seg.tDone)} title="Every number is checked">
					<span style={{fontFamily: MONO, fontSize: 24, color: C.brandStrong}}>{seg.checked} of {seg.checked} match</span>
				</Step>
				<Step n={5} on={on(seg.answer.s)} title="ElevenLabs speaks the answer" />
			</div>
			{/* the real sound */}
			{cap.coach ? <Audio src={staticFile(cap.coach.file)} trimBefore={Math.max(0, Math.round((seg.from - cap.coach.start) * FPS))} volume={(f) => interpolate(f, [0, 4, dur - 5, dur], [0, 1, 1, 0], clamp)} /> : null}
			{seg.q.file ? (
				<Sequence from={Math.round((seg.q.s - seg.from) * FPS)} durationInFrames={Math.ceil((seg.q.e - seg.q.s) * FPS) + 6}>
					<Audio src={staticFile(seg.q.file)} volume={0.95} />
				</Sequence>
			) : null}
		</>
	);
};

export const Voice: React.FC<{dur: number}> = ({dur}) => {
	const frame = useCurrentFrame();
	const cap = caps[VOICE_CAP];
	const segs = voiceSegs(cap);
	let at = 0;
	return (
		<Scene dur={dur}>
			{segs.map((s, i) => {
				const d = Math.round((s.to - s.from) * FPS);
				const from = at;
				at += d;
				const op = Math.min(i === 0 ? 1 : prog(frame, from / FPS, 0.25), interpolate(frame, [from + d - 6, from + d], [1, i === segs.length - 1 ? 1 : 0], clamp));
				return (
					<Sequence key={i} from={from} durationInFrames={d} name={`question ${i + 1}`}>
						<Part cap={cap} seg={s} dur={d} op={op} />
					</Sequence>
				);
			})}
		</Scene>
	);
};
