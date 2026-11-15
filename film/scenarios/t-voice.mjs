// Take film, shot 2: Home, then the round button. Kori speaks first, in its own voice.
// The customer is reset first (or Kori opens with a different line); the film starts after that.
import {buttons} from './_take.mjs';
export default {
	lang: 'en',
	path: '/?customer=CUST01885',
	async run({page, tap, heard, wait, mark, shot}) {
		await page.getByText('Ask Kori anything').first().waitFor({timeout: 60000});
		await wait(600);
		await tap(page.getByRole('button', {name: 'Switch demo customer'}), {label: 'customers'});
		await wait(700);
		await tap(page.getByRole('button', {name: /Clear this customer/}), {label: 'reset'});
		await wait(1500);
		const close = page.getByRole('button', {name: 'Close', exact: true}).first();
		if (await close.isVisible().catch(() => false)) await tap(close, {label: 'close'});
		await page.getByText('Ask Kori anything').first().waitFor({timeout: 60000});
		await wait(1500);
		mark('home');
		await wait(3500);
		// on this build the round button opens the chat; the voice starts from the microphone in Home's ask field
		await tap(page.getByRole('button', {name: 'Talk to Kori'}).first(), {label: 'talk'});
		await wait(1500);
		await shot('after-tap');
		console.log(await buttons(page));
		const ok = await heard({quiet: 1800, timeout: 45000});
		await shot('spoken');
		console.log(await buttons(page));
		await wait(1500);
		if (!ok) throw new Error('Kori did not speak');
	},
};
