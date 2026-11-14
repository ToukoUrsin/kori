// Part B, teach: the first lesson with its sorting step (six real payments, one sorted wrong on purpose) and the
// honest say-it-back: a wrong answer first ("Not yet"), then a good one, then "Finish lesson".
// The right basket of each payment is read from the app's own lesson data (GET /api/lessons/<id>).
const LABEL = {fixed: 'Fixed musts', surprise: 'Surprise musts', everyday: 'Everyday'};
export default {
	lang: 'en',
	path: '/#learn',
	async run({page, tap, wait, mark, shot}) {
		const items = [];
		page.on('response', async (r) => {
			if (!/\/api\/lessons\/[^/?]+/.test(r.url()) || !r.ok()) return;
			try {
				const j = await r.json();
				for (const s of j.slides ?? []) for (const it of s.items ?? []) items.push(it);
			} catch {
				/* not the lesson */
			}
		});
		await wait(1500);
		await tap(page.getByRole('button', {name: 'Start lesson'}).first(), {label: 'start lesson'});
		await wait(2600);
		// slides until the sorting step
		for (let i = 0; i < 8 && !(await page.getByText(/Payment \d of \d/).isVisible().catch(() => false)); i++) {
			const next = page.getByRole('button', {name: 'Next', exact: true});
			if (!(await next.isVisible().catch(() => false))) break;
			await tap(next, {label: 'next slide'});
			await wait(2200);
		}
		mark('sorting');
		const wrongAt = 2; // the third payment goes in the wrong basket, on purpose
		for (let n = 0; n < 6; n++) {
			const counter = await page.getByText(/Payment \d of \d/).first().textContent().catch(() => '');
			const k = Number(/Payment (\d)/.exec(counter ?? '')?.[1] ?? n + 1) - 1;
			const right = items[k]?.basket;
			if (!right) throw new Error(`no basket for payment ${k + 1}: the lesson API was not seen`);
			const pick = n === wrongAt ? (right === 'everyday' ? 'surprise' : 'everyday') : right;
			await wait(1100);
			await tap(page.getByRole('button', {name: LABEL[pick], exact: true}), {label: n === wrongAt ? 'sort (wrong on purpose)' : 'sort'});
			await wait(n === wrongAt ? 2600 : 1400); // the feedback, then the 750 ms auto-advance
		}
		mark('sorted');
		await wait(2500);
		await shot('sorted');
		// on to say-it-back
		for (let i = 0; i < 6 && !(await page.getByLabel('Say it back').isVisible().catch(() => false)); i++) {
			const go = page.getByRole('button', {name: /^(Next|Continue)$/});
			if (!(await go.first().isVisible().catch(() => false))) break;
			await tap(go.first(), {label: 'next'});
			await wait(1800);
		}
		const box = page.getByLabel('Say it back');
		mark('say it back');
		await box.click();
		await box.pressSequentially('The balance is what I can spend, so I just look at the account number', {delay: 28});
		await wait(500);
		await tap(page.getByRole('button', {name: 'Check my answer'}), {label: 'check (wrong)'});
		await page.getByText('Not yet').waitFor({timeout: 40000});
		mark('not yet');
		await wait(3500);
		await shot('not-yet');
		await tap(page.getByRole('button', {name: 'Try once more'}), {label: 'try again'});
		await wait(800);
		await box.fill('');
		await box.pressSequentially('Rent and bills are fixed musts, things that break are surprise musts, and everyday is the one I steer day to day.', {delay: 28});
		await wait(500);
		await tap(page.getByRole('button', {name: 'Check my answer'}), {label: 'check'});
		await page.getByRole('button', {name: 'Finish lesson'}).waitFor({timeout: 40000});
		mark('graded');
		await wait(3500);
		await shot('graded');
		await tap(page.getByRole('button', {name: 'Finish lesson'}), {label: 'finish'});
		await wait(2000);
	},
};
