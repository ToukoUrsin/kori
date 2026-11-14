#!/usr/bin/env node
// Brings the recordings into the film: screen video, the real voices, and who said what when.
//   node scripts/import-caps.mjs [scenario ...]        (default: every scenario the film uses)
// Reads /bulk2/runs/spankki/film/<scenario>/, writes public/cap/ (not in git) and src/data/caps.json.
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync, spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const film = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SRC = process.env.KORI_CAPS || '/bulk2/runs/spankki/film';
const USED = ['voice2', 'voice3', 'loop', 'lesson2', 'figures', 'peers', 'host', 'teach'];
const want = process.argv.slice(2).length ? process.argv.slice(2) : USED;
const out = path.join(film, 'public/cap');
fs.mkdirSync(out, {recursive: true});
const dataFile = path.join(film, 'src/data/caps.json');
fs.mkdirSync(path.dirname(dataFile), {recursive: true});
const caps = fs.existsSync(dataFile) ? JSON.parse(fs.readFileSync(dataFile, 'utf8')) : {};
const ff = (a) => execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...a], {stdio: ['ignore', 'inherit', 'inherit']});
// integrated loudness of a clip (LUFS), so the film can sit every real voice level with the narrator
const lufs = (file) => {
	const r = spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-i', file, '-af', 'ebur128', '-f', 'null', '-'], {encoding: 'utf8'});
	const m = [...r.stderr.matchAll(/I:\s+(-?[\d.]+) LUFS/g)].at(-1);
	return m ? Number(m[1]) : undefined;
};
const newer = (a, b) => !fs.existsSync(b) || fs.statSync(a).mtimeMs > fs.statSync(b).mtimeMs;
// the coach's "let me look" lines, as written in the backend, to show them spelled right
const toolsPy = fs.readFileSync(path.join(film, '../backend/kori/ai/tools.py'), 'utf8');
const EARLY = [...toolsPy.slice(toolsPy.indexOf('EARLY = {'), toolsPy.indexOf('EARLY_MIN_WORDS')).matchAll(/"([^"]{20,})"/g)].map((m) => m[1].trim());
const written = (heardText) => {
	const h = new Set(heardText.split(/\s+/).map(norm));
	let best = null, score = 0;
	for (const e of EARLY) {
		const ws = e.split(/\s+/).map(norm);
		const sc = ws.filter((w) => h.has(w)).length / ws.length;
		if (sc > score) (score = sc), (best = e);
	}
	return score >= 0.6 ? best : heardText;
};
// spread the words of `text` over the time the heard words took
const spread = (text, heardWords) => {
	const shown = text.split(/\s+/);
	const total = heardWords.reduce((a, w) => a + w.w.length, 0);
	const curve = [];
	let acc = 0;
	for (const w of heardWords) {
		curve.push([acc / total, w.s]);
		acc += w.w.length;
		curve.push([acc / total, w.e]);
	}
	const at = (f) => {
		for (let k = 1; k < curve.length; k++) {
			if (f <= curve[k][0]) {
				const [f0, t0] = curve[k - 1], [f1, t1] = curve[k];
				return f1 > f0 ? t0 + ((f - f0) / (f1 - f0)) * (t1 - t0) : t1;
			}
		}
		return curve.at(-1)[1];
	};
	const len = shown.join('').length;
	let a2 = 0;
	return shown.map((w) => {
		const s = at(a2 / len);
		a2 += w.length;
		return {w, s, e: at(a2 / len)};
	});
};
const norm = (w) => w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');

for (const name of want) {
	const dir = path.join(SRC, name);
	if (!fs.existsSync(path.join(dir, 'timeline.json'))) {
		console.log(`- ${name}: no recording yet`);
		continue;
	}
	const t = JSON.parse(fs.readFileSync(path.join(dir, 'timeline.json'), 'utf8'));
	const video = path.join(out, `${name}.mp4`);
	// a keyframe every half second, so any moment of the recording can be cut to
	if (newer(path.join(dir, 'video.mp4'), video)) {
		ff(['-i', path.join(dir, 'video.mp4'), '-vf', 'scale=936:-2', '-r', '30', '-g', '15', '-c:v', 'libx264', '-crf', '15', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-an', video]);
	}
	const cap = {seconds: t.seconds, lang: t.lang, viewport: t.viewport, video: `cap/${name}.mp4`, events: t.events, screen: t.screen || [], said: []};

	const coach = t.audio.find((a) => a.kind === 'coach');
	if (coach) {
		const mp3 = path.join(out, `${name}-coach.mp3`);
		if (newer(path.join(dir, coach.file), mp3)) ff(['-i', path.join(dir, coach.file), '-ar', '44100', '-ac', '2', '-b:a', '192k', mp3]);
		cap.coach = {file: `cap/${name}-coach.mp3`, start: coach.start, lufs: lufs(path.join(out, `${name}-coach.mp3`))};
		const wordsFile = path.join(dir, 'words.json');
		if (newer(path.join(dir, coach.file), wordsFile)) {
			execFileSync('uv', ['run', '-q', '--with', 'faster-whisper', 'python', path.join(film, 'scripts/words.py'), path.join(dir, coach.file), t.lang, wordsFile], {stdio: 'inherit'});
		}
		// times in the recording's clock
		const heard = JSON.parse(fs.readFileSync(wordsFile, 'utf8')).map((w) => ({w: w.w, s: w.s + coach.start, e: w.e + coach.start}));
		const users = t.audio.filter((a) => a.kind === 'user').sort((a, b) => a.start - b.start);
		users.forEach((u, i) => {
			const mp3 = path.join(out, `${name}-user-${i}.mp3`);
			fs.copyFileSync(path.join(dir, u.file), mp3);
			// the user's words: spread over the clip by length
			const ws = u.text.split(/\s+/);
			const total = ws.join('').length;
			let acc = 0;
			const lead = 0.12, body = u.seconds - 0.3;
			const words = ws.map((w) => {
				const s = u.start + lead + (acc / total) * body;
				acc += w.length;
				return {w, s, e: u.start + lead + (acc / total) * body};
			});
			cap.said.push({who: 'user', kind: 'question', text: u.text, file: `cap/${name}-user-${i}.mp3`, lufs: lufs(mp3), s: u.start, e: u.start + u.seconds, words});
		});
		// the coach: greeting before the first question, then per question "let me look" and the answer
		const answers = cap.screen.filter((e) => e.name === 'coach').map((e) => {
			try {
				return {at: e.at, text: JSON.parse(e.data).text};
			} catch {
				return {at: e.at, text: ''};
			}
		});
		const bounds = [0, ...users.map((u) => u.start + u.seconds - 0.2), 1e9];
		for (let i = 0; i + 1 < bounds.length; i++) {
			const ws = heard.filter((w) => w.e >= bounds[i] && w.e < bounds[i + 1]).map((w) => ({...w, s: Math.max(w.s, Math.min(bounds[i] + 0.2, w.e - 0.05))}));
			if (!ws.length) continue;
			if (i === 0) {
				// the opening is not sent to the screen as an event, so its caption is what was heard, with the two names
				// the transcriber cannot know put right
				const text = ws.map((w) => w.w).join(' ').replace(/^Hi,? I know,? it'?s Corey\.?/i, "Hi Aino, it's Kori.").replace(/\bCorey\b/g, 'Kori');
				cap.said.push({who: 'coach', kind: 'greeting', text, s: ws[0].s, e: ws.at(-1).e, words: spread(text, ws)});
				continue;
			}
			const ans = answers.find((a) => a.at >= bounds[i] && a.at < bounds[i + 1]);
			let cut = 0;
			if (ans && ans.text) {
				const first = ans.text.split(/\s+/).slice(0, 2).map(norm);
				cut = ws.findIndex((w, k) => norm(w.w) === first[0] && (!ws[k + 1] || norm(ws[k + 1].w) === first[1]));
				if (cut < 0) {
					// no match: the answer starts after the longest pause
					let gap = 0;
					for (let k = 1; k < ws.length; k++) if (ws[k].s - ws[k - 1].e > gap) (gap = ws[k].s - ws[k - 1].e), (cut = k);
				}
			}
			const filler = ws.slice(0, cut), answer = ws.slice(cut);
			if (filler.length) {
				const text = written(filler.map((w) => w.w).join(' '));
				cap.said.push({who: 'coach', kind: 'filler', text, s: filler[0].s, e: filler.at(-1).e, words: spread(text, filler)});
			}
			if (answer.length) {
				// show the answer as it was written, timed by how it was heard
				const text = ans && ans.text ? ans.text : answer.map((w) => w.w).join(' ');
				cap.said.push({who: 'coach', kind: 'answer', text, s: answer[0].s, e: answer.at(-1).e, words: spread(text, answer)});
			}
		}
		cap.said.sort((a, b) => a.s - b.s);
	}
	caps[name] = cap;
	console.log(`+ ${name}: ${t.seconds}s, ${cap.said.length} utterances`);
	for (const u of cap.said) console.log(`    ${u.s.toFixed(1).padStart(5)}-${u.e.toFixed(1).padStart(5)} ${u.who.padEnd(5)} ${u.kind.padEnd(8)} ${u.text.slice(0, 90)}`);
}
fs.writeFileSync(dataFile, JSON.stringify(caps, null, 1));
