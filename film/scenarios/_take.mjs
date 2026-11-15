// Helpers for the scenarios of the take film (scenarios/t-*.mjs): a clock to act on cue, smooth scrolling, buttons list.
export const clock = (wait) => {
	const t0 = Date.now();
	/** wait until `t` seconds after the scenario started */
	return async (t) => {
		const d = t * 1000 - (Date.now() - t0);
		if (d > 0) await wait(d);
	};
};
/** Scroll `sel` by `by` px (or to `to`) over `dur` ms, eased, like a thumb. Returns the new scrollTop. */
export const scroll = (page, sel, {by, to, dur = 1200}) =>
	page.evaluate(async ({sel, by, to, dur}) => {
		const el = document.querySelector(sel);
		const from = el.scrollTop, max = el.scrollHeight - el.clientHeight;
		const target = Math.max(0, Math.min(max, to !== undefined ? to : from + by));
		const t0 = performance.now();
		await new Promise((res) => {
			const step = (now) => {
				const p = Math.min(1, (now - t0) / dur);
				el.scrollTop = from + (target - from) * (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2);
				p < 1 ? requestAnimationFrame(step) : res();
			};
			requestAnimationFrame(step);
		});
		return el.scrollTop;
	}, {sel, by, to, dur});
/** Scroll `sel` so that the locator's top lands at page y `y`. */
export const bring = async (page, sel, loc, y, dur = 1200) => {
	const box = await loc.boundingBox();
	if (!box) return null;
	return scroll(page, sel, {by: box.y - y, dur});
};
export const buttons = (page) =>
	page.evaluate(() => [...document.querySelectorAll('button, a, textarea, [role=dialog]')].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.y < 844 && r.y > -10; })
		.map((e) => { const r = e.getBoundingClientRect(); return `${e.tagName.toLowerCase()} @${Math.round(r.x)},${Math.round(r.y)} ${Math.round(r.width)}x${Math.round(r.height)} "${e.getAttribute('aria-label') || ''}" "${(e.innerText || '').replace(/\s+/g, ' ').slice(0, 70)}"`; }).join('\n'));

// ---- the cut of the voice take (scripts/take-plan.mjs): where a moment of the take lands in its block of the film
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
const plan = JSON.parse(fs.readFileSync(fileURLToPath(new URL('../src/data/take-plan.json', import.meta.url)), 'utf8'));
/** seconds from the start of block `block` (0 the first line, 1 the long middle, 2 the ending) to take second `t` */
export const inBlock = (block, t) => {
	let at = 0;
	for (const p of plan.parts.filter((x) => x.block === block)) {
		if (t <= p.to) return at + Math.max(0, t - p.from);
		at += p.to - p.from;
	}
	return at;
};
