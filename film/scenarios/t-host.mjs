// Take film, inside the bank app (/host): consent is given first (tap the Safe to spend tile, Allow), then the film
// part: the bank's own home with Kori's number on its tile, a tap on the tile, Kori open inside the bank's frame.
export default {
	lang: 'en',
	path: '/host',
	async run({page, tap, wait, mark, shot}) {
		const nav = page.getByRole('navigation');
		const tile = page.locator('.host-safe-tile');
		await tile.waitFor({timeout: 60000});
		await wait(1500);
		if ((await tile.textContent()).includes('After you allow Kori')) {
			await tap(tile, {label: 'tile'});
			await page.getByText('Let Kori read this account?').waitFor({timeout: 15000});
			mark('consent');
			await wait(1200);
			await shot('consent');
			await tap(page.getByRole('button', {name: 'Allow', exact: true}), {label: 'allow'});
			await page.frameLocator('iframe[title="Kori coach"]').locator('body').waitFor({timeout: 20000});
			mark('kori inside');
			await wait(3000);
			await shot('inside');
			await tap(nav.getByRole('button', {name: 'Home'}), {label: 'host home'});
		}
		await page.waitForFunction(() => /€\s?1,35\d/.test(document.querySelector('.host-safe-tile')?.textContent || ''), null, {timeout: 20000});
		await wait(600);
		mark('tile');
		await shot('tile');
		await wait(2600);
		await tap(tile, {label: 'open Kori'});
		await page.frameLocator('iframe[title="Kori coach"]').locator('body').waitFor({timeout: 20000});
		mark('kori inside 2');
		await wait(4000);
		await shot('inside2');
	},
};
