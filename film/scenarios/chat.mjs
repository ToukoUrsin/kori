// Typed chat: the four questions from the challenge, each with its card.
export default {
	lang: 'en',
	path: '/',
	async run({page, tap, type, wait, mark, shot}) {
		await wait(1200);
		await shot('today');
		await tap(page.getByRole('button', {name: 'Talk to the coach'}), {label: 'open coach'});
		await wait(700);
		const input = 'textarea, input[type="text"]';
		const qs = ['How much did I spend on taxis last month?', 'What kind of spender am I?',
			'What is safe for me to spend this week?', 'How much could I save if I reduced dining out by 20%?'];
		for (const [i, q] of qs.entries()) {
			await type(input, q);
			await page.waitForFunction((n) => document.querySelectorAll('[data-turn="coach"]:not([data-pending])').length > n, i, {timeout: 60000});
			mark('answered');
			await wait(2200);
			await shot(`chat-${i + 1}`);
		}
	},
};
