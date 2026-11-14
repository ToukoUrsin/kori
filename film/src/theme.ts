import {Easing, interpolate} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Geist';
import {loadFont as loadMono} from '@remotion/google-fonts/GeistMono';

export const FPS = 30;
export const W = 1920, H = 1080;
export const SANS = loadFont('normal', {weights: ['400', '500', '600', '700'], subsets: ['latin', 'latin-ext']}).fontFamily;
export const MONO = loadMono('normal', {weights: ['400', '500'], subsets: ['latin']}).fontFamily;

// the app's own colours (web/src/index.css)
export const C = {
	stage: 'oklch(0.935 0.009 95)',
	ground: 'oklch(0.972 0.006 95)',
	surface: 'oklch(0.995 0.002 95)',
	sunk: 'oklch(0.95 0.008 95)',
	line: 'oklch(0.905 0.009 95)',
	lineStrong: 'oklch(0.83 0.012 95)',
	ink: 'oklch(0.22 0.02 160)',
	ink2: 'oklch(0.4 0.018 160)',
	ink3: 'oklch(0.52 0.014 160)',
	brand: 'oklch(0.42 0.095 158)',
	brandStrong: 'oklch(0.34 0.08 158)',
	brandMid: 'oklch(0.62 0.11 158)',
	brandLine: 'oklch(0.86 0.05 158)',
	brandSoft: 'oklch(0.95 0.028 158)',
	fixed: 'oklch(0.4 0.1 265)',
	fixedSoft: 'oklch(0.945 0.022 265)',
	surprise: 'oklch(0.58 0.15 335)',
	surpriseSoft: 'oklch(0.95 0.028 335)',
	everyday: 'oklch(0.72 0.105 215)',
	everydaySoft: 'oklch(0.95 0.03 215)',
	everydayInk: 'oklch(0.42 0.08 225)',
	cushion: 'oklch(0.7 0.012 95)',
	neg: 'oklch(0.5 0.17 27)',
	negSoft: 'oklch(0.95 0.03 27)',
};

export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export const out = Easing.bezier(0.16, 1, 0.3, 1);
export const inOut = Easing.bezier(0.65, 0, 0.35, 1);
/** 0 → 1 from `at` seconds over `dur` seconds, eased out. */
export const prog = (frame: number, at: number, dur = 0.6, ease = out) => interpolate(frame, [at * FPS, (at + dur) * FPS], [0, 1], {...clamp, easing: ease});
/** fade and rise into place */
export const rise = (frame: number, at: number, dur = 0.6, dy = 28): React.CSSProperties => {
	const p = prog(frame, at, dur);
	return {opacity: p, transform: `translateY(${(1 - p) * dy}px)`};
};
export const eur = (n: number, digits = 0) => '€' + n.toLocaleString('en-GB', {minimumFractionDigits: digits, maximumFractionDigits: digits});
