// The live voice conversation: three spoken questions, real answers, cards arriving while the coach speaks.
export default {
	lang: 'en',
	path: '/',
	async run({page, tap, say, heard, answered, wait, mark}) {
		await wait(1500);
		await tap(page.getByRole('button', {name: 'Talk to the coach'}), {label: 'open coach'});
		await wait(900);
		await tap(page.getByRole('dialog').getByRole('button', {name: 'Talk to Kori'}), {label: 'start voice'});
		await page.getByText('Listening').or(page.getByText('Kori is speaking')).first().waitFor({timeout: 20000});
		mark('voice live');
		await heard({quiet: 1200});                       // the greeting
		for (const q of ['What is safe for me to spend this week?',
			'How much did I spend on taxis last month?',
			'How much could I save if I reduced dining out by twenty percent?']) {
			await say(q);
			await answered({quiet: 1500});
			await wait(600);
		}
		await tap(page.getByRole('button', {name: 'End', exact: true}), {label: 'end voice'});
		await wait(1200);
	},
};
