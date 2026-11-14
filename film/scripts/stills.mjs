// Bundles the film once and renders the given frames as PNGs: node scripts/stills.mjs <outDir> <frame> [frame ...]
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';

// the bundler and the renderer come with @remotion/cli (they are not listed as the film's own dependencies)
const req = createRequire(fs.realpathSync('node_modules/@remotion/cli/package.json'));
const {bundle} = req('@remotion/bundler');
const {renderStill, selectComposition, openBrowser} = req('@remotion/renderer');

const [out, ...frames] = process.argv.slice(2);
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const browser = await openBrowser('chrome');
const composition = await selectComposition({serveUrl, id: 'Film', puppeteerInstance: browser});
let i = 0;
const next = async () => {
	while (i < frames.length) {
		const k = i++;
		const f = Number(frames[k]);
		await renderStill({serveUrl, composition, frame: Math.min(f, composition.durationInFrames - 1), output: path.join(out, `${String(k).padStart(2, '0')}-${f}.png`), puppeteerInstance: browser});
	}
};
await Promise.all([next(), next(), next(), next()]);
await browser.close({silent: true});
