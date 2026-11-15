// Dev probe: run a small script against the live app and dump screenshots + button names. node capture/probe.mjs <script.mjs> <outdir> [width height]
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from 'playwright';
const [script, out, w = '390', h = '844'] = process.argv.slice(2);
fs.mkdirSync(out, {recursive: true});
const browser = await chromium.launch({headless: true, args: ['--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream']});
const VW = Number(w), VH = Number(h);
const ctx = await browser.newContext({viewport: {width: VW, height: VH}, deviceScaleFactor: 2, isMobile: VW < 600, hasTouch: VW < 600, locale: 'en-GB', permissions: ['microphone']});
const page = await ctx.newPage();
let n = 0; const only = false;
const api = {
	page, wait: (ms) => page.waitForTimeout(ms),
	shot: async (name) => { await page.screenshot({path: path.join(out, `${String(n++).padStart(2, '0')}-${name}.png`)}); },
	dump: async (name) => {
		const d = await page.evaluate(() => {
			const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
			const els = [...document.querySelectorAll('button, a, [role=button], [role=switch], input, textarea, select, [role=slider], iframe')].filter(vis);
			return els.map((e) => { const r = e.getBoundingClientRect(); return `${e.tagName.toLowerCase()}${e.getAttribute('role') ? '[' + e.getAttribute('role') + ']' : ''} @${Math.round(r.x)},${Math.round(r.y)} ${Math.round(r.width)}x${Math.round(r.height)} aria="${e.getAttribute('aria-label') || ''}" cls="${String(e.className).slice(0, 50)}" txt="${(e.innerText || e.value || e.placeholder || '').replace(/\s+/g, ' ').slice(0, 90)}"`; });
		});
		for (const fr of page.frames().slice(1)) {
			const fd = await fr.evaluate(() => {
				const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
				const els = [...document.querySelectorAll('button, a, [role=button], [role=switch], input, textarea, select, [role=slider], h1, h2, h3, [data-action], label')].filter(vis);
				return ['FRAME h=' + document.documentElement.scrollHeight, ...els.map((e) => { const r = e.getBoundingClientRect(); return `  ${e.tagName.toLowerCase()}${e.getAttribute('role') ? '[' + e.getAttribute('role') + ']' : ''}${e.type ? ':' + e.type : ''} @${Math.round(r.x)},${Math.round(r.y)} ${Math.round(r.width)}x${Math.round(r.height)} aria="${e.getAttribute('aria-label') || ''}" cls="${String(e.className).slice(0, 40)}" txt="${(e.innerText || e.value || '').replace(/\s+/g, ' ').slice(0, 80)}"`; })];
			}).catch((e) => ['FRAME err ' + e.message]);
			d.push(...fd);
		}
		fs.writeFileSync(path.join(out, `${name}.txt`), d.join('\n'));
		console.log(`--- ${name}\n` + d.filter((l) => only ? l.startsWith('FRAME') || l.startsWith('  ') || /kc-|iframe/.test(l) : true).join('\n'));
	},
};
try { await (await import(path.resolve(script))).default(api); } catch (e) { console.error('FAILED', e.message); await api.shot('failed').catch(() => {}); }
await browser.close();
