#!/usr/bin/env node
// The narrator (ElevenLabs, with word timings for the captions). Spoken numbers come from the app's own data.
//   ELEVENLABS_API_KEY=... node scripts/make-vo.mjs [--print]
// Writes public/audio/vo-NN.mp3 (cached by text) and src/data/vo.json.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const film = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const A = process.argv.slice(2);
const home = JSON.parse(fs.readFileSync(path.join(film, 'src/data/home.json'), 'utf8'));
const bt = JSON.parse(fs.readFileSync(path.join(film, '../docs/backtest.json'), 'utf8'));

const ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(' ');
const TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];
const words = (n) => {
	n = Math.round(n);
	if (n < 20) return ONES[n];
	if (n < 100) return TENS[Math.floor(n / 10)] + (n % 10 ? '-' + ONES[n % 10] : '');
	if (n < 1000) return ONES[Math.floor(n / 100)] + ' hundred' + (n % 100 ? ' and ' + words(n % 100) : '');
	if (n < 1e6) return words(Math.floor(n / 1000)) + ' thousand' + (n % 1000 ? (n % 1000 < 100 ? ' and ' : ' ') + words(n % 1000) : '');
	return String(n);
};
const S = home.safe;

// [scene, gap in seconds before the line (after the scene start or the previous line), text, part B?]
// Scenes: open, balance, loop, math, proof, teach, host, end (src/Film.tsx). In the scenes with recorded voices
// (open, loop) the narrator starts after the recording; the film places it.
// Lines marked PART_B are written for the second cut and are not generated until `--part-b` is given, once the new
// footage is final. Until then vo.json carries them as `pending` with an estimated length and no audio.
const PART_B = true;
const LINES = [
	['open', 0.35, 'This is Kori, a money coach for young adults, right inside the bank app.', PART_B],
	['balance', 0.3, `Aino has ${words(Math.floor(S.balance))} euros on her account.`],
	['balance', 0.3, `But rent, bills and the usual surprises all come before payday.`],
	['balance', 0.3, `What is really hers to spend is ${words(S.amount)}.`],
	['balance', 0.45, 'Your balance is not your budget.'],
	['loop', 0.35, 'It notices, asks, and sets one thing to try until payday. Then it keeps count.', PART_B],
	['math', 0.3, 'The AI never does the math. Gemini only picks the calculation.'],
	['math', 0.3, 'A plain engine runs it on the real transactions.'],
	['math', 0.3, 'Then every number in the answer is checked. One that does not match never reaches you.'],
	['proof', 0.4, `Is the number any good? We replayed it on ${words(bt.customers)} customers.`],
	['proof', 0.35, `Spend what Kori calls safe, and you stay above zero ${words(Math.round(bt.promise.safe_held_pct))} percent of the time.`],
	['proof', 0.3, `Trust the balance instead: ${words(Math.round(bt.promise.balance_as_budget_held_pct))}.`],
	['teach', 0.3, 'And it teaches. Money goes in three baskets: fixed musts, surprise musts, and everyday.'],
	['teach', 0.3, 'Short lessons use your own numbers. You say it back in your own words, and the coach grades it.'],
	['teach', 0.3, 'It compares her with people like her, from Statistics Finland.', PART_B],
	['host', 0.3, 'Here it sits inside a stand-in bank app, the way it would in S-mobiili.', PART_B],
	['host', 0.3, 'It asks before it reads anything. In Finnish and English.', PART_B],
	['end', 0.3, 'Kori. Your balance is not your budget.'],
];
const partB = A.includes('--part-b');
if (A.includes('--print')) {
	for (const l of LINES) console.log(`${l[0].padEnd(7)} +${l[1]}s ${l[3] ? 'B' : ' '} ${String(l[2].length).padStart(3)}  ${l[2]}`);
	console.log(LINES.reduce((a, l) => a + l[2].length, 0), 'characters,', LINES.filter((l) => l[3]).reduce((a, l) => a + l[2].length, 0), 'of them in part B lines');
	process.exit(0);
}

const KEY = process.env.ELEVENLABS_API_KEY;
const voice = A.includes('--voice') ? A[A.indexOf('--voice') + 1] : 'nPczCjzI2devNBz1zQrb'; // "Brian"
const outDir = path.join(film, 'public/audio/vo');
fs.mkdirSync(outDir, {recursive: true});
const key = (t) => {
	let h = 0;
	for (const ch of voice + t) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
	return h.toString(16).padStart(8, '0');
};
const lines = [];
let scene = null, t = 0;
for (const [sc, gap, text, b] of LINES) {
	const base = `vo-${key(text)}`;
	const mp3 = path.join(outDir, `${base}.mp3`), meta = path.join(outDir, `${base}.json`);
	let m = fs.existsSync(meta) && fs.existsSync(mp3) ? JSON.parse(fs.readFileSync(meta, 'utf8')) : null;
	if (!m && b && !partB) {
		// not generated yet: an estimate from the narrator's pace (about 16.5 characters a second at speed 1.05)
		const ws = text.split(/\s+/), dur = Math.round((text.length / 16.5) * 100) / 100;
		let acc = 0;
		const wt = ws.map((w) => {
			const s0 = (acc / text.length) * dur;
			acc += w.length + 1;
			return {w, s: s0, e: Math.min(dur, (acc / text.length) * dur)};
		});
		if (sc !== scene) (scene = sc), (t = 0);
		t += gap;
		lines.push({scene: sc, at: Math.round(t * 100) / 100, text, file: null, pending: true, dur, words: wt});
		t += dur;
		continue;
	}
	if (!m) {
		if (!KEY) throw new Error('ELEVENLABS_API_KEY missing');
		const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voice}/with-timestamps?output_format=mp3_44100_128`, {
			method: 'POST',
			headers: {'xi-api-key': KEY, 'content-type': 'application/json'},
			body: JSON.stringify({text, model_id: 'eleven_multilingual_v2', voice_settings: {stability: 0.5, similarity_boost: 0.8, style: 0.2, use_speaker_boost: true, speed: 1.05}}),
		});
		if (!r.ok) throw new Error(`TTS ${r.status}: ${(await r.text()).slice(0, 300)}`);
		const j = await r.json();
		fs.writeFileSync(mp3, Buffer.from(j.audio_base64, 'base64'));
		const al = j.alignment;
		const ws = [];
		let cur = null;
		al.characters.forEach((ch, k) => {
			if (/\s/.test(ch)) {
				if (cur) ws.push(cur);
				cur = null;
				return;
			}
			if (!cur) cur = {w: '', s: al.character_start_times_seconds[k], e: 0};
			cur.w += ch;
			cur.e = al.character_end_times_seconds[k];
		});
		if (cur) ws.push(cur);
		m = {text, voice, dur: al.character_end_times_seconds.at(-1), words: ws};
		fs.writeFileSync(meta, JSON.stringify(m));
		console.log(`new (${m.dur.toFixed(2)} s): ${text}`);
	}
	if (sc !== scene) (scene = sc), (t = 0);
	t += gap;
	lines.push({scene: sc, at: Math.round(t * 100) / 100, text, file: `audio/vo/${base}.mp3`, dur: m.dur, words: m.words});
	t += m.dur;
}
fs.writeFileSync(path.join(film, 'src/data/vo.json'), JSON.stringify({voice, lines}, null, 1));
const per = {};
for (const l of lines) per[l.scene] = Math.max(per[l.scene] || 0, l.at + l.dur);
console.log(Object.entries(per).map(([s, d]) => `${s} ${d.toFixed(1)}s`).join(' · '));
