// The Today screen, top to bottom: the number, what the balance is spoken for, the forecast, the baskets.
export default {
	lang: 'en',
	path: '/',
	async run({page, wait, mark, shot}) {
		await wait(2600);
		await shot('today');
		mark('scroll');
		// the page scrolls inside the app shell: find what actually scrolls and move it smoothly
		await page.evaluate(async () => {
			const all = [document.scrollingElement, ...document.querySelectorAll('*')].filter(Boolean);
			const el = all.filter((e) => e.scrollHeight > e.clientHeight + 200 && /(auto|scroll)/.test(getComputedStyle(e).overflowY) || e === document.scrollingElement)
				.sort((a, b) => b.scrollHeight - b.clientHeight - (a.scrollHeight - a.clientHeight))[0];
			const max = el.scrollHeight - el.clientHeight;
			const t0 = performance.now(), dur = 9000;
			await new Promise((res) => {
				const step = (now) => {
					const p = Math.min(1, (now - t0) / dur);
					el.scrollTop = max * (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2);
					p < 1 ? requestAnimationFrame(step) : res();
				};
				requestAnimationFrame(step);
			});
		});
		await wait(1200);
	},
};
