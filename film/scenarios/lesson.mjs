// A one-minute lesson from start to finish: slides on the customer's own numbers, a quick question, say it back.
export default {
	lang: 'en',
	path: '/#learn',
	async run({page, tap, wait, mark, shot}) {
		await wait(1500);
		await tap(page.getByRole('button', {name: 'Start lesson'}).first(), {label: 'start lesson'});
		await wait(2600);
		for (let i = 0; i < 6; i++) {
			const next = page.getByRole('button', {name: 'Next', exact: true});
			if (!(await next.isVisible().catch(() => false))) break;
			await tap(next, {label: 'next slide'});
			await wait(2400);
		}
		mark('question');
		await wait(1200);
		await tap(page.getByRole('button', {name: 'Surprise musts'}).or(page.getByRole('radio', {name: 'Surprise musts'})).first(), {label: 'answer'});
		await wait(2600);
		await tap(page.getByRole('button', {name: 'Continue'}), {label: 'continue'});
		await wait(1500);
		mark('say it back');
		const box = page.locator('textarea').first();
		await box.click();
		await box.pressSequentially('Fixed musts are rent and bills, surprise musts are things that break, and everyday is the one I steer day to day.', {delay: 28});
		await wait(600);
		await tap(page.getByRole('button', {name: 'Check my answer'}), {label: 'check'});
		await page.getByRole('button', {name: 'Finish lesson'}).waitFor({timeout: 40000});
		mark('graded');
		await wait(3500);
		await shot('graded');
		await tap(page.getByRole('button', {name: 'Finish lesson'}), {label: 'finish'});
		await wait(2500);
	},
};
