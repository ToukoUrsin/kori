// One spoken question in Finnish, from another customer (Eetu): the same coach, the other language.
export default {
	lang: 'fi',
	path: '/?customer=CUST00248&lang=fi',
	async run({page, tap, say, heard, answered, wait, mark}) {
		await wait(1500);
		await tap(page.getByRole('button', {name: 'Puhu valmentajalle'}), {label: 'open coach'});
		await wait(900);
		await tap(page.getByRole('dialog').getByRole('button', {name: 'Puhu Korille'}), {label: 'start voice'});
		await page.getByText('Kuuntelen').or(page.getByText('Kori puhuu')).first().waitFor({timeout: 20000});
		mark('voice live');
		await heard({quiet: 1200});
		await wait(500);
		await say('Riittävätkö rahani palkkapäivään asti?');
		await answered({quiet: 1500});
		await wait(700);
		await tap(page.getByRole('button', {name: 'Lopeta', exact: true}), {label: 'end voice'});
		await wait(800);
	},
};
