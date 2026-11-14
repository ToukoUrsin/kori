import React from 'react';
import {Sequence, interpolate, useCurrentFrame} from 'remotion';
import {Chip, Cross, Eyebrow, H1, Phone, Scene, Tick, phoneWidth} from '../components';
import {backtest, caps, cue, home, lineAt} from '../data';
import {C, FPS, MONO, clamp, eur, out, prog, rise} from '../theme';
import {VOICE_CAP, voiceSegs} from './Voice';

const S = home.safe;
const TOOLS = ['safe_to_spend', 'what_if', 'baskets', 'spending', 'compare_with_peers', 'track_record', 'spender_profile', 'balance_forecast'];

const Box: React.FC<{x: number; w: number; n: string; who: string; does: string; style?: React.CSSProperties; children: React.ReactNode}> = ({x, w, n, who, does, style, children}) => (
	<div style={{position: 'absolute', left: x, top: 300, width: w, height: 430, background: C.surface, border: `1.5px solid ${C.line}`, borderRadius: 28, padding: '34px 38px', boxSizing: 'border-box', boxShadow: '0 1px 2px oklch(0.22 0.02 160 / 0.05), 0 18px 40px -18px oklch(0.22 0.02 160 / 0.18)', ...style}}>
		<div style={{display: 'flex', alignItems: 'center', gap: 14}}>
			<div style={{width: 40, height: 40, borderRadius: 20, background: C.ink, color: C.ground, fontSize: 22, fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>{n}</div>
			<div style={{fontSize: 26, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: C.ink3}}>{who}</div>
		</div>
		<div style={{fontSize: 42, fontWeight: 600, letterSpacing: '-0.03em', marginTop: 16, marginBottom: 22}}>{does}</div>
		{children}
	</div>
);
const Arrow: React.FC<{x: number; p: number}> = ({x, p}) => (
	<svg width={60} height={40} viewBox="0 0 60 40" style={{position: 'absolute', left: x, top: 495, opacity: p}}>
		<path d="M4 20h44M36 8l14 12-14 12" fill="none" stroke={C.ink3} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="90" strokeDashoffset={90 * (1 - p)} />
	</svg>
);

/** The model picks, the engine computes, the check decides. With the answer just heard. */
export const MathScene: React.FC<{dur: number}> = ({dur}) => {
	const frame = useCurrentFrame();
	const t1 = cue('math', 0, 'gemini') - 0.2, t2 = lineAt('math', 1) - 0.1, t3 = lineAt('math', 2) - 0.1;
	const tCheck = cue('math', 2, 'checked') - 0.25, tFail = cue('math', 2, 'one') - 0.2;
	const seg = voiceSegs(caps[VOICE_CAP])[0];
	const sentence = seg.answer.text.split(/(?<=\.)\s/).slice(0, 2).join(' ');
	const W3 = 536, G = 60, X = 96;
	const nums = [String(Math.round(S.this_week)), String(Math.round(S.per_day))];
	const pick = prog(frame, t1 + 0.9, 0.4);
	return (
		<Scene dur={dur}>
			<div style={{position: 'absolute', left: X, top: 84}}>
				<Eyebrow style={rise(frame, 0.05, 0.5, 14)}>Under the hood</Eyebrow>
				<H1 size={96} style={{marginTop: 14, ...rise(frame, 0.15, 0.6)}}>The AI never does the math.</H1>
			</div>
			<Box x={X} w={W3} n="1" who="Gemini" does="picks the calculation" style={rise(frame, t1, 0.6)}>
				<div style={{display: 'flex', flexWrap: 'wrap', gap: 10}}>
					{TOOLS.map((tool, i) => (
						<div key={tool} style={{fontFamily: MONO, fontSize: 23, padding: '8px 14px', borderRadius: 12, border: `1.5px solid ${i === 0 ? interpolate(pick, [0, 1], [0, 1]) > 0.5 ? C.brand : C.line : C.line}`, background: i === 0 && pick > 0.5 ? C.brand : C.surface, color: i === 0 && pick > 0.5 ? 'white' : C.ink2, opacity: i === 0 ? 1 : interpolate(pick, [0, 1], [1, 0.45])}}>{tool}</div>
					))}
					<div style={{fontFamily: MONO, fontSize: 23, padding: '8px 4px', color: C.ink3, opacity: interpolate(pick, [0, 1], [1, 0.45])}}>+5 more</div>
				</div>
			</Box>
			<Arrow x={X + W3} p={prog(frame, t2 - 0.25, 0.5)} />
			<Box x={X + W3 + G} w={W3} n="2" who="Engine" does="computes it" style={rise(frame, t2, 0.6)}>
				{[
					['this_week', S.this_week],
					['per_day', S.per_day],
					['safe_to_spend', S.amount],
				].map(([k, v], i) => (
					<div key={k as string} style={{display: 'flex', justifyContent: 'space-between', fontFamily: MONO, fontSize: 30, padding: '9px 0', borderBottom: `1.5px solid ${C.line}`, ...rise(frame, t2 + 0.35 + i * 0.18, 0.45, 10)}}>
						<span style={{color: C.ink3}}>{k}</span>
						<span style={{color: C.ink, fontWeight: 500}}>{(v as number).toLocaleString('en-GB', {minimumFractionDigits: 2})}</span>
					</div>
				))}
				<div style={{fontSize: 24, color: C.ink3, marginTop: 18, ...rise(frame, t2 + 0.9, 0.45, 10)}}>Plain code on her real transactions. No model.</div>
			</Box>
			<Arrow x={X + 2 * W3 + G} p={prog(frame, t3 - 0.25, 0.5)} />
			<Box x={X + 2 * (W3 + G)} w={W3} n="3" who="Number check" does="checks every number" style={rise(frame, t3, 0.6)}>
				<div style={{fontSize: 30, lineHeight: 1.42, color: C.ink2, fontWeight: 500}}>
					{sentence.split(/(\d+)/).map((part, i) => {
						const k = nums.indexOf(part);
						if (k < 0) return <span key={i}>{part}</span>;
						const p = prog(frame, tCheck + k * 0.35, 0.35);
						return (
							<span key={i} style={{display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0 10px 0 8px', margin: '0 2px', borderRadius: 10, background: p > 0.05 ? C.brandSoft : C.sunk, color: C.ink, fontWeight: 600, verticalAlign: 'baseline'}}>
								{part}
								<span style={{display: 'inline-flex', width: 24 * p, overflow: 'hidden'}}><Tick size={24} p={p} /></span>
							</span>
						);
					})}
				</div>
			</Box>
			{/* and when a number is wrong */}
			<div style={{position: 'absolute', left: X, right: X, top: 790, display: 'flex', alignItems: 'center', gap: 22, ...rise(frame, tFail, 0.6)}}>
				<div style={{fontSize: 34, fontWeight: 500, color: C.ink2, display: 'flex', alignItems: 'center', gap: 12}}>
					“…about
					<span style={{display: 'inline-flex', alignItems: 'center', gap: 8, padding: '2px 12px', borderRadius: 10, background: C.negSoft, color: C.neg, fontWeight: 600, textDecoration: prog(frame, tFail + 0.5, 0.3) > 0.5 ? 'line-through' : 'none'}}>
						350 <Cross size={26} />
					</span>
					euros this week.”
				</div>
				<div style={{flex: 1, height: 2, background: C.line}} />
				<div style={{...rise(frame, tFail + 0.7, 0.5, 12)}}><Chip size={28}>not in the result</Chip></div>
				<div style={{...rise(frame, tFail + 1.1, 0.5, 12)}}><Chip size={28}>rewritten once</Chip></div>
				<div style={{...rise(frame, tFail + 1.5, 0.5, 12)}}><Chip size={28} tone="neg">still wrong: answer held back</Chip></div>
			</div>
		</Scene>
	);
};

const PCT_W = 1010;
const Bar: React.FC<{y: number; label: string; pct: number; color: string; at: number; land: number; strong?: boolean}> = ({y, label, pct, color, at, land, strong}) => {
	const frame = useCurrentFrame();
	const p = interpolate(frame, [at * FPS, land * FPS], [0, 1], {...clamp, easing: out});
	return (
		<div style={{position: 'absolute', left: 0, top: y, width: PCT_W, ...rise(frame, at - 0.2, 0.5, 16)}}>
			<div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
				<div style={{fontSize: 38, fontWeight: 600, letterSpacing: '-0.02em', color: strong ? C.ink : C.ink2}}>{label}</div>
				<div style={{fontSize: strong ? 120 : 84, fontWeight: 600, letterSpacing: '-0.045em', lineHeight: 1, color: strong ? C.brand : C.ink3, fontVariantNumeric: 'tabular-nums'}}>{(pct * p).toFixed(1)}%</div>
			</div>
			<div style={{marginTop: 14, height: 36, borderRadius: 12, background: C.sunk, overflow: 'hidden', border: `1.5px solid ${C.line}`}}>
				<div style={{width: `${pct * p}%`, height: '100%', background: color, borderRadius: 10}} />
			</div>
		</div>
	);
};

/** Was "safe to spend" actually safe? The replay on every customer, and the same question asked in the app. */
export const Proof: React.FC<{dur: number}> = ({dur}) => {
	const frame = useCurrentFrame();
	const cap = caps.track;
	const PH = 900;
	const x0 = 150 + phoneWidth(PH) + 110;
	const from = 7.4;
	const rate = Math.min(1, (cap.seconds - from - 0.3) / (dur / FPS));
	return (
		<Scene dur={dur}>
			<div style={{position: 'absolute', left: 150, top: 50, ...rise(frame, 0.05, 0.7, 40)}}>
				<Phone h={PH} cap={cap} from={from} rate={rate} />
			</div>
			<div style={{position: 'absolute', left: x0, top: 96, width: PCT_W}}>
				<Eyebrow style={rise(frame, 0.1, 0.5, 14)}>Backtest · {backtest.customers.toLocaleString('en-GB')} customers · {backtest.cases.toLocaleString('en-GB')} replays</Eyebrow>
				<H1 size={84} style={{marginTop: 16, ...rise(frame, 0.2, 0.6)}}>Is “safe to spend”<br />really safe?</H1>
				<div style={{position: 'relative', marginTop: 56}}>
					<Bar y={0} label="Spend what Kori calls safe" pct={backtest.promise.safe_held_pct} color={C.brand} at={lineAt('proof', 1)} land={cue('proof', 1, 'ninety') + 0.5} strong />
					<Bar y={250} label="Treat the balance as the budget" pct={backtest.promise.balance_as_budget_held_pct} color={C.cushion} at={lineAt('proof', 2)} land={cue('proof', 2, 'twenty') + 0.5} />
				</div>
				<div style={{position: 'absolute', top: 760, fontSize: 30, lineHeight: 1.35, color: C.ink3, ...rise(frame, lineAt('proof', 1) + 0.6, 0.6, 14)}}>
					Share of cases where the account stayed above zero until the next pay arrived.<br />Anyone can ask the app the same thing: “Was this number right before?”
				</div>
			</div>
		</Scene>
	);
};

const BASKETS = [
	{key: 'fixed', name: 'Fixed musts', what: 'Rent, housing, utilities. Same every month.', color: C.fixed, soft: C.fixedSoft},
	{key: 'surprise', name: 'Surprise musts', what: 'The dentist. The washing machine.', color: C.surprise, soft: C.surpriseSoft},
	{key: 'everyday', name: 'Everyday', what: 'Food, coffees, rides, fun. The one you steer.', color: C.everyday, soft: C.everydaySoft},
];
/** It teaches: the three baskets, a lesson on your own numbers, say it back, graded. */
export const Teach: React.FC<{dur: number}> = ({dur}) => {
	const frame = useCurrentFrame();
	const cap = caps.lesson;
	const PH = 900;
	const x0 = 150 + phoneWidth(PH) + 110;
	const rate = (cap.seconds - 1.2) / (dur / FPS);
	const at = [cue('teach', 0, 'fixed'), cue('teach', 0, 'surprise'), cue('teach', 0, 'everyday')];
	const steps = [
		{t: lineAt('teach', 1), label: 'A lesson on your own numbers'},
		{t: cue('teach', 1, 'say'), label: 'Say it back in your own words'},
		{t: cue('teach', 1, 'coach'), label: 'The coach grades it'},
	];
	return (
		<Scene dur={dur}>
			<div style={{position: 'absolute', left: 150, top: 50, ...rise(frame, 0.05, 0.7, 40)}}>
				<Phone h={PH} cap={cap} from={1.0} rate={rate} />
			</div>
			<div style={{position: 'absolute', left: x0, right: 96, top: 96}}>
				<Eyebrow style={rise(frame, 0.1, 0.5, 14)}>Financial literacy</Eyebrow>
				<H1 size={84} style={{marginTop: 16, ...rise(frame, 0.2, 0.6)}}>It teaches,<br />in three baskets.</H1>
				<div style={{display: 'flex', gap: 22, marginTop: 50}}>
					{BASKETS.map((b, i) => {
						const amount = home.baskets.baskets.find((x) => x.key === b.key)?.usual ?? 0;
						return (
							<div key={b.key} style={{flex: 1, height: 262, background: b.soft, borderRadius: 24, padding: '26px 28px', boxSizing: 'border-box', borderTop: `10px solid ${b.color}`, ...rise(frame, at[i] - 0.15, 0.55, 26)}}>
								<div style={{fontSize: 38, fontWeight: 600, letterSpacing: '-0.025em'}}>{b.name}</div>
								<div style={{fontSize: 25, lineHeight: 1.3, color: C.ink2, marginTop: 10, height: 66}}>{b.what}</div>
								<div style={{fontSize: 40, fontWeight: 600, letterSpacing: '-0.03em', marginTop: 16, fontVariantNumeric: 'tabular-nums'}}>
									{eur(amount)}
									<span style={{fontSize: 24, fontWeight: 500, color: C.ink3, letterSpacing: 0}}> a month</span>
								</div>
							</div>
						);
					})}
				</div>
				<div style={{marginTop: 46, display: 'flex', flexDirection: 'column', gap: 16}}>
					{steps.map((s, i) => {
						const p = prog(frame, s.t - 0.1, 0.4);
						return (
							<div key={i} style={{display: 'flex', alignItems: 'center', gap: 18, opacity: interpolate(p, [0, 1], [0.3, 1])}}>
								<Tick size={38} p={p} />
								<div style={{fontSize: 38, fontWeight: 600, letterSpacing: '-0.02em'}}>{s.label}</div>
							</div>
						);
					})}
				</div>
			</div>
		</Scene>
	);
};

/** Where it lives: a mobile web view, in Finnish, honest about a partial view. */
export const Fit: React.FC<{dur: number}> = ({dur}) => {
	const frame = useCurrentFrame();
	const PH = 1040;
	const pw = phoneWidth(PH);
	const gap = (1920 - 2 * 110 - 3 * pw) / 2;
	const items = [
		{at: 0.15, label: 'Voice or text, in a mobile web view', el: (d: number) => <Phone h={PH} cap={caps.chat} from={1.2} rate={(caps.chat.seconds - 1.6) / (d / FPS)} />},
		{at: cue('fit', 0, 'finnish') - 0.5, label: 'Finnish and English', el: () => <Phone h={PH} still="cap/still-fi.png" />},
		{at: lineAt('fit', 1) - 0.2, label: 'Honest about a partial view (PSD2)', el: () => <Phone h={PH} still="cap/still-jari.png" />},
	];
	return (
		<Scene dur={dur}>
			<div style={{position: 'absolute', left: 110, top: 70}}>
				<Eyebrow style={rise(frame, 0.05, 0.5, 14)}>Mobile web · embeddable</Eyebrow>
				<H1 size={84} style={{marginTop: 12, ...rise(frame, 0.15, 0.6)}}>Made to sit inside S-mobiili.</H1>
			</div>
			{items.map((it, i) => {
				const p = prog(frame, it.at, 0.9);
				const start = Math.max(0, Math.round(it.at * FPS));
				return (
					<div key={i} style={{position: 'absolute', left: 110 + i * (pw + gap), top: 268, width: pw, opacity: Math.min(1, p * 1.4), transform: `translateY(${(1 - p) * 160}px)`}}>
						<div style={{fontSize: 30, fontWeight: 600, letterSpacing: '-0.015em', color: C.ink2, textAlign: 'center', marginBottom: 20, whiteSpace: 'nowrap'}}>{it.label}</div>
						<Sequence from={start} layout="none">
							{it.el(dur - start)}
						</Sequence>
					</div>
				);
			})}
		</Scene>
	);
};
