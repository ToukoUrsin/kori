import React from 'react';
import {Sequence, interpolate, useCurrentFrame} from 'remotion';
import {Chip, Cross, Eyebrow, H1, Provenance, Scene, Tick} from '../components';
import {btMonths, cue, home, lineAt} from '../data';
import {Footage, sceneSec, type Clip} from '../footage';
import {C, FPS, MONO, clamp, eur, inOut, out, prog, rise} from '../theme';
import {X0} from './Open';

// a beat of a scene: in at `a`, out at `b` (seconds). The old one is gone before the next one comes in,
// so two headlines are never on top of each other
const beat = (frame: number, a: number, b = 1e9, d = 0.35) => Math.min(prog(frame, a + 0.06, d), 1 - prog(frame, b - 0.16, 0.2, inOut));

// ---------------------------------------------------------------- 4. why the numbers are right
// the app's 19 calculations (backend/kori/ai/tools.py); 8 are shown
const TOOLS = ['safe_to_spend', 'can_i_afford', 'what_if', 'baskets', 'spending', 'balance_forecast', 'compare_with_peers', 'track_record'];
const TOOL_COUNT = 19;
// the engine's numbers (the app's own home data) and the typed answer as the `figures` recording shows it
const SAFE = home.safe;
const ANSWER = 'It is safe for you to spend €319 this week. That works out to €46 a day until payday…';
// a wrong number, from the app's own test (backend/tests/test_agent.py, test_wrong_twice_is_withheld)
const WRONG = {draft: '1,700', retry: '1,300'};

/** The model picks, plain code computes, every number is checked; and what happens to a wrong one, slowly. */
export const MathScene: React.FC<{dur: number; figures: Clip[]}> = ({dur, figures}) => {
	const frame = useCurrentFrame();
	const t2 = lineAt('math', 1) - 0.25, t3 = lineAt('math', 2) - 0.15;
	const tPick = cue('math', 0, 'picks') - 0.1;
	const tCheck = cue('math', 2, 'checked') - 0.2, tFail = cue('math', 2, 'one') - 0.15;
	const X = 96;
	const A = beat(frame, 0, t2), B = beat(frame, t2, t3), Cc = beat(frame, t3, tFail), D = beat(frame, tFail);
	const pick = prog(frame, tPick, 0.4);
	const nums = ['319', '46'];
	return (
		<Scene dur={dur}>
			{/* A: Gemini picks one of the calculations */}
			<div style={{position: 'absolute', left: X, right: X, top: 150, opacity: A}}>
				<H1 size={110} style={rise(frame, 0.1, 0.6)}>The AI never does the math.</H1>
				<div style={{fontSize: 48, fontWeight: 600, letterSpacing: '-0.02em', color: C.ink2, marginTop: 70, ...rise(frame, cue('math', 0, 'gemini') - 0.25, 0.5, 14)}}>
					Gemini picks one of {TOOL_COUNT} calculations
				</div>
				<div style={{display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 30, maxWidth: 1600, ...rise(frame, cue('math', 0, 'gemini'), 0.5, 14)}}>
					{TOOLS.map((tool, i) => {
						const on = i === 0 ? pick : 0;
						return (
							<div key={tool} style={{fontFamily: MONO, fontSize: 34, padding: '10px 20px', borderRadius: 14, border: `2px solid ${on > 0.5 ? C.brand : C.line}`, background: on > 0.5 ? C.brand : C.surface, color: on > 0.5 ? 'white' : C.ink2, opacity: i === 0 ? 1 : interpolate(pick, [0, 1], [1, 0.4]), transform: `scale(${1 + 0.08 * Math.sin(Math.PI * on)})`}}>{tool}()</div>
						);
					})}
					<div style={{fontFamily: MONO, fontSize: 34, padding: '10px 6px', color: C.ink3, opacity: interpolate(pick, [0, 1], [1, 0.4])}}>+{TOOL_COUNT - TOOLS.length} more</div>
				</div>
			</div>

			{/* B: plain code runs it; the app's own figure sheet, punched in */}
			<div style={{opacity: B}}>
				<Sequence from={Math.round(t2 * FPS)} layout="none">
					<Footage clips={figures} audio={false} />
				</Sequence>
				<div style={{position: 'absolute', left: X0, right: 96, top: 170}}>
					<Eyebrow>Then plain code, no model</Eyebrow>
					<div style={{fontFamily: MONO, fontSize: 52, fontWeight: 500, color: C.brandStrong, marginTop: 26}}>safe_to_spend()</div>
					<div style={{marginTop: 26, borderTop: `2px solid ${C.line}`}}>
						{[
							['safe until payday', SAFE.amount],
							['this week', SAFE.this_week],
							['per day', SAFE.per_day],
						].map(([k, v], i) => (
							<div key={k as string} style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '20px 0', borderBottom: `2px solid ${C.line}`, ...rise(frame, t2 + 0.5 + i * 0.3, 0.45, 12)}}>
								<span style={{fontSize: 44, fontWeight: 500, color: C.ink2}}>{k}</span>
								<span style={{fontFamily: MONO, fontSize: 56, fontWeight: 500, color: C.ink}}>{eur(v as number, 2)}</span>
							</div>
						))}
					</div>
					<div style={{fontSize: 36, fontWeight: 500, color: C.ink3, marginTop: 26, ...rise(frame, t2 + 1.4, 0.45, 10)}}>From her real transactions</div>
				</div>
			</div>

			{/* C: every number in the answer is checked */}
			<div style={{position: 'absolute', left: X, right: X, top: 170, opacity: Cc}}>
				<Eyebrow>Every number in the answer is checked</Eyebrow>
				<div style={{fontSize: 68, fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1.3, marginTop: 40, maxWidth: 1600}}>
					“
					{ANSWER.split(/(\d+)/).map((part, i) => {
						const k = nums.indexOf(part);
						if (k < 0) return <span key={i}>{part}</span>;
						const p = prog(frame, tCheck + k * 0.3, 0.35);
						return (
							<span key={i} style={{display: 'inline-flex', alignItems: 'center', gap: 10, padding: '0 14px', margin: '0 4px', borderRadius: 14, background: p > 0.05 ? C.brandSoft : C.sunk, color: C.brandStrong}}>
								{part}
								<span style={{display: 'inline-flex', width: 50 * p, overflow: 'hidden'}}><Tick size={50} p={p} /></span>
							</span>
						);
					})}
					”
				</div>
				<div style={{display: 'flex', alignItems: 'center', gap: 14, marginTop: 44, ...rise(frame, tCheck + 0.7, 0.45, 10)}}>
					<Tick size={40} />
					<span style={{fontSize: 40, fontWeight: 600}}>Both are in the engine’s result. The answer is shown.</span>
				</div>
			</div>

			{/* D: a wrong number, step by step, held long enough to read */}
			<div style={{position: 'absolute', left: X, right: X, top: 150, opacity: D}}>
				<Eyebrow>And when one does not match · from the app’s tests</Eyebrow>
				<div style={{display: 'flex', alignItems: 'center', gap: 22, marginTop: 40, fontSize: 60, fontWeight: 600, letterSpacing: '-0.03em', color: C.ink2}}>
					“You can safely spend about
					<span style={{display: 'inline-flex', alignItems: 'center', gap: 12, padding: '2px 18px', borderRadius: 14, background: C.negSoft, color: C.neg, textDecoration: prog(frame, tFail + 0.4, 0.3) > 0.5 ? 'line-through' : 'none'}}>
						€{WRONG.draft}
						<span style={{display: 'inline-flex', width: 46 * prog(frame, tFail + 0.4, 0.3), overflow: 'hidden'}}><Cross size={46} /></span>
					</span>
					until payday.”
				</div>
				<div style={{display: 'flex', alignItems: 'center', gap: 20, marginTop: 44}}>
					<div style={rise(frame, tFail + 0.7, 0.45, 12)}><Chip size={36}>not in any result</Chip></div>
					<Arrow p={prog(frame, tFail + 0.9, 0.3)} />
					<div style={rise(frame, tFail + 1.0, 0.45, 12)}><Chip size={36}>rewritten once: €{WRONG.retry}</Chip></div>
					<Arrow p={prog(frame, tFail + 1.2, 0.3)} />
					<div style={rise(frame, tFail + 1.3, 0.45, 12)}><Chip size={36} tone="neg">still wrong: answer held back</Chip></div>
				</div>
				<div style={{marginTop: 96, ...rise(frame, tFail + 1.6, 0.6, 18)}}>
					<H1 size={76}>A wrong number is stopped before you hear it.</H1>
					<div style={{fontSize: 36, fontWeight: 500, color: C.ink3, marginTop: 22}}>She sees the engine’s card with the real figures instead.</div>
				</div>
			</div>
		</Scene>
	);
};
const Arrow: React.FC<{p: number}> = ({p}) => (
	<svg width={54} height={36} viewBox="0 0 60 40" style={{opacity: p, flex: 'none'}}>
		<path d="M4 20h44M36 8l14 12-14 12" fill="none" stroke={C.ink3} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="90" strokeDashoffset={90 * (1 - p)} />
	</svg>
);

// ---------------------------------------------------------------- 5. the proof: the one big moment
const MONTH = (k: string) => new Date(k + '-01T00:00:00Z').toLocaleString('en-GB', {month: 'short', timeZone: 'UTC'});
const M = btMonths.months;
const fmt = (n: number) => Math.round(n).toLocaleString('en-GB');
/** a running total through the months: at p ∈ [0, 1] across the eleven months, value `key` (eased inside each month) */
const through = (p: number, key: 'cases_total' | 'customers_total' | 'safe_held_pct_total' | 'balance_held_pct_total') => {
	const x = p * M.length;
	const i = Math.min(M.length - 1, Math.floor(x));
	const prev = i === 0 ? 0 : M[i - 1][key];
	return prev + (M[i][key] - prev) * Math.min(1, x - i);
};

const BAR_W = 1480;
/** Was "safe to spend" actually safe? The replay of every customer, month by month, as a counter and two bars. */
export const Proof: React.FC<{dur: number}> = ({dur}) => {
	const frame = useCurrentFrame();
	const t = frame / FPS;
	// the counter runs through the eleven months while the narrator says "we replayed it on 4,850 customers"
	const c0 = cue('proof', 0, 'replayed') - 0.1, c1 = cue('proof', 0, 'customers') + 0.35;
	const cp = interpolate(t, [c0, c1], [0, 1], {...clamp, easing: inOut});
	const mi = Math.min(M.length - 1, Math.floor(cp * M.length * 0.999));
	// the bars race through the same months; the big numbers land on the spoken words
	const r0 = lineAt('proof', 1) + 0.1, tSafe = cue('proof', 1, 'ninety'), tBal = cue('proof', 2, 'twenty');
	const rp = interpolate(t, [r0, tSafe], [0, 1], {...clamp, easing: inOut});
	const up = prog(frame, r0 - 0.5, 0.7, inOut); // the counters move up out of the bars' way
	const safeP = rp === 0 ? 0 : through(rp, 'safe_held_pct_total') * interpolate(rp, [0, 0.12], [0, 1], clamp);
	const balP = rp === 0 ? 0 : through(rp, 'balance_held_pct_total') * interpolate(rp, [0, 0.12], [0, 1], clamp);
	const land = (at: number) => ({p: prog(frame, at - 0.05, 0.35), pop: interpolate(t, [at - 0.05, at + 0.12, at + 0.4], [0.6, 1.08, 1], {...clamp, easing: out})});
	const s = land(tSafe), b = land(tBal);
	const big = {fontSize: 160, fontWeight: 600, letterSpacing: '-0.05em', lineHeight: 1, fontVariantNumeric: 'tabular-nums' as const};
	return (
		<Scene dur={dur}>
			<div style={{position: 'absolute', left: 0, right: 0, top: 70, textAlign: 'center', ...rise(frame, 0.1, 0.5, 14)}}>
				<Provenance style={{justifyContent: 'center'}}>Backtest on history the coach could not see</Provenance>
				<H1 size={96} style={{marginTop: 20, opacity: 1 - up}}>Is the number any good?</H1>
			</div>
			{/* the counter */}
			<div style={{position: 'absolute', left: 0, right: 0, top: interpolate(up, [0, 1], [330, 150]), display: 'flex', justifyContent: 'center', gap: interpolate(up, [0, 1], [140, 70]), transform: `scale(${interpolate(up, [0, 1], [1, 0.62])})`, transformOrigin: '50% 0', opacity: prog(frame, c0 - 0.3, 0.4)}}>
				<Counter n={cp === 0 ? 0 : through(cp, 'cases_total')} label="past dates replayed" />
				<Counter n={cp === 0 ? 0 : through(cp, 'customers_total')} label="customers" />
			</div>
			{/* the months */}
			<div style={{position: 'absolute', left: 0, right: 0, top: interpolate(up, [0, 1], [640, 360]), display: 'flex', justifyContent: 'center', gap: 14, opacity: prog(frame, c0 - 0.3, 0.4)}}>
				{M.map((m, i) => {
					const on = cp > 0 && i <= mi;
					const now = i === mi && cp > 0 && cp < 1;
					return (
						<div key={m.month} style={{width: 108, textAlign: 'center', fontSize: 32, fontWeight: 600, color: on ? (now ? C.brand : C.ink) : C.lineStrong, borderTop: `6px solid ${on ? C.brand : C.line}`, paddingTop: 10}}>
							{MONTH(m.month)}
							{i === 0 || m.month.endsWith('-01') ? <div style={{fontSize: 28, fontWeight: 500, color: C.ink3}}>{m.month.slice(0, 4)}</div> : null}
						</div>
					);
				})}
			</div>
			{/* the two bars */}
			<div style={{position: 'absolute', left: (1920 - BAR_W) / 2, top: 530, width: BAR_W, opacity: up}}>
				<Race y={0} label="Spend what Kori says is safe" pct={safeP} color={C.brand} strong />
				<Race y={210} label="Spend your balance" pct={balP} color={C.cushion} />
				<div style={{position: 'absolute', right: 0, top: -28, textAlign: 'right', opacity: s.p, transform: `scale(${s.pop})`, transformOrigin: '100% 50%'}}>
					<div style={{...big, color: C.brand}}>{Math.round(btMonths.promise.safe_held_pct)} %</div>
				</div>
				<div style={{position: 'absolute', right: 0, top: 182, textAlign: 'right', opacity: b.p, transform: `scale(${b.pop})`, transformOrigin: '100% 50%'}}>
					<div style={{...big, color: C.ink3}}>{Math.round(btMonths.promise.balance_as_budget_held_pct)} %</div>
				</div>
			</div>
			<div style={{position: 'absolute', left: 0, right: 0, top: 900, textAlign: 'center', fontSize: 32, color: C.ink3, opacity: prog(frame, tSafe + 0.6, 0.6)}}>
				Stayed above zero until the next pay: {btMonths.promise.safe_held_pct} % vs {btMonths.promise.balance_as_budget_held_pct} % of {fmt(btMonths.promise.cases)} cases
			</div>
		</Scene>
	);
};
const Counter: React.FC<{n: number; label: string}> = ({n, label}) => (
	<div style={{textAlign: 'center'}}>
		<div style={{fontSize: 190, fontWeight: 600, letterSpacing: '-0.05em', lineHeight: 1, fontVariantNumeric: 'tabular-nums'}}>{fmt(n)}</div>
		<div style={{fontSize: 46, fontWeight: 500, color: C.ink2, marginTop: 10}}>{label}</div>
	</div>
);
const Race: React.FC<{y: number; label: string; pct: number; color: string; strong?: boolean}> = ({y, label, pct, color, strong}) => (
	<div style={{position: 'absolute', left: 0, top: y, width: BAR_W - 420}}>
		<div style={{fontSize: 48, fontWeight: 600, letterSpacing: '-0.02em', color: strong ? C.ink : C.ink2}}>{label}</div>
		<div style={{marginTop: 18, height: 60, borderRadius: 16, background: C.sunk, overflow: 'hidden', border: `2px solid ${C.line}`}}>
			<div style={{width: `${pct}%`, height: '100%', background: color, borderRadius: 14}} />
		</div>
	</div>
);

// ---------------------------------------------------------------- 6. it teaches
const BASKETS = [
	{key: 'fixed', name: 'Fixed musts', what: 'Rent, bills. Same every month.', color: C.fixed, soft: C.fixedSoft},
	{key: 'surprise', name: 'Surprise musts', what: 'The dentist, a broken phone.', color: C.surprise, soft: C.surpriseSoft},
	{key: 'everyday', name: 'Everyday', what: 'Food, coffee, fun. The one she steers.', color: C.everyday, soft: C.everydaySoft},
];
/** Baskets, a lesson she has to say back, and how she compares with people like her. Footage left, beats right. */
export const Teach: React.FC<{dur: number; clips: Clip[]}> = ({dur, clips}) => {
	const frame = useCurrentFrame();
	const t2 = lineAt('teach', 1) - 0.2, t3 = lineAt('teach', 2) - 0.2;
	const at = [cue('teach', 0, 'fixed'), cue('teach', 0, 'surprise'), cue('teach', 0, 'everyday')];
	const steps = [
		{t: lineAt('teach', 1), label: 'She sorts her own payments'},
		{t: cue('teach', 1, 'say'), label: 'Says it back in her own words'},
		{t: cue('teach', 1, 'grades'), label: 'Graded honestly: “Not yet” is allowed'},
	];
	return (
		<Scene dur={dur}>
			<Footage clips={clips} />
			<div style={{position: 'absolute', left: X0, right: 96, top: 84, opacity: beat(frame, 0, t2)}}>
				<Eyebrow>It teaches</Eyebrow>
				<H1 size={80} style={{marginTop: 16}}>Three baskets.</H1>
				<div style={{display: 'flex', flexDirection: 'column', gap: 20, marginTop: 40}}>
					{BASKETS.map((bk, i) => {
						const amount = home.baskets.baskets.find((x) => x.key === bk.key)?.amount ?? 0;
						return (
							<div key={bk.key} style={{display: 'flex', alignItems: 'center', gap: 30, background: bk.soft, borderRadius: 24, padding: '22px 32px', borderLeft: `12px solid ${bk.color}`, ...rise(frame, at[i] - 0.2, 0.5, 20)}}>
								<div style={{flex: 1}}>
									<div style={{fontSize: 48, fontWeight: 600, letterSpacing: '-0.025em'}}>{bk.name}</div>
									<div style={{fontSize: 32, color: C.ink2, marginTop: 4}}>{bk.what}</div>
								</div>
								<div style={{textAlign: 'right'}}>
									<div style={{fontSize: 52, fontWeight: 600, letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums'}}>{eur(amount)}</div>
									<div style={{fontSize: 28, color: C.ink3}}>this month</div>
								</div>
							</div>
						);
					})}
				</div>
			</div>
			<div style={{position: 'absolute', left: X0, right: 96, top: 84, opacity: beat(frame, t2, t3)}}>
				<Eyebrow>Lessons</Eyebrow>
				<H1 size={80} style={{marginTop: 16}}>Say it back.<br />Graded honestly.</H1>
				<div style={{display: 'flex', flexDirection: 'column', gap: 26, marginTop: 56}}>
					{steps.map((st, i) => {
						const p = prog(frame, st.t - 0.1, 0.4);
						return (
							<div key={i} style={{display: 'flex', alignItems: 'center', gap: 20, opacity: interpolate(p, [0, 1], [0.3, 1])}}>
								<Tick size={46} p={p} />
								<div style={{fontSize: 42, fontWeight: 600, letterSpacing: '-0.02em'}}>{st.label}</div>
							</div>
						);
					})}
				</div>
			</div>
			<div style={{position: 'absolute', left: X0, right: 96, top: 84, opacity: beat(frame, t3)}}>
				<Eyebrow>People like her</Eyebrow>
				<H1 size={80} style={{marginTop: 16}}>Compared with<br />people like her.</H1>
				<div style={{display: 'flex', gap: 16, marginTop: 50, flexWrap: 'wrap', ...rise(frame, cue('teach', 2, 'statistics') - 0.2, 0.5, 14)}}>
					<Chip size={40} tone="brand">Statistics Finland data</Chip>
					<Chip size={40} mono>compare_with_peers()</Chip>
				</div>
			</div>
		</Scene>
	);
};

// ---------------------------------------------------------------- 7. inside the bank app
/** The host app: footage left; the steps (from the slot's beats) light up as they are seen. */
export const Host: React.FC<{dur: number; clips: Clip[]; beats: {cap: string; at: number; label: string}[]}> = ({dur, clips, beats}) => {
	const frame = useCurrentFrame();
	const t = frame / FPS;
	const at = beats.map((b) => sceneSec(clips, b.cap, b.at) ?? 1e9);
	// the phone stays on into the last card: only the words leave
	const away = interpolate(frame, [dur - 7, dur], [1, 0], clamp);
	return (
		<Scene dur={dur} fadeOut={false}>
			<Footage clips={clips} stripOp={away} />
			<div style={{position: 'absolute', left: X0, right: 96, top: 84, opacity: away}}>
				<Provenance live style={rise(frame, 0.05, 0.5, 12)}>Recorded live · real speed</Provenance>
				<H1 size={84} style={{marginTop: 24, ...rise(frame, 0.15, 0.6)}}>Made to sit<br />inside S-mobiili.</H1>
				<div style={{display: 'flex', flexDirection: 'column', gap: 24, marginTop: 52}}>
					{beats.map((b, i) => {
						const on = interpolate(t, [at[i] - 0.1, at[i] + 0.3], [0, 1], clamp);
						const now = on > 0 && (i === beats.length - 1 || t < at[i + 1] - 0.1);
						return (
							<div key={i} style={{display: 'flex', alignItems: 'center', gap: 22, opacity: interpolate(on, [0, 1], [0.3, 1])}}>
								<Tick size={46} p={on} />
								<div style={{fontSize: 46, fontWeight: 600, letterSpacing: '-0.025em', color: now ? C.ink : C.ink2}}>{b.label}</div>
							</div>
						);
					})}
				</div>
			</div>
		</Scene>
	);
};
