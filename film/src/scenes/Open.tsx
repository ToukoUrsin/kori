import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import {Chip, H1, Mark, Scene} from '../components';
import {cue, home, lineAt} from '../data';
import {C, FPS, MONO, SANS, clamp, eur, inOut, out, prog, rise} from '../theme';

const S = home.safe;
const part = (k: string) => S.spoken_for.find((p) => p.key === k)?.amount ?? 0;
const BAR_W = 1560, BAR_X = 180, BAR_Y = 452, BAR_H = 104;
const SEGS = [
	{key: 'fixed', label: 'Rent and bills due', color: C.fixed},
	{key: 'surprise', label: 'Surprise reserve', color: C.surprise},
	{key: 'cushion', label: 'Cushion', color: C.cushion},
	{key: 'safe', label: 'Safe to spend', color: C.brand},
	{key: 'buffer', label: 'Buffer', color: C.brandLine},
].map((s) => ({...s, amount: part(s.key)}));

/** 0–15 s: the balance, what it is already spoken for, and the one number that is hers. */
export const Hook: React.FC<{dur: number}> = ({dur}) => {
	const frame = useCurrentFrame();
	const tMove = lineAt('hook', 1) - 0.15;                 // "But rent, bills…"
	const at: Record<string, number> = {
		fixed: cue('hook', 1, 'rent'),
		surprise: cue('hook', 1, 'surprises'),
		cushion: cue('hook', 1, 'come'),
		buffer: cue('hook', 1, 'before') + 0.25,
		safe: cue('hook', 2, 'hers') - 0.1,
	};
	const tNum = cue('hook', 2, 'one') - 0.1;
	const tLine = lineAt('hook', 3) - 0.1;
	const move = prog(frame, tMove, 0.9, inOut);
	const count = interpolate(frame, [0.25 * FPS, 1.7 * FPS], [0, S.balance], {...clamp, easing: out});
	const whole = Math.floor(count), cents = String(Math.round((count - whole) * 100)).padStart(2, '0');
	const numSize = interpolate(move, [0, 1], [300, 150]);
	const numY = interpolate(move, [0, 1], [372, 190]);
	const spot = prog(frame, at.safe + 0.5, 0.6);
	const gone = prog(frame, tLine - 0.1, 0.4);
	let x = 0;
	return (
		<Scene dur={dur}>
			{/* the balance */}
			<div style={{opacity: 1 - gone}}>
				<div style={{position: 'absolute', left: 0, right: 0, top: numY - 78 + (1 - move) * 8, textAlign: 'center', fontSize: interpolate(move, [0, 1], [40, 30]), fontWeight: 500, color: C.ink3, ...rise(frame, 0.05, 0.5, 16)}}>On Aino’s account today</div>
				<div style={{position: 'absolute', left: 0, right: 0, top: numY, textAlign: 'center', fontSize: numSize, fontWeight: 600, letterSpacing: '-0.045em', lineHeight: 1, fontVariantNumeric: 'tabular-nums', opacity: prog(frame, 0.1, 0.4)}}>
					{eur(whole)}
					<span style={{fontSize: numSize * 0.42, color: C.ink3, letterSpacing: '-0.03em'}}>.{cents}</span>
				</div>
			</div>
			{/* the line to remember takes its place */}
			<div style={{position: 'absolute', left: 0, right: 0, top: 196, textAlign: 'center', ...rise(frame, tLine + 0.15, 0.7, 30)}}>
				<H1 size={100}>Your balance is not your budget.</H1>
			</div>
			<div style={{position: 'absolute', left: BAR_X, top: BAR_Y - 54, width: BAR_W, textAlign: 'right', fontSize: 30, fontWeight: 500, color: C.ink3, opacity: gone}}>
				On her account <span style={{color: C.ink, fontWeight: 600}}>{eur(S.balance, 2)}</span>
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
			{/* what each part is */}
			<div style={{position: 'absolute', left: BAR_X, top: BAR_Y + BAR_H + 26, width: BAR_W, display: 'flex', gap: 56, opacity: interpolate(spot, [0, 1], [1, 0.5])}}>
				{SEGS.filter((s) => s.key !== 'safe').map((s) => (
					<div key={s.key} style={{display: 'flex', alignItems: 'center', gap: 14, fontSize: 32, fontWeight: 500, color: C.ink2, ...rise(frame, at[s.key], 0.5, 14)}}>
						<div style={{width: 20, height: 20, borderRadius: 6, background: s.key === 'buffer' ? C.brandLine : s.color}} />
						{s.label}
						<span style={{color: C.ink, fontWeight: 600, fontVariantNumeric: 'tabular-nums'}}>{eur(s.amount)}</span>
					</div>
				))}
			</div>
			{/* the number that is hers */}
			<div style={{position: 'absolute', left: BAR_X + ((part('fixed') + part('surprise') + part('cushion')) / S.balance) * BAR_W, top: BAR_Y + BAR_H + 108, ...rise(frame, tNum, 0.6, 24)}}>
				<div style={{fontSize: 34, fontWeight: 600, color: C.brand}}>Safe to spend until payday</div>
				<div style={{display: 'flex', alignItems: 'baseline', gap: 28}}>
					<div style={{fontSize: 190, fontWeight: 600, letterSpacing: '-0.045em', lineHeight: 1.02, color: C.brand, fontVariantNumeric: 'tabular-nums'}}>{eur(Math.round(S.amount))}</div>
					<div style={{fontSize: 40, fontWeight: 500, color: C.ink2}}>{eur(S.per_day)} a day</div>
				</div>
			</div>
		</Scene>
	);
};

/** The name. */
export const Title: React.FC<{dur: number}> = ({dur}) => {
	const frame = useCurrentFrame();
	const lv = [0, 1, 2].map((i) => interpolate(prog(frame, 0.1 + i * 0.09, 0.7), [0, 1], [0.08, [0.55, 1, 0.42][i]]));
	return (
		<Scene dur={dur}>
			<div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 34}}>
				<div style={{display: 'flex', alignItems: 'center', gap: 26}}>
					<Mark size={210} levels={lv} />
					<div style={{fontSize: 250, fontWeight: 600, letterSpacing: '-0.055em', lineHeight: 1, ...rise(frame, 0.2, 0.7, 30)}}>Kori</div>
				</div>
				<div style={{fontSize: 56, fontWeight: 500, letterSpacing: '-0.025em', color: C.ink2, ...rise(frame, cue('title', 0, 'a') - 0.1, 0.6)}}>A voice coach for your own bank account.</div>
				<div style={{display: 'flex', gap: 18, marginTop: 18, ...rise(frame, cue('title', 0, 'works'), 0.6)}}>
					<Chip size={30}>Voice by ElevenLabs</Chip>
					<Chip size={30}>Reasoning by Gemini</Chip>
					<Chip size={30} tone="brand">Made for S-mobiili</Chip>
				</div>
			</div>
		</Scene>
	);
};

/** The last card. */
export const End: React.FC<{dur: number}> = ({dur}) => {
	const frame = useCurrentFrame();
	return (
		<Scene dur={dur}>
			<div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 30}}>
				<div style={{display: 'flex', alignItems: 'center', gap: 14, ...rise(frame, 0.1, 0.6)}}>
					<Mark size={96} />
					<div style={{fontSize: 110, fontWeight: 600, letterSpacing: '-0.05em', lineHeight: 1}}>Kori</div>
				</div>
				<H1 size={104} style={{textAlign: 'center', ...rise(frame, cue('end', 0, 'your') - 0.15, 0.7)}}>Your balance is not your budget.</H1>
				<div style={{marginTop: 26, fontFamily: MONO, fontSize: 50, fontWeight: 500, color: C.brandStrong, background: C.brandSoft, border: `2px solid ${C.brandLine}`, borderRadius: 22, padding: '20px 44px', ...rise(frame, 1.9, 0.6)}}>kori-coach.fly.dev</div>
				<div style={{display: 'flex', gap: 16, marginTop: 10, ...rise(frame, 2.3, 0.6)}}>
					<Chip size={28}>Voice by ElevenLabs Agents</Chip>
					<Chip size={28}>Reasoning by Gemini</Chip>
					<Chip size={28} mono>github.com/ToukoUrsin/kori</Chip>
				</div>
				<div style={{fontFamily: SANS, fontSize: 28, color: C.ink3, marginTop: 14, opacity: prog(frame, 2.7, 0.6)}}>Junction 2026 · S-Pankki challenge: Personal Economic Trainer</div>
			</div>
		</Scene>
	);
};
