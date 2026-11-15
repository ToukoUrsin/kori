// Take film, the proof: Home, the "Tested on 18 past paydays" card, the sheet with the month strip, then down to
// the number against the balance and the check across every customer. The film places the tap on his line.
import {scroll} from './_take.mjs';
export default {
	lang: 'en',
	path: '/?customer=CUST01885',
	async run({page, tap, wait, mark, shot}) {
		await page.getByText('Ask Kori anything').first().waitFor({timeout: 60000});
		await wait(800);
		mark('home');
		await wait(1800);
		await tap(page.locator('button', {hasText: 'Tested on 18 past paydays'}).first(), {label: 'tested'});
		await page.getByText('Payday replay').first().waitFor({timeout: 20000});
		mark('sheet');
		// the month strip stays while he says "the number she started with"; then down to the check against the balance
		await wait(1900);
		mark('scroll', {label: 'versus balance'});
		const sel = await page.evaluate(() => {
			const el = [...document.querySelectorAll('div')].filter((e) => e.scrollHeight > e.clientHeight + 40 && /(auto|scroll)/.test(getComputedStyle(e).overflowY) && e.innerText.includes('Payday replay') === false && e.innerText.includes('would have held')).at(-1);
			el.setAttribute('data-film-scroll', '1');
			return '[data-film-scroll]';
		});
		await scroll(page, sel, {to: 99999, dur: 1300});
		await wait(6500);
		await shot('sheet');
	},
};
