import React from 'react';
import {Freeze, interpolate, useCurrentFrame} from 'remotion';
import {CaptionBox, chunks} from '../captions';
import {Chip, H1, Mark, Phone, Provenance, Scene, Spoken, Tick} from '../components';
import {caps, cardOf, cue, home, lineAt} from '../data';
import {Footage, PH, PY, X0, phoneX, sceneSec, spoken, type Clip} from '../footage';
import {C, FPS, MONO, SANS, clamp, eur, inOut, out, prog, rise} from '../theme';

const S = home.safe;
const part = (k: string) => S.spoken_for.find((p) => p.key === k)?.amount ?? 0;
const BAR_W = 1600, BAR_X = 160, BAR_Y = 430, BAR_H = 104;
const SEGS = [
	{key: 'fixed', label: 'Still due before payday', color: C.fixed},
	{key: 'surprise', label: 'Surprise reserve', color: C.surprise},
	{key: 'cushion', label: 'Cushion', color: C.cushion},
	{key: 'safe', label: 'Safe to spend', color: C.brand},
	{key: 'buffer', label: 'Buffer', color: C.brandLine},
].map((s) => ({...s, amount: part(s.key)}));

/** The balance, what is already spoken for, and the one number that is hers. */
export const Balance: React.FC<{dur: number}> = ({dur}) => {
	const frame = useCurrentFrame();
	const tMove = lineAt('balance', 1) - 0.15; // "But rent, bills…"
	const at: Record<string, number> = {
		fixed: cue('balance', 1, 'rent'),
		surprise: cue('balance', 1, 'surprises'),
		cushion: cue('balance', 1, 'come'),
		buffer: cue('balance', 1, 'before') + 0.25,
		safe: cue('balance', 2, 'hers') - 0.1,
	};
	const tNum = cue('balance', 2, 'one') - 0.1;
	const tLine = lineAt('balance', 3) - 0.1;
	const move = prog(frame, tMove, 0.9, inOut);
	const count = interpolate(frame, [0.2 * FPS, 1.6 * FPS], [0, S.balance], {...clamp, easing: out});
	const whole = Math.floor(count), cents = String(Math.round((count - whole) * 100)).padStart(2, '0');
	const numSize = interpolate(move, [0, 1], [300, 150]);
	const numY = interpolate(move, [0, 1], [372, 170]);
	const spot = prog(frame, at.safe + 0.5, 0.6);
	const gone = prog(frame, tLine - 0.1, 0.4);
	let x = 0;
	const rows = [SEGS.filter((s) => s.key === 'fixed' || s.key === 'surprise'), SEGS.filter((s) => s.key === 'cushion' || s.key === 'buffer')];
	return (
		<Scene dur={dur}>
			{/* the balance */}
			<div style={{opacity: 1 - gone}}>
				<div style={{position: 'absolute', left: 0, right: 0, top: numY - 80 + (1 - move) * 8, textAlign: 'center', fontSize: interpolate(move, [0, 1], [44, 34]), fontWeight: 500, color: C.ink3, ...rise(frame, 0.05, 0.5, 16)}}>On Aino’s account today</div>
				<div style={{position: 'absolute', left: 0, right: 0, top: numY, textAlign: 'center', fontSize: numSize, fontWeight: 600, letterSpacing: '-0.045em', lineHeight: 1, fontVariantNumeric: 'tabular-nums', opacity: prog(frame, 0.1, 0.4)}}>
					{eur(whole)}
					<span style={{fontSize: numSize * 0.42, color: C.ink3, letterSpacing: '-0.03em'}}>.{cents}</span>
				</div>
			</div>
			{/* the line to remember takes its place */}
			<div style={{position: 'absolute', left: 0, right: 0, top: 176, textAlign: 'center', ...rise(frame, tLine + 0.15, 0.7, 30)}}>
				<H1 size={104}>Your balance is not your budget.</H1>
			</div>
			{/* the same money as a bar, carved up */}
			<div style={{position: 'absolute', left: BAR_X, top: BAR_Y, width: BAR_W, height: BAR_H, borderRadius: 22, overflow: 'hidden', background: spot > 0 ? C.ground : C.ink, opacity: prog(frame, tMove + 0.35, 0.5), transform: `scaleX(${interpolate(prog(frame, tMove + 0.35, 0.8), [0, 1], [0.6, 1])})`}}>
				{SEGS.map((s) => {
					const w = (s.amount / S.balance) * BAR_W;
					const left = x;
					x += w;
					const p = prog(frame, at[s.key], 0.55);
					const dim = s.key === 'safe' ? 1 : interpolate(spot, [0, 1], [1, 0.38]);
					return (
						<div key={s.key} style={{position: 'absolute', left, top: 0, width: w, height: BAR_H, opacity: dim}}>
							<div
								style={{
									width: `${p * 100}%`, height: '100%',
									background: s.key === 'buffer' ? `repeating-linear-gradient(135deg, ${C.brandLine} 0 10px, ${C.brandSoft} 10px 20px)` : s.color,
									borderRight: p > 0.02 ? `4px solid ${C.ground}` : 'none', boxSizing: 'border-box',
								}}
							/>
						</div>
					);
				})}
			</div>
			{/* what each part is: two rows, 36 px */}
			<div style={{position: 'absolute', left: BAR_X, top: BAR_Y + BAR_H + 24, width: BAR_W, opacity: interpolate(spot, [0, 1], [1, 0.45])}}>
				{rows.map((row, r) => (
					<div key={r} style={{display: 'flex', gap: 64, height: 56, alignItems: 'center'}}>
						{row.map((s) => (
							<div key={s.key} style={{display: 'flex', alignItems: 'center', gap: 16, fontSize: 36, fontWeight: 500, color: C.ink2, ...rise(frame, at[s.key], 0.5, 14)}}>
								<div style={{width: 22, height: 22, borderRadius: 6, background: s.key === 'buffer' ? C.brandLine : s.color}} />
								{s.label}
								<span style={{color: C.ink, fontWeight: 600, fontVariantNumeric: 'tabular-nums'}}>{eur(s.amount)}</span>
							</div>
						))}
					</div>
				))}
			</div>
			{/* the number that is hers */}
			<div style={{position: 'absolute', left: BAR_X + ((part('fixed') + part('surprise') + part('cushion')) / S.balance) * BAR_W, top: BAR_Y + BAR_H + 150, ...rise(frame, tNum, 0.6, 24)}}>
				<div style={{fontSize: 38, fontWeight: 600, color: C.brand}}>Safe to spend until payday</div>
				<div style={{display: 'flex', alignItems: 'baseline', gap: 28}}>
					<div style={{fontSize: 190, fontWeight: 600, letterSpacing: '-0.045em', lineHeight: 1.02, color: C.brand, fontVariantNumeric: 'tabular-nums'}}>{eur(Math.round(S.amount))}</div>
					<div style={{fontSize: 44, fontWeight: 500, color: C.ink2}}>{eur(S.per_day)} a day</div>
				</div>
			</div>
		</Scene>
	);
};

// ---------------------------------------------------------------- the scenes with the real voices
export {PH, PY, X0};
const COL = {position: 'absolute' as const, left: X0, right: 96};

const STEPS = ['Notices what happened', 'Asks one question', 'Sets one thing to try', 'Keeps count on the home screen'];

/** The number the answer changes, from the card the app showed: "€46 → €19 a day". Each number lands when it is said. */
const BigChange: React.FC<{cap: string; card: string; tBefore: number; tAfter: number}> = ({cap, card, tBefore, tAfter}) => {
	const frame = useCurrentFrame();
	const d = cardOf(caps[cap], card);
	if (!d) return null;
	const p = prog(frame, tBefore, 0.5);
	const p2 = prog(frame, tAfter, 0.5);
	const pop = interpolate(frame / FPS, [tAfter, tAfter + 0.16, tAfter + 0.45], [0.7, 1.07, 1], {...clamp, easing: out});
	const big = {fontSize: 150, fontWeight: 600, letterSpacing: '-0.05em', lineHeight: 1, fontVariantNumeric: 'tabular-nums' as const};
	return (
		<div style={{opacity: p, transform: `translateY(${(1 - p) * 26}px)`}}>
			<div style={{fontSize: 38, fontWeight: 600, color: C.ink3}}>Her pace until payday</div>
			<div style={{display: 'flex', alignItems: 'baseline', gap: 26, marginTop: 8}}>
				<div style={{...big, color: C.ink3}}>{eur(Math.round(d.per_day.before))}</div>
				<svg width={84} height={56} viewBox="0 0 60 40" style={{alignSelf: 'center', opacity: p2, flex: 'none'}}>
					<path d="M4 20h44M36 8l14 12-14 12" fill="none" stroke={C.ink3} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
				</svg>
				<div style={{...big, color: C.brand, opacity: p2, transform: `scale(${pop})`, transformOrigin: '0 80%'}}>{eur(Math.round(d.per_day.after))}</div>
				<div style={{fontSize: 48, fontWeight: 500, color: C.ink2, opacity: p2, whiteSpace: 'nowrap'}}>a day</div>
			</div>
		</div>
	);
};

/** A live conversation, recorded: the phone (the camera pushes in on the answer), what Aino says, and either the
 *  number that changes (cold open) or the four steps of the habit loop. The narrator speaks from `voAt`. */
export const Talk: React.FC<{dur: number; kind: 'open' | 'loop'; clips: Clip[]; big?: {cap: string; card: string}; beats?: {cap: string; at: number}[]; voAt: number}> = ({dur, kind, clips, big, beats, voAt}) => {
	const frame = useCurrentFrame();
	const t = frame / FPS;
	const said = spoken(clips);
	const q = said.filter((u) => u.who === 'user' && u.s - 0.2 <= t).at(-1);
	const coach = said.filter((u) => u.who === 'coach');
	const caps_ = coach.flatMap((u) => chunks(u));
	const c = caps_.find((x) => t >= x.s - 0.05 && t < x.e + 0.25);
	const outro = prog(frame, voAt - 0.1, 0.6);
	// the two numbers of the card land when the coach says them
	let tBefore = 0, tAfter = 0;
	if (big) {
		const d = cardOf(caps[big.cap], big.card);
		const saidAt = (n: number) => coach.flatMap((u) => u.words).find((w) => w.w.replace(/\D/g, '') === String(Math.round(n)))?.s;
		tBefore = (d && saidAt(d.per_day.before)) ?? (coach[0]?.s ?? 0) + 0.4;
		tAfter = (d && saidAt(d.per_day.after)) ?? tBefore + 0.6;
	}
	const beatAt = (beats ?? []).map((b) => sceneSec(clips, b.cap, b.at) ?? 1e9);
	return (
		<Scene dur={dur}>
			<Footage clips={clips} />
			<div style={{...COL, top: 84}}>
				<Provenance live style={rise(frame, 0.05, 0.5, 12)}>Recorded live · ElevenLabs · excerpts</Provenance>
			</div>
			{kind === 'open' ? (
				<>
					<div style={{...COL, top: 164, opacity: 1 - outro}}>
						{q ? (
							<div key={q.text} style={{display: 'flex', flexDirection: 'column', gap: 8, ...rise(frame, q.s - 0.25, 0.4, 14)}}>
								<div style={{fontSize: 34, fontWeight: 600, color: C.ink3}}>Aino asks</div>
								<Spoken words={q.words} t={t} size={62} weight={600} dim={0.22} style={{letterSpacing: '-0.03em'}} />
							</div>
						) : null}
					</div>
					{big ? (
						<div style={{...COL, top: 500, opacity: 1 - outro}}>
							<BigChange cap={big.cap} card={big.card} tBefore={tBefore} tAfter={tAfter} />
						</div>
					) : null}
					<div style={{...COL, top: 250, opacity: outro, transform: `translateY(${(1 - outro) * 30}px)`}}>
						<div style={{display: 'flex', alignItems: 'center', gap: 24}}>
							<Mark size={150} levels={[0, 1, 2].map((i) => interpolate(prog(frame, voAt + i * 0.09, 0.7), [0, 1], [0.1, [0.55, 1, 0.42][i]]))} />
							<div style={{fontSize: 190, fontWeight: 600, letterSpacing: '-0.055em', lineHeight: 1}}>Kori</div>
						</div>
						<div style={{fontSize: 58, fontWeight: 500, letterSpacing: '-0.025em', lineHeight: 1.18, color: C.ink2, marginTop: 30}}>A money coach for young adults, right inside the bank app.</div>
						<div style={{display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 40, ...rise(frame, voAt + 1.4, 0.6, 12)}}>
							<Chip>Voice: ElevenLabs Agents</Chip>
							<Chip>Reasoning: Gemini</Chip>
							<Chip tone="brand">For S-Pankki</Chip>
						</div>
					</div>
				</>
			) : (
				<>
					<div style={{...COL, top: 150}}>
						<H1 size={84} style={rise(frame, 0.15, 0.6)}>Kori speaks first.</H1>
					</div>
					<div style={{...COL, top: 300, display: 'flex', flexDirection: 'column', gap: 24}}>
						{STEPS.map((label, i) => {
							const on = interpolate(t, [beatAt[i] - 0.1, beatAt[i] + 0.3], [0, 1], clamp);
							const now = on > 0 && (i === STEPS.length - 1 || t < beatAt[i + 1] - 0.1);
							return (
								<div key={label} style={{display: 'flex', alignItems: 'center', gap: 22, opacity: interpolate(on, [0, 1], [0.3, 1])}}>
									<div style={{width: 46, height: 46, flex: 'none', position: 'relative'}}>
										<div style={{position: 'absolute', inset: 4, borderRadius: 99, border: `3px solid ${C.lineStrong}`, opacity: 1 - on}} />
										<div style={{position: 'absolute', inset: 0, opacity: on}}><Tick size={46} p={on} /></div>
									</div>
									<div style={{fontSize: 48, fontWeight: 600, letterSpacing: '-0.025em', color: now ? C.ink : C.ink2}}>{label}</div>
								</div>
							);
						})}
					</div>
					<div style={{...COL, top: 630, opacity: 1 - prog(frame, voAt - 0.3, 0.4)}}>
						{q ? (
							<div style={{display: 'flex', flexDirection: 'column', gap: 6, ...rise(frame, q.s - 0.25, 0.4, 14)}}>
								<div style={{fontSize: 34, fontWeight: 600, color: C.ink3}}>Aino answers</div>
								<Spoken words={q.words} t={t} size={62} weight={600} dim={0.22} style={{letterSpacing: '-0.03em'}} />
							</div>
						) : null}
					</div>
				</>
			)}
			{c ? <CaptionBox text={c.text} op={Math.min(interpolate(t, [c.s - 0.05, c.s + 0.1], [0, 1], clamp), interpolate(t, [c.e + 0.1, c.e + 0.25], [1, 0], clamp))} x={[X0 - 20, 1844]} /> : null}
		</Scene>
	);
};

/** The last card: the phone stays where the bank app scene left it, the name and the line land with the narrator. */
export const End: React.FC<{dur: number; clips: Clip[]}> = ({dur, clips}) => {
	const frame = useCurrentFrame();
	const last = clips[clips.length - 1];
	const tLine = cue('end', 0, 'your') - 0.15;
	return (
		<Scene dur={dur + 7} fadeIn={false}>
			<div style={{position: 'absolute', top: PY, left: phoneX}}>
				<Freeze frame={0}>
					<Phone h={PH} cap={caps[last.cap]} from={last.to - 1 / FPS} taps={false} />
				</Freeze>
			</div>
			<div style={{position: 'absolute', left: X0 - 60, right: 70, top: 150}}>
				<div style={{display: 'flex', alignItems: 'center', gap: 18, ...rise(frame, 0.45, 0.6)}}>
					<Mark size={120} />
					<div style={{fontSize: 150, fontWeight: 600, letterSpacing: '-0.055em', lineHeight: 1}}>Kori</div>
				</div>
				<H1 size={84} style={{marginTop: 30, ...rise(frame, tLine, 0.7)}}>Your balance is<br />not your budget.</H1>
				<div style={{display: 'inline-block', marginTop: 44, fontFamily: MONO, fontSize: 48, fontWeight: 500, color: C.brandStrong, background: C.brandSoft, border: `2px solid ${C.brandLine}`, borderRadius: 22, padding: '16px 38px', ...rise(frame, 1.9, 0.6)}}>kori-coach.fly.dev</div>
				<div style={{display: 'flex', gap: 14, marginTop: 30, flexWrap: 'wrap', ...rise(frame, 2.3, 0.6)}}>
					<Chip>Voice: ElevenLabs Agents</Chip>
					<Chip>Reasoning: Gemini</Chip>
					<Chip mono>github.com/ToukoUrsin/kori</Chip>
				</div>
				<div style={{fontFamily: SANS, fontSize: 34, fontWeight: 500, color: C.ink2, marginTop: 34, opacity: prog(frame, 2.7, 0.6)}}>Junction 2026 · S-Pankki challenge: Personal Economic Trainer</div>
				<div style={{fontFamily: SANS, fontSize: 28, color: C.ink3, marginTop: 14, opacity: prog(frame, 2.9, 0.6)}}>Demo data · 6 sample customers</div>
			</div>
		</Scene>
	);
};
