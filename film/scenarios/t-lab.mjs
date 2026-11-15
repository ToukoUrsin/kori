// Take film, the work view (a laptop page; record with --width 1040 --height 624 --scale 3): the grocery question
// with fresh=1, so Kori writes the code live; then the finished view and the line under it.
import {scroll} from './_take.mjs';
export default {
	lang: 'en',
	path: '/lab?customer=CUST01885&dev=1&fresh=1',
	async run({page, tap, wait, mark, shot}) {
		await page.locator('.lab-starter').first().waitFor({timeout: 60000});
		await wait(1500);
		mark('page');
		await tap(page.locator('.lab-starter', {hasText: 'Can my grocery shopping be cheaper?'}), {label: 'groceries'});
		await page.locator('.lab-run-row').first().waitFor({timeout: 60000});
		mark('code');
		await page.locator('.lab-answer').first().waitFor({timeout: 90000});
		mark('words');
		await page.locator('.lab-scroll iframe').first().waitFor({timeout: 120000});
		mark('view');
		await page.getByText(/figures, all from one run of code/).first().waitFor({timeout: 120000});
		mark('done');
		await wait(2500);
		await shot('done');
		mark('scroll', {label: 'check line'});
		await scroll(page, '.lab-scroll', {to: 99999, dur: 1600});
		await wait(8000);
		await shot('bottom');
	},
};
