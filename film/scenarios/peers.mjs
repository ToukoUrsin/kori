// Part B, teach: the "people like you" comparison (Statistics Finland's household survey), held on the card.
export default {
	lang: 'en',
	path: '/?customer=CUST00092',
	async run({page, tap, type, wait, mark, shot}) {
		await wait(1200);
		await tap(page.getByRole('button', {name: 'Talk to the coach'}), {label: 'open coach'});
		await wait(700);
		await type('textarea, input[type="text"]', 'How do I compare with people my age?');
		await page.waitForFunction(() => document.querySelectorAll('[data-turn="coach"]:not([data-pending])').length > 0, null, {timeout: 60000});
		mark('answered');
		await wait(1500);
		await page.locator('[data-turn="coach"]').last().scrollIntoViewIfNeeded();
		mark('card');
		await wait(4000);
		await shot('peers');
	},
};
