// Part B, it teaches: the three baskets on the Baskets tab, then a typed what-if (eating out 20% less) and its card.
export default {
	lang: 'en',
	path: '/?customer=CUST00092#baskets',
	async run({page, tap, type, wait, mark, shot}) {
		await wait(1500);
		mark('baskets');
		await wait(4500);
		await shot('baskets');
		await tap(page.getByRole('button', {name: 'Talk to the coach'}), {label: 'open coach'});
		await wait(700);
		await type('textarea, input[type="text"]', 'How much could I save if I reduced dining out by 20%?');
		await page.waitForFunction(() => document.querySelectorAll('[data-turn="coach"]:not([data-pending])').length > 0, null, {timeout: 60000});
		mark('answered');
		await wait(1500);
		await page.locator('[data-turn="coach"]').last().scrollIntoViewIfNeeded();
		mark('card');
		await wait(4000);
		await shot('whatif');
	},
};
