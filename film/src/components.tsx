import React from 'react';
import {Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {C, FPS, MONO, SANS, clamp, out, prog} from './theme';
import type {Cap} from './data';

/** The Kori mark: three bars (the same as in the app). */
export const Mark: React.FC<{size: number; color?: string; levels?: number[]}> = ({size, color = C.brand, levels}) => {
	const h = [0.55, 1, 0.42];
	return (
		<svg width={size} height={size} viewBox="0 0 20 20">
			{h.map((v, i) => {
				const hh = 14 * (levels ? levels[i] ?? v : v);
				return <rect key={i} x={3.5 + i * 5} y={17 - hh} width={3} height={hh} rx={1.5} fill={color} />;
			})}
		</svg>
	);
};

export const Eyebrow: React.FC<{children: React.ReactNode; color?: string; style?: React.CSSProperties}> = ({children, color = C.ink3, style}) => (
	<div style={{fontFamily: SANS, fontSize: 26, fontWeight: 600, letterSpacing: '0.09em', textTransform: 'uppercase', color, ...style}}>{children}</div>
);
export const H1: React.FC<{children: React.ReactNode; size?: number; style?: React.CSSProperties}> = ({children, size = 84, style}) => (
	<div style={{fontFamily: SANS, fontSize: size, fontWeight: 600, letterSpacing: '-0.035em', lineHeight: 1.04, color: C.ink, ...style}}>{children}</div>
);

const phoneW = (h: number) => {
	const b = Math.round(h * 0.013);
	return {b, w: Math.round(((h - 2 * b) * 390) / 844) + 2 * b};
};
export const phoneWidth = (h: number) => phoneW(h).w;

/** A phone showing a recording (or a still). Lives inside a <Sequence>: frame 0 is second `from` of the recording. */
export const Phone: React.FC<{
	h: number;
	cap?: Cap;
	still?: string;
	from?: number;
	rate?: number;
	taps?: boolean;
	style?: React.CSSProperties;
}> = ({h, cap, still, from = 0, rate = 1, taps = true, style}) => {
	const frame = useCurrentFrame();
	const {b, w} = phoneW(h);
	const sw = w - 2 * b, sh = h - 2 * b;
	const k = sw / 390;
	const t = from + (frame / FPS) * rate;
	const r = Math.round(h * 0.062);
	return (
		<div style={{position: 'relative', width: w, height: h, borderRadius: r, background: 'oklch(0.18 0.012 160)', boxShadow: '0 2px 4px oklch(0.22 0.02 160 / 0.10), 0 40px 80px -24px oklch(0.22 0.02 160 / 0.32)', ...style}}>
			<div style={{position: 'absolute', left: b, top: b, width: sw, height: sh, borderRadius: r - b, overflow: 'hidden', background: C.ground}}>
				{cap ? (
					<OffthreadVideo src={staticFile(cap.video)} trimBefore={Math.round(from * FPS)} playbackRate={rate} muted style={{width: sw, height: sh, objectFit: 'cover', objectPosition: 'top'}} />
				) : still ? (
					<Img src={staticFile(still)} style={{width: sw, height: sh, objectFit: 'cover', objectPosition: 'top'}} />
				) : null}
				{cap && taps
					? cap.events
							.filter((e) => e.kind === 'tap' && e.box && t >= e.at - 0.05 && t < e.at + 0.5 * rate)
							.map((e, i) => {
								const p = (t - e.at) / (0.5 * rate);
								const cx = (e.box!.x + e.box!.width / 2) * k, cy = (e.box!.y + e.box!.height / 2) * k;
								const rad = (16 + 22 * Math.min(1, Math.max(0, p))) * k;
								return <div key={i} style={{position: 'absolute', left: cx - rad, top: cy - rad, width: rad * 2, height: rad * 2, borderRadius: rad, background: 'oklch(0.22 0.02 160 / 0.32)', opacity: 1 - Math.max(0, p)}} />;
							})
					: null}
			</div>
		</div>
	);
};

/** Words that light up as they are spoken. `t` is the clock the word times are in. */
export const Spoken: React.FC<{words: {w: string; s: number; e: number}[]; t: number; size: number; color?: string; weight?: number; dim?: number; style?: React.CSSProperties}> = ({words, t, size, color = C.ink, weight = 600, dim = 0.2, style}) => (
	<div style={{fontFamily: SANS, fontSize: size, fontWeight: weight, letterSpacing: '-0.022em', lineHeight: 1.2, color, ...style}}>
		{words.map((w, i) => (
			<span key={i} style={{opacity: interpolate(t, [w.s - 0.08, w.s + 0.1], [dim, 1], clamp)}}>
				{w.w}{' '}
			</span>
		))}
	</div>
);

export const Chip: React.FC<{children: React.ReactNode; tone?: 'plain' | 'brand' | 'neg'; mono?: boolean; size?: number; style?: React.CSSProperties}> = ({children, tone = 'plain', mono, size = 26, style}) => {
	const t = tone === 'brand' ? {bg: C.brandSoft, fg: C.brandStrong, bd: C.brandLine} : tone === 'neg' ? {bg: C.negSoft, fg: C.neg, bd: 'oklch(0.86 0.06 27)'} : {bg: C.surface, fg: C.ink2, bd: C.line};
	return (
		<div style={{display: 'inline-flex', alignItems: 'center', gap: 10, fontFamily: mono ? MONO : SANS, fontSize: size, fontWeight: 500, color: t.fg, background: t.bg, border: `1.5px solid ${t.bd}`, borderRadius: 999, padding: `${Math.round(size * 0.32)}px ${Math.round(size * 0.7)}px`, whiteSpace: 'nowrap', ...style}}>{children}</div>
	);
};

export const Tick: React.FC<{size?: number; color?: string; p?: number}> = ({size = 28, color = C.brand, p = 1}) => (
	<svg width={size} height={size} viewBox="0 0 24 24" style={{flex: 'none'}}>
		<circle cx="12" cy="12" r="11" fill={color} opacity={p} />
		<path d="M7 12.5l3.2 3.2L17 9" fill="none" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="16" strokeDashoffset={16 * (1 - p)} />
	</svg>
);
export const Cross: React.FC<{size?: number}> = ({size = 28}) => (
	<svg width={size} height={size} viewBox="0 0 24 24" style={{flex: 'none'}}>
		<circle cx="12" cy="12" r="11" fill={C.neg} />
		<path d="M8 8l8 8M16 8l-8 8" stroke="white" strokeWidth="2.4" strokeLinecap="round" />
	</svg>
);

/** A scene: fades in and out over the paper-coloured ground. */
export const Scene: React.FC<{dur: number; children: React.ReactNode}> = ({dur, children}) => {
	const frame = useCurrentFrame();
	const op = Math.min(interpolate(frame, [0, 9], [0, 1], {...clamp, easing: out}), interpolate(frame, [dur - 7, dur], [1, 0], clamp));
	return <div style={{position: 'absolute', inset: 0, opacity: op, fontFamily: SANS, color: C.ink}}>{children}</div>;
};
export {prog};
