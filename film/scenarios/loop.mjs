// Part B, habit loop (no voice): the suggestion on the home screen, answered with one tap, then tracked;
// the check-in preview, and dropping it again with Undo. Each step is marked for the film's beats.
export default {
	lang: 'en',
	path: '/?customer=CUST00092',
	async run({page, tap, wait, mark, shot}) {
		await wait(1500);
		const suggested = page.locator('[data-loop="suggested"]');
		await suggested.waitFor({timeout: 15000});
		await suggested.scrollIntoViewIfNeeded();
		mark('suggested');
		await wait(2500);
		await shot('suggested');
		await tap(suggested.locator('[data-loop-answer]').first(), {label: 'answer'});
		const active = page.locator('[data-loop="active"]');
		await active.waitFor({timeout: 15000});
		mark('active');
		await wait(3000);
		await shot('active');
		await tap(page.getByText('How the check-in will look'), {label: 'check-in preview'});
		mark('check-in');
		await wait(3000);
		await tap(active.locator('[data-loop-drop]'), {label: 'drop'});
		mark('dropped');
		await wait(1200);
		await tap(page.getByRole('button', {name: 'Undo'}), {label: 'undo'});
		await active.waitFor({timeout: 15000});
		mark('undone');
		await wait(2500);
	},
};
