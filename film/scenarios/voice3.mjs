// Part B, cold open and habit loop: three spoken turns with Aino, then the home screen with the one thing tracked.
//   1 "Can I afford a six hundred and fifty euro phone this month?"  → the afford card (per day 46 → 18)
//   2 "How did my last pay cycle go?"                                 → the look-back card and its question
//   3 "It was unusual"                                                → the one thing is set (groceries under 520)
// Then the coach closes and the home screen holds 3 s on [data-loop="active"].
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
		await heard({quiet: 1200}); // the greeting
		await wait(500);
		for (const [i, q] of ['Can I afford a six hundred and fifty euro phone this month?', 'How did my last pay cycle go?', 'It was unusual'].entries()) {
			mark(`q${i + 1}`);
			await say(q);
			await answered({quiet: 1500});
			await wait(800);
		}
		await tap(page.getByRole('button', {name: 'End', exact: true}), {label: 'end voice'});
		await wait(900);
		await tap(page.getByRole('dialog').getByRole('button', {name: 'Close'}).first(), {label: 'close coach'});
		const loop = page.locator('[data-loop="active"]');
		await loop.waitFor({timeout: 15000});
		await loop.scrollIntoViewIfNeeded();
		mark('loop active');
		await wait(3000);
	},
};
