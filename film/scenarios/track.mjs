// "Was this number right before?": the coach replays the customer's own past months.
export default {
	lang: 'en',
	path: '/',
	async run({page, tap, type, wait, mark, shot}) {
		await wait(1200);
		await tap(page.getByRole('button', {name: 'Talk to the coach'}), {label: 'open coach'});
		await wait(800);
		await type('textarea, input[type="text"]', 'Was this number right before?');
		await page.waitForFunction(() => document.querySelectorAll('[data-turn="coach"]:not([data-pending])').length > 0, null, {timeout: 60000});
		mark('answered');
		await wait(2500);
		await shot('track');
		await page.mouse.move(195, 600);
		for (let i = 0; i < 6; i++) {
			await page.mouse.wheel(0, 90);
			await wait(350);
		}
		await wait(1500);
	},
};
