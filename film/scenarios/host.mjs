// Part B, inside the bank app (/host): the host's home, Kori asks before it reads anything (consent sheet held 3 s),
// Allow, Kori opens inside the host, back to the host home where its own "Safe to spend" tile shows the number Kori
// sent back over the bridge, then one beat of Finnish. If consent was already given, it is withdrawn first.
export default {
	lang: 'en',
	path: '/host',
	async run({page, tap, wait, mark, shot}) {
		const nav = page.getByRole('navigation');
		const tile = page.locator('.host-safe-tile');
		await wait(2000);
		// a clean start: no consent yet
		if (!(await tile.textContent().catch(() => '')).includes('Waiting for Kori')) {
			await tap(page.getByRole('button', {name: /Data and permissions/}), {label: 'permissions'});
			await wait(600);
			const withdraw = page.getByRole('button', {name: 'Withdraw Kori access'});
			if (await withdraw.isEnabled().catch(() => false)) await tap(withdraw, {label: 'withdraw'});
			await wait(600);
			const close = page.getByRole('button', {name: 'Close', exact: true});
			if (await close.first().isVisible().catch(() => false)) await tap(close.first(), {label: 'close'});
			await wait(1200);
		}
		mark('host home');
		await wait(2000);
		await tap(nav.getByRole('button', {name: 'Coach'}), {label: 'open Kori'});
		await page.getByText('Let Kori read this account?').waitFor({timeout: 10000});
		mark('consent');
		await wait(3000);
		await shot('consent');
		await tap(page.getByRole('button', {name: 'Allow', exact: true}), {label: 'allow'});
		await page.frameLocator('iframe[title="Kori coach"]').locator('body').waitFor({timeout: 20000});
		mark('kori inside');
		await wait(3500);
		await tap(nav.getByRole('button', {name: 'Home'}), {label: 'host home'});
		await page.waitForFunction(() => !document.querySelector('.host-safe-tile')?.textContent?.includes('Waiting for Kori'), null, {timeout: 20000});
		await tile.scrollIntoViewIfNeeded();
		mark('tile');
		await wait(3000);
		await shot('tile');
		await page.getByRole('combobox', {name: 'Language'}).selectOption('fi');
		mark('suomeksi');
		await wait(4000);
		await shot('fi');
	},
};
