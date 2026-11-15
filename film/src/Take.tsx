import React from 'react';
import {AbsoluteFill, Audio, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Mark, WaitCut} from './components';
import {C, FPS, MONO, SANS, clamp, inOut, out} from './theme';
import planJson from './data/take-plan.json';
import capsJson from './data/take-caps.json';
import usedJson from './data/take-used.json';

// The film cut around the founder's voice take. His words set the clock: the take is cut into three blocks (the first
// line over the cold open; the long middle; the ending), pauses tightened (scripts/take-plan.mjs), and every screen
// recording was made on that clock (scenarios/t-*.mjs), so a tap lands just before the words about its result.
// Everything on the stage is a recording of the real app; where a wait is cut, the cut is marked.

type Ev = {at: number; kind: string; label?: string; box?: {x: number; y: number; width: number; height: number}};
type Cap = {video: string; w: number; h: number; seconds: number; events: Ev[]; voice?: {file: string; start: number; lufs: number}};
const caps = capsJson.caps as unknown as Record<string, Cap>;
const GREEN = '#085C38';
const fr = (s: number) => Math.round(s * FPS);
const ev = (cap: string, kind: string, label?: string) => {
	const e = caps[cap].events.find((x) => x.kind === kind && (label === undefined || x.label === label));
	if (!e) throw new Error(`no event ${kind} ${label ?? ''} in ${cap}`);
	return e.at;
};

// ---- the take: parts kept, laid end to end in three blocks -------------------------------------------------------
const LEAD = 1.0;                                    // the scenarios start their clock this long before the block
const speech = {first: 5.824, firstEnd: 16.269, mid: 21.635, midEnd: 101.583, last: 107.45};
const partsOf = (b: number) => (planJson.parts as {from: number; to: number; block: number}[]).filter((p) => p.block === b);
const blockFrames = (b: number) => partsOf(b).reduce((a, p) => a + fr(p.to - p.from), 0);
/** seconds from the start of block `b` to take second `t` (a moment inside a cut lands on the cut) */
const inBlock = (b: number, t: number) => {
	let at = 0;
	for (const p of partsOf(b)) {
		if (t <= p.to) return (at + Math.max(0, fr(t - p.from))) / FPS;
		at += fr(p.to - p.from);
	}
	return at / FPS;
};

// ---- the timeline, in film seconds ---------------------------------------------------------------------------------
const B0 = 0.3;                                      // his first line starts over the cold open
const CUT = 9.0;                                     // inside the open's hold: a short dissolve to the stage
const DISSOLVE = 6;
const TAPF = CUT + 1.6;                              // the tap on the microphone, as his first line ends
const V = caps.voice;
const tapV = ev('voice', 'tap', 'talk');
const VCUT = TAPF + 0.8;                             // the sheet is open and connecting: that wait is cut (and marked)
const vTo = V.voice!.start + (usedJson.koriLines as [number, number, string][])[0][0] - 0.4;
const KA = VCUT - (vTo - V.voice!.start);            // Kori's voice clip starts
const kori = (usedJson.koriLines as [number, number, string][]).map(([s, e, text]) => ({s: KA + s, e: KA + e, text}));
const KEND = kori[kori.length - 1].e;
const B1 = KEND + 0.3 - (speech.mid - partsOf(1)[0].from);
// between the code and the proof he pauses (the take's own silence before the line, not tightened as much): the
// time goes to the proof sheet, whose last lines need reading
const GAP12 = 1.2;
const B2 = B1 + blockFrames(1) / FPS + GAP12;
const BLOCK = [B0, B1, B2];
/** the film second at which take second `t` is heard */
const filmOf = (t: number) => {
	const b = t < 20 ? 0 : t < 104 ? 1 : 2;
	return BLOCK[b] + inBlock(b, t);
};

// the chat recording runs on block 1's clock, the proof on block 2's
const chatF = (c: number) => B1 + (c - ev('chat', 'home') - LEAD);
const chatC = (f: number) => f - B1 + ev('chat', 'home') + LEAD;
const tapP = ev('proof', 'tap', 'tested');           // the tap on the card lands just before "And the number she started with"
const proofF = (c: number) => B2 - 0.2 + (c - tapP);
const VIN = KEND + 0.2;                              // the voice sheet → Home again
const SEND = chatF(ev('chat', 'send'));
const OATCUT = SEND + 0.9;                           // the wait for the fresh answer is cut here …
const OATDONE = filmOf(85.63) + 0.6;                 // … so that the finished screen lands on "2 euros and 5 cents"
const oatTo = ev('chat', 'done') - (OATDONE - OATCUT);
const oatWait = oatTo - chatC(OATCUT);
const LIN = filmOf(90.976) + 0.2;                    // the work view (a laptop page)
const LTAP = filmOf(92.18) - 0.35;
const tapL = ev('lab', 'tap', 'groceries');
const LCUT = filmOf(98.15) - 0.2;                    // "And each figure on screen…": the finished view, at the check line
const labTo = ev('lab', 'scroll') + 1.9;
const labWait = ev('lab', 'done') - (tapL + (LCUT - LTAP));   // the wait is up to the finished view; the rest is the scroll down
const PIN = B2 - 1.1;                                // the proof
const HIN = filmOf(112.686) + 0.7;                   // inside the bank app
const HTAP = HIN + 0.8;
const tapH = ev('host', 'tap', 'open Kori');
const E0 = filmOf(118.112) + 0.12;                   // the end card, after "Thank you for watching"
export const TAKE_TOTAL = fr(E0) + fr(capsJson.open.end);

type Seg = {cap: string; start: number; end: number; from: number; cut?: number; wide?: boolean};
const SEGS: Seg[] = [
	{cap: 'voice', start: CUT, end: VCUT, from: tapV - (TAPF - CUT)},
	{cap: 'voice', start: VCUT, end: VIN, from: vTo, cut: vTo - (tapV + VCUT - TAPF)},
	{cap: 'chat', start: VIN, end: OATCUT, from: chatC(VIN)},
	{cap: 'chat', start: OATCUT, end: LIN, from: oatTo, cut: oatWait},
	{cap: 'lab', start: LIN, end: LCUT, from: tapL - (LTAP - LIN), wide: true},
	{cap: 'lab', start: LCUT, end: PIN, from: labTo, cut: labWait, wide: true},
	{cap: 'proof', start: PIN, end: HIN, from: tapP - (B2 - 0.2 - PIN)},
	{cap: 'host', start: HIN, end: E0, from: tapH - (HTAP - HIN)},
];
const segAt = (t: number) => SEGS.find((s) => t >= s.start && t < s.end);

// ---- the camera ------------------------------------------------------------------------------------------------------
// The phone stands in the middle; the camera pushes in on it (k: screen px per app px; y: the app px at the middle of
// the picture area) and follows the action, so app text reads at 22 px and more. Below 900 px is the caption's.
const MIDY = 462, TOPM = 22, FLOOR = 884, PCX = 960;
const K = 1.65, WHOLE = 1.02;
type Key = {t: number; k: number; y: number; d?: number};
const cf = chatF;
const KEYS: Key[] = [
	// the match cut lands on Home's top block (the same label and number as the open's last frame), then out to the
	// whole phone for the tap on the microphone in the ask field
	{t: CUT - 1, k: K, y: 285, d: 0},
	{t: CUT + 0.6, k: WHOLE, y: 422, d: 0.7},
	// Kori speaks: its words and the card it is talking about
	{t: TAPF + 0.25, k: 1.6, y: 296, d: 0.6},
	// … and the camera goes where Kori's words are: the cycle that went over, the purchase, back to the question
	{t: kori[2].s - 0.2, k: 1.9, y: 335, d: 1.1},
	{t: kori[4].s - 0.3, k: 1.9, y: 452, d: 1.1},
	{t: kori[5].s - 0.3, k: 1.6, y: 296, d: 1.0},
	{t: VIN, k: K, y: 285, d: 0},
	{t: cf(ev('chat', 'tap', 'ask')) + 0.6, k: K, y: 548, d: 0.9},
	{t: cf(ev('chat', 'view', 'groceries')) + 0.05, k: K, y: 300, d: 0.8},
	{t: cf(ev('chat', 'scroll', 'lever')), k: K, y: 470, d: 1.0},
	{t: cf(ev('chat', 'view', 'eating out')) + 0.05, k: K, y: 300, d: 0.7},
	{t: cf(ev('chat', 'scroll', 'what would change it')), k: K, y: 455, d: 1.0},
	{t: cf(ev('chat', 'view', 'ten years')) + 0.05, k: K, y: 300, d: 0.7},
	{t: cf(ev('chat', 'scroll', 'fund')), k: K, y: 500, d: 1.2},
	// the pen (top right) and the laptop question (bottom) are 0.7 s apart: step back for both
	{t: cf(ev('chat', 'tap', 'new chat')) - 1.0, k: 1.2, y: 385, d: 0.8},
	{t: cf(ev('chat', 'view', 'laptop')) + 0.1, k: K, y: 300, d: 0.9},
	{t: cf(ev('chat', 'tap', 'field')) - 0.8, k: K, y: 575, d: 0.8},
	{t: SEND + 0.25, k: K, y: 300, d: 0.6},
	{t: OATCUT + 0.1, k: K, y: 480, d: 0.8},
	{t: PIN, k: K, y: 285, d: 0},
	{t: proofF(ev('proof', 'scroll')), k: 1.95, y: 560, d: 1.5},
	{t: HIN, k: 1.5, y: 300, d: 0},
	{t: HTAP + 1.9, k: 1.02, y: 422, d: 1.2},
];
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const camAt = (t: number) => {
	let st = {k: KEYS[0].k, y: KEYS[0].y};
	for (const key of KEYS) {
		if (t < key.t) break;
		const d = key.d ?? 0.7;
		const p = d <= 0 ? 1 : interpolate(t, [key.t, key.t + d], [0, 1], {...clamp, easing: inOut});
		st = {k: lerp(st.k, key.k, p), y: lerp(st.y, key.y, p)};
	}
	return st;
};
// the laptop page: scale s, the page point (x, y) at the middle of the picture area left of the circle
const WCX = 800;
type WKey = {t: number; s: number; x: number; y: number; d?: number};
const WKEYS: WKey[] = [
	{t: LIN - 1, s: 1.8, x: 492.6, y: 270, d: 0},
	{t: LCUT, s: 2.2, x: 390, y: 400, d: 0},
];
const wideAt = (t: number) => {
	let st = {s: WKEYS[0].s, x: WKEYS[0].x, y: WKEYS[0].y};
	for (const key of WKEYS) {
		if (t < key.t) break;
		const d = key.d ?? 0.7;
		const p = d <= 0 ? 1 : interpolate(t, [key.t, key.t + d], [0, 1], {...clamp, easing: inOut});
		st = {s: lerp(st.s, key.s, p), x: lerp(st.x, key.x, p), y: lerp(st.y, key.y, p)};
	}
	return st;
};

// ---- what he says (take seconds; spelling as in the brief) ---------------------------------------------------------
const SAID: [number, number, string][] = [
	[5.82, 9.6, 'Elli has €2,764 in her bank account,'],
	[10.3, 13.7, 'but only €1,357 of that'],
	[14.05, 16.3, 'is safe to spend before payday.'],
	[21.6, 24.1, 'Then she asks her own questions.'],
	[24.82, 28.4, 'She asks if her groceries could be cheaper.'],
	[28.74, 30.85, 'Kori puts every brand she buys'],
	[31.1, 32.4, 'next to the S Group product'],
	[32.97, 33.8, "that's the same thing,"],
	[34.25, 37.16, 'with real pictures and real Prisma prices.'],
	[38.21, 39.58, "That's €69 a month."],
	[40.21, 42.85, 'She keeps her coffee and the total updates.'],
	[43.83, 47.27, 'Kori also shows her the bigger cost: eating out.'],
	[47.87, 50.12, 'At €552 a month,'],
	[50.84, 54.4, 'two fewer visits saves €112.'],
	[55.19, 56.35, 'If she puts that aside,'],
	[56.67, 58.5, 'she sees ten years of it'],
	[59.11, 61.12, "in one of S-Pankki's own funds."],
	[62.02, 62.95, "That's an illustration,"],
	[63.15, 65.05, 'not actual investment advice.'],
	[66.51, 68.2, "Now she's looking at the new laptop."],
	[68.55, 72.35, 'Up to €287 keeps her at the usual pace.'],
	[73.05, 75.2, 'And up to €715 fits'],
	[75.4, 77.1, 'if she tightens up for a while.'],
	[77.75, 80.45, 'These are in Finnish shops now, at real prices.'],
	[81.66, 83.4, 'For anything else, she just types.'],
	[83.8, 87.0, 'Her oat drink costs €2.05.'],
	[87.8, 90.98, 'And the same thing is €1.15.'],
	[92.18, 93.76, 'Every number comes from code.'],
	[94.68, 98.0, 'Kori writes it and runs it on her own data.'],
	[98.15, 99.45, 'And each figure on screen'],
	[99.45, 101.58, 'traces back to that actual run.'],
	[107.45, 109.0, 'And the number she started with'],
	[109.0, 112.69, 'held on 17 of her last 18 paydays.'],
	[113.46, 116.4, 'We built Kori to go inside S-mobiili.'],
	[117.29, 118.11, 'Thank you for watching.'],
];
type Line = {s: number; e: number; text: string; kori?: boolean};
const LINES: Line[] = [...SAID.map(([s, e, text]) => ({s: filmOf(s) - 0.04, e: filmOf(e) + 0.3, text})), ...kori.map((l) => ({s: l.s - 0.04, e: l.e + 0.3, text: l.text, kori: true}))]
	.sort((a, b) => a.s - b.s)
	.map((l, i, all) => ({...l, e: i + 1 < all.length ? Math.min(l.e, all[i + 1].s - 0.03) : l.e}));

// ---- the pieces ------------------------------------------------------------------------------------------------------
const Ripples: React.FC<{cap: Cap; t: number; k: number}> = ({cap, t, k}) => (
	<>
		{cap.events
			.filter((e) => e.kind === 'tap' && e.box && t >= e.at - 0.05 && t < e.at + 0.5)
			.map((e, i) => {
				const p = Math.min(1, Math.max(0, (t - e.at) / 0.5));
				const cx = (e.box!.x + e.box!.width / 2) * k, cy = (e.box!.y + e.box!.height / 2) * k;
				const rad = (16 + 22 * p) * k;
				return <div key={i} style={{position: 'absolute', left: cx - rad, top: cy - rad, width: rad * 2, height: rad * 2, borderRadius: rad, background: 'oklch(0.22 0.02 160 / 0.32)', opacity: 1 - p}} />;
			})}
	</>
);

const PhoneStage: React.FC = () => {
	const frame = useCurrentFrame();
	const t = frame / FPS;
	const seg = segAt(t);
	if (!seg || seg.wide) return null;
	const {k, y} = camAt(t);
	const sw = 390 * k, sh = 844 * k, b = Math.round(7 * k);
	const h = sh + 2 * b;
	const top = h <= FLOOR - TOPM ? TOPM : Math.max(FLOOR - h, Math.min(TOPM, MIDY - b - y * k));
	const r = 44 * k;
	return (
		<div style={{position: 'absolute', left: PCX - sw / 2 - b, top, width: sw + 2 * b, height: h, borderRadius: r + b, background: 'oklch(0.18 0.012 160)', boxShadow: '0 2px 4px oklch(0.22 0.02 160 / 0.10), 0 40px 80px -24px oklch(0.22 0.02 160 / 0.30)'}}>
			<div style={{position: 'absolute', left: b, top: b, width: sw, height: sh, borderRadius: r, overflow: 'hidden', background: C.ground}}>
				{SEGS.filter((s) => !s.wide).map((s, i) => (
					<Sequence key={i} from={fr(s.start)} durationInFrames={fr(s.end) - fr(s.start)} layout="none" name={`${s.cap} ${s.from.toFixed(1)}`}>
						<OffthreadVideo src={staticFile(caps[s.cap].video)} trimBefore={fr(s.from)} muted style={{position: 'absolute', left: 0, top: 0, width: sw, height: sh}} />
					</Sequence>
				))}
				<Ripples cap={caps[seg.cap]} t={seg.from + (t - seg.start)} k={k} />
			</div>
		</div>
	);
};

const WideStage: React.FC = () => {
	const frame = useCurrentFrame();
	const t = frame / FPS;
	const seg = segAt(t);
	if (!seg || !seg.wide) return null;
	const cap = caps[seg.cap];
	const {s, x, y} = wideAt(t);
	return (
		<div style={{position: 'absolute', left: WCX - x * s, top: MIDY - y * s, width: cap.w * s, height: cap.h * s}}>
			{SEGS.filter((g) => g.wide).map((g, i) => (
				<Sequence key={i} from={fr(g.start)} durationInFrames={fr(g.end) - fr(g.start)} layout="none" name={`${g.cap} ${g.from.toFixed(1)}`}>
					<OffthreadVideo src={staticFile(cap.video)} trimBefore={fr(g.from)} muted style={{position: 'absolute', left: 0, top: 0, width: cap.w * s, height: cap.h * s}} />
				</Sequence>
			))}
			<Ripples cap={cap} t={seg.from + (t - seg.start)} k={s} />
		</div>
	);
};

// who is talking: the founder's camera, or Kori's mark while Kori talks
const CIRCLE = 220, CX = 1750, CY = 898;
const fade = (t: number, a: number, b: number, d = 0.3) => Math.min(interpolate(t, [a, a + d], [0, 1], clamp), interpolate(t, [b - d, b], [1, 0], clamp));
const FACE_ON: [number, number][] = [[CUT + 0.1, kori[0].s - 0.3], [B1 - 0.35, E0 + 1]];
const KORI_ON: [number, number] = [kori[0].s - 0.35, VIN + 0.05];
const placed = [0, 1, 2].flatMap((b) => {
	let at = fr(BLOCK[b]);
	const ps = partsOf(b);
	return ps.map((p, i) => {
		const frames = fr(p.to - p.from);
		// the picture runs a little before the first part of a block and after its last, so the circle can fade
		const pre = i === 0 ? [0, 14, fr(GAP12) - 10][b] : 0, post = i === ps.length - 1 ? [18, 12, 0][b] : 0;
		const x = {start: at, frames, from: p.from, pre, post};
		at += frames;
		return x;
	});
});
const Face: React.FC = () => {
	const t = useCurrentFrame() / FPS;
	const op = Math.max(...FACE_ON.map(([a, b]) => fade(t, a, b)));
	const kop = fade(t, KORI_ON[0], KORI_ON[1]);
	const ring: React.CSSProperties = {position: 'absolute', left: CX - CIRCLE / 2, top: CY - CIRCLE / 2, width: CIRCLE, height: CIRCLE, borderRadius: CIRCLE, overflow: 'hidden', boxShadow: `0 0 0 4px ${C.surface}, 0 14px 36px -14px oklch(0.22 0.02 160 / 0.45)`};
	return (
		<>
			<div style={{...ring, opacity: op, background: C.sunk}}>
				{placed.map((p, i) => (
					<Sequence key={i} from={p.start - p.pre} durationInFrames={p.frames + p.pre + p.post} layout="none">
						<OffthreadVideo src={staticFile('take/face.mp4')} trimBefore={fr(p.from) - p.pre} muted style={{position: 'absolute', left: 0, top: 0, width: CIRCLE, height: CIRCLE}} />
					</Sequence>
				))}
			</div>
			{kop > 0 ? (
				<div style={{...ring, opacity: kop, background: GREEN, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
					<Mark size={104} color="oklch(0.972 0.006 95)" />
				</div>
			) : null}
		</>
	);
};

/** A small label in the app's own chip style, above the circle. */
const Label: React.FC<{from: number; to: number; icon: React.ReactNode; beside?: boolean; children: React.ReactNode}> = ({from, to, icon, beside, children}) => {
	const t = useCurrentFrame() / FPS;
	const op = fade(t, from, to);
	if (op <= 0) return null;
	return (
		<div style={{position: 'absolute', right: beside ? 1920 - (CX - CIRCLE / 2) + 22 : 1920 - (CX + CIRCLE / 2) - 4, top: beside ? 822 : 694, opacity: op, display: 'flex', alignItems: 'center', gap: 12, fontFamily: SANS, fontSize: 28, fontWeight: 500, color: C.ink, background: C.surface, border: `1.5px solid ${C.lineStrong}`, borderRadius: 999, padding: '9px 20px 9px 16px', whiteSpace: 'nowrap', transform: `translateY(${(1 - op) * 8}px)`}}>
			{icon}
			{children}
		</div>
	);
};
const WaveIcon = (
	<svg width={28} height={28} viewBox="0 0 24 24">
		{[5, 9.5, 14, 18.5].map((x, i) => {
			const h = [8, 16, 11, 6][i];
			return <rect key={i} x={x - 1.3} y={12 - h / 2} width={2.6} height={h} rx={1.3} fill={GREEN} />;
		})}
	</svg>
);
const CodeIcon = (
	<svg width={28} height={28} viewBox="0 0 24 24">
		<path d="M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5" fill="none" stroke={GREEN} strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
	</svg>
);

const Captions: React.FC = () => {
	const t = useCurrentFrame() / FPS;
	const l = LINES.find((x) => t >= x.s && t < x.e);
	if (!l) return null;
	const op = Math.min(interpolate(t, [l.s, l.s + 0.1], [0, 1], clamp), interpolate(t, [l.e - 0.1, l.e], [1, 0], clamp));
	return (
		<div style={{position: 'absolute', left: 240, width: 1440, bottom: 38, display: 'flex', justifyContent: 'center', opacity: op}}>
			<div style={{display: 'flex', alignItems: 'center', gap: 14, fontFamily: SANS, fontSize: 44, fontWeight: 500, lineHeight: 1.2, color: 'oklch(0.972 0.006 95)', padding: l.kori ? '11px 30px 11px 22px' : '11px 30px', borderRadius: 18, background: l.kori ? GREEN : 'oklch(0.22 0.02 160 / 0.94)', letterSpacing: '-0.012em', whiteSpace: 'nowrap'}}>
				{l.kori ? <Mark size={40} color="oklch(0.972 0.006 95)" /> : null}
				{l.text}
			</div>
		</div>
	);
};

const fadeEdge = (f: number, n: number) => interpolate(f, [0, 1, n - 1, n], [0, 1, 1, 0], clamp);

export const Take: React.FC = () => {
	const frame = useCurrentFrame();
	const t = frame / FPS;
	const openEnd = fr(CUT) + DISSOLVE;
	const endCard = t >= E0;
	return (
		<AbsoluteFill style={{background: C.ground}}>
			{/* the stage */}
			{t >= CUT - 0.1 && !endCard ? (
				<>
					<PhoneStage />
					<WideStage />
					<div style={{position: 'absolute', left: 0, right: 0, top: 880, height: 200, background: `linear-gradient(to bottom, oklch(0.972 0.006 95 / 0) 0, ${C.ground} 46px, ${C.ground} 100%)`}} />
					{SEGS.map((s, i) =>
						s.cut ? (
							<Sequence key={i} from={fr(s.start)} durationInFrames={60} layout="none">
								<div style={{position: 'absolute', right: 1920 - (CX + CIRCLE / 2) - 4, top: 612}}>
									<WaitCut seconds={s.cut} />
								</div>
							</Sequence>
						) : null,
					)}
					<Label from={KORI_ON[0]} to={KORI_ON[1]} icon={WaveIcon}>Voice: ElevenLabs</Label>
					<Label from={LIN + 0.25} to={PIN} icon={CodeIcon} beside>Gemini writes this code</Label>
					<Face />
				</>
			) : null}

			{/* the cold open, as it is in its folder; its own sound runs to its end under his first line */}
			<Sequence from={0} durationInFrames={openEnd} layout="none" name="cold open">
				<AbsoluteFill style={{opacity: interpolate(frame, [fr(CUT), openEnd], [1, 0], clamp)}}>
					<OffthreadVideo src={staticFile('open/open.mp4')} muted style={{width: 1920, height: 1080}} />
				</AbsoluteFill>
			</Sequence>
			<Sequence from={0} durationInFrames={fr(capsJson.open.seconds)} layout="none" name="cold open sound">
				<Audio src={staticFile('open/open.mp4')} volume={(f) => 0.5 * interpolate(f, [fr(capsJson.open.seconds) - 12, fr(capsJson.open.seconds)], [1, 0], clamp)} />
			</Sequence>

			{/* the end card */}
			<Sequence from={fr(E0)} layout="none" name="end card">
				<AbsoluteFill>
					<OffthreadVideo src={staticFile('open/end.mp4')} muted style={{width: 1920, height: 1080}} />
				</AbsoluteFill>
			</Sequence>

			<Captions />

			{/* his voice, part by part; Kori's real voice from the recording */}
			{placed.map((p, i) => (
				<Sequence key={i} from={p.start} durationInFrames={p.frames} layout="none" name={`take ${p.from.toFixed(1)}`}>
					<Audio src={staticFile('take/voice.wav')} trimBefore={fr(p.from)} volume={(f) => fadeEdge(f, p.frames)} />
				</Sequence>
			))}
			<Sequence from={fr(KA)} durationInFrames={fr(VIN - KA)} layout="none" name="Kori's voice">
				<Audio src={staticFile(V.voice!.file)} volume={(f) => interpolate(f, [fr(VIN - KA) - 6, fr(VIN - KA)], [1, 0], clamp)} />
			</Sequence>
		</AbsoluteFill>
	);
};

// for the log: where everything lands
export const takeTimes = {CUT, TAPF, VCUT, vCut: vTo - (tapV + VCUT - TAPF), KA, KEND, B1, SEND, OATCUT, OATDONE, oatWait, LIN, LTAP, LCUT, labWait, B2, PIN, HIN, HTAP, E0, total: TAKE_TOTAL / FPS};
void MONO; void out;
