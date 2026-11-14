#!/usr/bin/env node
// Records a real session with the live app for the film: crisp screen frames, the coach's real voice
// and the exact moment of every tap and spoken question.
//
//   node capture/record.mjs <scenario> [--base https://kori-coach.fly.dev] [--out /bulk2/runs/spankki/film/<scenario>]
//
// How it works
//   screen   Chrome's own screencast (CDP) at 3x device pixels, one JPEG per painted frame with its timestamp,
//            turned into a 30 fps mp4 by ffmpeg.
//   mic      getUserMedia is replaced by a Web Audio stream we can play a question into on cue. The question is
//            real speech (ElevenLabs, a different voice from the coach) and the agent really hears it.
//   voice    the agent's WebRTC audio track is recorded in the page with MediaRecorder. Other sounds the app plays
//            (money minute, spoken replies) are logged with their start time and URL and fetched afterwards.
//   clock    everything is stamped in epoch milliseconds, so screen and sound line up without guessing.
//
// Output: video.mp4 (silent), voice-N.webm, user-N.mp3, sound-N.mp3, timeline.json and preview.mp4 (all mixed).
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flag = (name, dflt) => {
	const i = args.indexOf(`--${name}`);
	return i >= 0 ? args[i + 1] : dflt;
};
const scenarioName = args[0];
if (!scenarioName) {
	console.error('usage: record.mjs <scenario> [--base URL] [--out DIR]');
	process.exit(1);
}
const BASE = flag('base', 'https://kori-coach.fly.dev');
const OUT = flag('out', `/bulk2/runs/spankki/film/${scenarioName}`);
const VW = Number(flag('width', 390)), VH = Number(flag('height', 844)), SCALE = Number(flag('scale', 3));
const USER_VOICE = {en: 'cjVigY5qzO86Huf0OWal', fi: 'ESapivUCtGNuYKDCwzcI'};   // not the coach's voice
const CACHE = path.join(here, '..', 'public', 'audio', 'user');
fs.mkdirSync(path.join(OUT, 'frames'), {recursive: true});
fs.mkdirSync(CACHE, {recursive: true});

// ---------------------------------------------------------------- the user's voice (cached: never paid for twice)
async function userSpeech(text, lang) {
	const key = crypto.createHash('sha1').update(`${lang}:${text}`).digest('hex').slice(0, 16);
	const file = path.join(CACHE, `${key}.mp3`);
	if (!fs.existsSync(file)) {
		const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${USER_VOICE[lang]}?output_format=mp3_44100_128`, {
			method: 'POST',
			headers: {'xi-api-key': process.env.ELEVENLABS_API_KEY, 'content-type': 'application/json'},
			body: JSON.stringify({text, model_id: 'eleven_multilingual_v2'}),
		});
		if (!r.ok) throw new Error(`tts ${r.status} ${(await r.text()).slice(0, 200)}`);
		fs.writeFileSync(file, Buffer.from(await r.arrayBuffer()));
	}
	return file;
}

// ---------------------------------------------------------------- runs inside the page, before the app
const inPage = () => {
	const epoch = () => performance.timeOrigin + performance.now();
	const K = (window.__kori = {voices: [], sounds: [], screen: [], level: 0, lastLoud: 0, everLoud: false});
	// what the server tells the voice screen (the user's words, cards, the coach's words) and when
	const ES = window.EventSource;
	const Hook = function (url, opts) {
		const es = new ES(url, opts);
		for (const name of ['user', 'status', 'card', 'coach', 'effect', 'done']) {
			es.addEventListener(name, (e) => K.screen.push({at: epoch(), name, data: String(e.data || '').slice(0, 600)}));
		}
		return es;
	};
	Hook.prototype = ES.prototype;
	Object.setPrototypeOf(Hook, ES);
	window.EventSource = Hook;
	let ctx, dest;
	const ensure = () => {
		if (!ctx) {
			ctx = new AudioContext({sampleRate: 48000});
			dest = ctx.createMediaStreamDestination();
			const g = ctx.createGain();
			g.gain.value = 0;
			const o = ctx.createOscillator();     // a silent source keeps the "microphone" alive
			o.connect(g).connect(dest);
			o.start();
		}
		return ctx;
	};
	// the microphone
	const md = navigator.mediaDevices;
	const realEnumerate = md.enumerateDevices.bind(md);
	md.getUserMedia = async (c) => {
		if (!c || !c.audio) throw new DOMException('no camera here', 'NotFoundError');
		ensure();
		await ctx.resume();
		return new MediaStream(dest.stream.getAudioTracks().map((t) => t.clone()));
	};
	md.enumerateDevices = async () => {
		const d = await realEnumerate().catch(() => []);
		return d.length ? d : [{deviceId: 'default', kind: 'audioinput', label: 'Microphone', groupId: 'g', toJSON() { return this; }}];
	};
	K.say = async (b64) => {
		ensure();
		await ctx.resume();
		const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
		const buf = await ctx.decodeAudioData(bytes.buffer);
		const src = ctx.createBufferSource();
		src.buffer = buf;
		src.connect(dest);
		const at = epoch();
		src.start();
		return {at, seconds: buf.duration};
	};
	// the coach's voice: record every remote audio track
	const watch = (stream) => {
		try {
			const a = new Audio();          // Chrome only feeds a remote track into Web Audio once an element plays it
			a.srcObject = stream;
			a.muted = true;
			a.play().catch(() => {});
			const actx = new AudioContext();
			const an = actx.createAnalyser();
			an.fftSize = 1024;
			actx.createMediaStreamSource(stream).connect(an);
			const data = new Float32Array(an.fftSize);
			setInterval(() => {
				an.getFloatTimeDomainData(data);
				let s = 0;
				for (const v of data) s += v * v;
				K.level = Math.sqrt(s / data.length);
				if (K.level > 0.01) {
					K.lastLoud = epoch();
					K.everLoud = true;
				}
			}, 50);
		} catch (e) {
			console.warn('level meter failed', e);
		}
	};
	const Orig = window.RTCPeerConnection;
	const Hooked = function (...a) {
		const pc = new Orig(...a);
		pc.addEventListener('track', (e) => {
			if (e.track.kind !== 'audio') return;
			const stream = new MediaStream([e.track]);
			const item = {at: epoch(), chunks: []};
			const mr = new MediaRecorder(stream, {mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 128000});
			mr.ondataavailable = (ev) => ev.data.size && item.chunks.push(ev.data);
			mr.onstart = () => (item.at = epoch());
			mr.start(200);
			item.mr = mr;
			K.voices.push(item);
			watch(stream);
		});
		return pc;
	};
	Hooked.prototype = Orig.prototype;
	Object.setPrototypeOf(Hooked, Orig);
	window.RTCPeerConnection = Hooked;
	// every other sound the app plays
	const play = HTMLMediaElement.prototype.play;
	HTMLMediaElement.prototype.play = function (...a) {
		if (!this.muted && (this.currentSrc || this.src)) K.sounds.push({at: epoch(), src: this.currentSrc || this.src, from: this.currentTime || 0});
		this.addEventListener('pause', () => K.sounds.push({at: epoch(), src: this.currentSrc || this.src, stop: true}), {once: true});
		return play.apply(this, a);
	};
	K.finish = async () => {
		const out = [];
		for (const v of K.voices) {
			if (v.mr.state !== 'inactive') {
				await new Promise((res) => {
					v.mr.onstop = res;
					v.mr.stop();
				});
			}
			const blob = new Blob(v.chunks, {type: 'audio/webm'});
			const b64 = await new Promise((res) => {
				const fr = new FileReader();
				fr.onload = () => res(String(fr.result).split(',')[1] || '');
				fr.readAsDataURL(blob);
			});
			out.push({at: v.at, b64});
		}
		return out;
	};
};

// ---------------------------------------------------------------- record
const {default: scenario} = await import(path.resolve(here, '..', 'scenarios', `${scenarioName}.mjs`));
const lang = scenario.lang || 'en';
const browser = await chromium.launch({
	headless: true,
	args: ['--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
});
const ctx = await browser.newContext({
	viewport: {width: VW, height: VH}, deviceScaleFactor: SCALE, isMobile: VW < 600, hasTouch: VW < 600,
	locale: lang === 'fi' ? 'fi-FI' : 'en-GB', permissions: ['microphone'],
});
await ctx.addInitScript(inPage);
const page = await ctx.newPage();
page.on('console', (m) => m.type() === 'error' && console.log('  [page error]', m.text().slice(0, 200)));
const cdp = await ctx.newCDPSession(page);
const frames = [];
cdp.on('Page.screencastFrame', async (f) => {
	const file = `frames/${String(frames.length).padStart(6, '0')}.jpg`;
	fs.writeFileSync(path.join(OUT, file), Buffer.from(f.data, 'base64'));
	frames.push({file, at: f.metadata.timestamp * 1000});
	await cdp.send('Page.screencastFrameAck', {sessionId: f.sessionId}).catch(() => {});
});

const events = [];
const now = () => Date.now();
const mark = (kind, extra = {}) => {
	events.push({at: now(), kind, ...extra});
	console.log(`  ${((now() - t0) / 1000).toFixed(1).padStart(6)}s ${kind} ${extra.text || extra.selector || extra.label || ''}`);
};
let t0 = now();
const userClips = [];
let asked = 0;          // how many screen events there were when the last question was spoken
const api = {
	page, lang, base: BASE,
	wait: (ms) => page.waitForTimeout(ms),
	mark,
	async tap(selector, opts = {}) {
		const el = typeof selector === 'string' ? page.locator(selector).first() : selector;
		await el.scrollIntoViewIfNeeded().catch(() => {});
		const box = await el.boundingBox();
		mark('tap', {selector: String(selector).slice(0, 80), box, label: opts.label});
		await el.click({timeout: 15000});
	},
	async type(selector, text, {submit = true, delay = 45} = {}) {
		const el = page.locator(selector).first();
		await el.click();
		mark('type', {text});
		await el.pressSequentially(text, {delay});
		if (submit) await el.press('Enter');
	},
	/** Speak a question into the microphone. Resolves when the user has finished talking. */
	async say(text) {
		const file = await userSpeech(text, lang);
		asked = await page.evaluate(() => window.__kori.screen.length);
		const r = await page.evaluate((b64) => window.__kori.say(b64), fs.readFileSync(file).toString('base64'));
		userClips.push({at: r.at, seconds: r.seconds, text, file});
		mark('say', {text, seconds: r.seconds});
		await page.waitForTimeout(r.seconds * 1000);
		mark('said');
	},
	/** Wait until the coach has spoken and then been quiet for `quiet` ms. */
	async heard({quiet = 1400, timeout = 45000, after = now()} = {}) {
		const start = now();
		while (now() - start < timeout) {
			const k = await page.evaluate(() => ({last: window.__kori.lastLoud, level: window.__kori.level}));
			if (k.last > after && now() - k.last > quiet) {
				mark('coach finished');
				return true;
			}
			await page.waitForTimeout(100);
		}
		mark('coach timeout');
		return false;
	},
	/** Wait until the coach has answered the last spoken question: its words reached the screen, it said them,
	 *  and it has been quiet for `quiet` ms. (The "let me look" it says first is not the answer.) */
	async answered({quiet = 1400, timeout = 60000} = {}) {
		const start = now();
		while (now() - start < timeout) {
			const k = await page.evaluate((from) => {
				const K = window.__kori;
				const done = K.screen.slice(from).find((e) => e.name === 'done');
				return {done: done ? done.at : 0, last: K.lastLoud};
			}, asked);
			if (k.done && k.last > k.done && now() - k.last > quiet) {
				mark('coach answered');
				return true;
			}
			await page.waitForTimeout(100);
		}
		mark('coach timeout');
		throw new Error('the coach did not answer in time');
	},
	async shot(name) {
		await page.screenshot({path: path.join(OUT, `${name}.png`)});
	},
};

await page.goto(BASE + (scenario.path || '/'), {waitUntil: 'networkidle', timeout: 60000});
await page.waitForTimeout(600);
await cdp.send('Page.startScreencast', {format: 'jpeg', quality: 92, maxWidth: VW * SCALE, maxHeight: VH * SCALE, everyNthFrame: 1});
t0 = now();
mark('start');
let failed = null;
try {
	await scenario.run(api);
} catch (e) {
	failed = e;
	console.error('scenario failed:', e.message);
	await page.screenshot({path: path.join(OUT, 'failed.png')}).catch(() => {});
}
mark('end');
const tEnd = now();
await cdp.send('Page.stopScreencast').catch(() => {});
const voices = await page.evaluate(() => window.__kori.finish()).catch(() => []);
const sounds = await page.evaluate(() => window.__kori.sounds).catch(() => []);
const screen = await page.evaluate(() => window.__kori.screen).catch(() => []);
await browser.close();

// ---------------------------------------------------------------- write files
const rel = (ms) => Math.round(ms - t0) / 1000;
const kept = frames.filter((f) => f.at >= t0 - 50);
if (!kept.length) throw new Error('no frames recorded');
// constant 30 fps from painted frames: each frame is held until the next one
const list = [];
kept.forEach((f, i) => {
	const next = i + 1 < kept.length ? kept[i + 1].at : tEnd;
	list.push(`file '${path.join(OUT, f.file)}'`, `duration ${Math.max(0.001, (next - f.at) / 1000).toFixed(4)}`);
});
list.push(`file '${path.join(OUT, kept[kept.length - 1].file)}'`);
fs.writeFileSync(path.join(OUT, 'frames.txt'), list.join('\n'));
const lead = Math.max(0, (kept[0].at - t0) / 1000);
const ff = (a) => execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...a], {stdio: ['ignore', 'inherit', 'inherit']});
ff(['-f', 'concat', '-safe', '0', '-i', path.join(OUT, 'frames.txt'), '-vf', `fps=30,tpad=start_duration=${lead.toFixed(3)}:start_mode=clone,scale=trunc(iw/2)*2:trunc(ih/2)*2`,
	'-c:v', 'libx264', '-crf', '14', '-preset', 'medium', '-pix_fmt', 'yuv420p', path.join(OUT, 'video.mp4')]);

const audio = [];
voices.forEach((v, i) => {
	if (!v.b64) return;
	const f = `voice-${i}.webm`;
	fs.writeFileSync(path.join(OUT, f), Buffer.from(v.b64, 'base64'));
	audio.push({kind: 'coach', file: f, start: rel(v.at)});
});
userClips.forEach((u, i) => {
	const f = `user-${i}.mp3`;
	fs.copyFileSync(u.file, path.join(OUT, f));
	audio.push({kind: 'user', file: f, start: rel(u.at), seconds: u.seconds, text: u.text});
});
let n = 0;
for (const s of sounds.filter((x) => !x.stop && /^https?:/.test(x.src))) {
	const stop = sounds.find((x) => x.stop && x.src === s.src && x.at > s.at);
	try {
		const r = await fetch(s.src);
		if (!r.ok) continue;
		const f = `sound-${n++}.mp3`;
		fs.writeFileSync(path.join(OUT, f), Buffer.from(await r.arrayBuffer()));
		audio.push({kind: 'app', file: f, start: rel(s.at), from: s.from, stop: stop ? rel(stop.at) : null, src: s.src});
	} catch { /* a blob: URL or a sound that is gone */ }
}
const timeline = {
	scenario: scenarioName, base: BASE, lang, viewport: [VW, VH], scale: SCALE, seconds: rel(tEnd), frames: kept.length,
	events: events.map((e) => ({...e, at: rel(e.at)})), screen: screen.map((e) => ({...e, at: rel(e.at)})), audio,
	failed: failed ? failed.message : null,
};
fs.writeFileSync(path.join(OUT, 'timeline.json'), JSON.stringify(timeline, null, 2));

// one file with everything mixed, to watch and to check sync
if (audio.length) {
	const inputs = ['-i', path.join(OUT, 'video.mp4')];
	const filters = [];
	audio.forEach((a, i) => {
		inputs.push('-i', path.join(OUT, a.file));
		const ms = Math.max(0, Math.round(a.start * 1000));
		const trim = a.kind === 'app' && a.stop ? `,atrim=0:${Math.max(0.1, a.stop - a.start).toFixed(2)}` : '';
		filters.push(`[${i + 1}:a]aresample=48000${trim},adelay=${ms}:all=1[a${i}]`);
	});
	filters.push(`${audio.map((_, i) => `[a${i}]`).join('')}amix=inputs=${audio.length}:normalize=0:duration=longest[mix]`);
	ff([...inputs, '-filter_complex', filters.join(';'), '-map', '0:v', '-map', '[mix]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
		'-t', String(rel(tEnd)), path.join(OUT, 'preview.mp4')]);
}
console.log(`${failed ? 'FAILED' : 'ok'}: ${rel(tEnd)}s, ${kept.length} frames, ${audio.length} audio clips -> ${OUT}`);
process.exit(failed ? 1 : 0);
