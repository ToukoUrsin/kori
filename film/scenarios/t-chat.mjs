// Take film, the long middle: Home, Ask Kori anything, the grocery question, the coffee switch, eating out,
// Save the difference, a new chat, the laptop, the price picker, the shops, then the typed oat drink question.
// It is played on the clock of the voice take (take seconds, tightened as in src/data/take-plan.json), so each tap
// lands where he says it. LEAD seconds of Home come first.
import {clock, scroll, bring, inBlock} from './_take.mjs';
export const LEAD = 1.0;
const S = '.kc-scroll';
export default {
	lang: 'en',
	path: '/?customer=CUST01885',
	async run({page, tap, wait, mark, shot}) {
		await page.getByText('Ask Kori anything').first().waitFor({timeout: 60000});
		const at0 = clock(wait);
		const at = (take) => at0(LEAD + inBlock(1, take));
		const frame = () => page.frameLocator(`${S} article:last-child iframe`);
		const arrived = async (n, label) => {
			await page.locator(`${S} article[data-state="done"]`).nth(n - 1).waitFor({timeout: 60000});
			await page.locator(`${S} article`).nth(n - 1).locator('iframe').waitFor({timeout: 60000});
			mark('view', {label});
		};
		mark('home');
		await at(21.95);
		await tap(page.getByText('Ask Kori anything').first(), {label: 'ask'});
		await at(25.45);
		await tap(page.locator('button:visible', {hasText: 'Can my grocery shopping be cheaper?'}).last(), {label: 'groceries'});
		await arrived(1, 'groceries');
		await at(30.2);
		mark('scroll', {label: 'rows'});
		await scroll(page, S, {by: 150, dur: 3600});
		await at(40.7);
		await tap(frame().locator('.k-switch').first(), {label: 'coffee off'});
		await at(43.3);
		mark('scroll', {label: 'lever'});
		await scroll(page, S, {to: 99999, dur: 1500});
		await at(46.3);
		await tap(frame().getByText('Eating out is the bigger lever'), {label: 'eating out'});
		await arrived(2, 'eating out');
		await at(50.0);
		mark('scroll', {label: 'what would change it'});
		await bring(page, S, frame().getByRole('slider', {name: 'What would change it'}), 330, 1300);
		await at(55.45);
		await tap(frame().getByText('Save the difference'), {label: 'save the difference'});
		await arrived(3, 'ten years');
		await at(60.9);
		mark('scroll', {label: 'fund'});
		await scroll(page, S, {to: 99999, dur: 1300});
		await at(65.2);
		await tap(page.getByRole('button', {name: 'New conversation'}), {label: 'new chat'});
		await at(66.45);
		await tap(page.locator('button:visible', {hasText: 'I need a new laptop'}).last(), {label: 'laptop'});
		await arrived(1, 'laptop');
		await at(73.0);
		// the price picker: drag the thumb from the €287 stop to the €715 stop (the picker has six stops)
		const slider = frame().getByRole('slider', {name: 'laptop price'});
		const b = await slider.boundingBox();
		const info = await slider.evaluate((e) => ({min: +e.min, max: +e.max, value: +e.value}));
		const xOf = (v) => b.x + 14 + ((v - info.min) / (info.max - info.min)) * (b.width - 28);
		const y = b.y + b.height / 2, x0 = xOf(info.value), x1 = xOf(3);
		mark('tap', {label: 'price picker', box: {x: x0 - 14, y: y - 14, width: 28, height: 28}});
		await page.mouse.move(x0, y);
		await page.mouse.down();
		for (let i = 1; i <= 26; i++) {
			const p = i / 26;
			await page.mouse.move(x0 + (x1 - x0) * (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2), y);
			await wait(34);
		}
		await wait(120);
		await page.mouse.up();
		mark('picker', {label: `stop ${await slider.evaluate((e) => e.value)}: ${await frame().locator('body').evaluate((e) => e.innerText.replace(/\s+/g, ' ').slice(70, 150))}`});
		await at(77.2);
		mark('scroll', {label: 'shops'});
		await scroll(page, S, {to: 99999, dur: 1100});
		await at(81.55);
		const input = page.locator('.kc-composer textarea');
		await tap(input, {label: 'field'});
		mark('type', {text: 'Is there a cheaper oat drink than the one I buy?'});
		await input.pressSequentially('Is there a cheaper oat drink than the one I buy?', {delay: 34});
		await wait(250);
		mark('send');
		await input.press('Enter');
		// built fresh: the words first, then the screen
		const turn = page.locator(`${S} article`).nth(1);
		await turn.locator('.kc-answer').waitFor({timeout: 90000});
		mark('words');
		await turn.locator('iframe').waitFor({timeout: 120000});
		mark('view', {label: 'oat drink'});
		await page.locator(`${S} article[data-state="done"]`).nth(1).waitFor({timeout: 120000}).catch(() => {});
		mark('done');
		await wait(6000);
		await shot('oat');
		mark('scroll', {label: 'oat down'});
		await scroll(page, S, {by: 260, dur: 2200});
		await wait(3000);
		await shot('oat2');
		await scroll(page, S, {by: 400, dur: 2200});
		await wait(2000);
		await shot('oat3');
	},
};
