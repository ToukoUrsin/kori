// Part B, why the numbers are right: a typed question, the answer, then "N numbers checked" opened (where each
// figure came from), held three seconds.
export default {
	lang: 'en',
	path: '/?customer=CUST00092',
	async run({page, tap, type, wait, mark, shot}) {
		await wait(1200);
		await tap(page.getByRole('button', {name: 'Talk to the coach'}), {label: 'open coach'});
		await wait(700);
		await type('textarea, input[type="text"]', 'What is safe for me to spend this week?');
		await page.waitForFunction(() => document.querySelectorAll('[data-turn="coach"]:not([data-pending])').length > 0, null, {timeout: 60000});
		mark('answered');
		await wait(1800);
		const figures = page.locator('[data-figures]').last();
		await figures.scrollIntoViewIfNeeded();
		await wait(600);
		await tap(figures, {label: 'numbers checked'});
		mark('figures');
		await wait(3000);
		await shot('figures');
	},
};
