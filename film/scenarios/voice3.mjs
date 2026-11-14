// Part B, habit loop and cold open: the coach speaks first, then two spoken turns with Aino, then the home screen
// with the one thing tracked.
//   0 Kori opens by itself: what it noticed about the last pay cycle, and the one question
//   1 "It was unusual."                                               → the one thing is set (groceries under 520)
//   2 "Can I afford a six hundred and fifty euro phone this month?"  → the afford card (per day 46 → 18)
// Then the coach closes and the home screen holds 3 s on [data-loop="active"].
export default {
	lang: 'en',
	path: '/?customer=CUST00092',
	async run({page, tap, say, heard, answered, wait, mark}) {
		await wait(1500);
		await tap(page.getByRole('button', {name: 'Talk to the coach'}), {label: 'open coach'});
		await wait(900);
		await tap(page.getByRole('dialog').getByRole('button', {name: 'Talk to Kori'}), {label: 'start voice'});
		await page.getByText('Listening').or(page.getByText('Kori is speaking')).first().waitFor({timeout: 20000});
		mark('voice live');
		await heard({quiet: 1300}); // the opening: what it noticed, and the question
		await wait(400);
		for (const [i, q] of ['It was unusual.', 'Can I afford a six hundred and fifty euro phone this month?'].entries()) {
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
		await wait(3500);
	},
};
