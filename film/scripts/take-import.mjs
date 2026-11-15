#!/usr/bin/env node
// Brings what the take film is cut from into its public folder (outside the repo) and writes src/data/take-caps.json:
// the recordings of the real app (screen video at full resolution, the time of every tap), Kori's real voice, and the
// cold open and end card, read from their own folder by path so that a new open is picked up by the next render.
//   node scripts/take-import.mjs
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync, spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const film = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RUN = process.env.KORI_TAKE || '/bulk3/runs/spankki/film2';
const OPEN = process.env.KORI_OPEN || '/bulk3/runs/opens/final/kori';
const PUB = path.join(RUN, 'public');
// which recording each shot is cut from (folders under cap/)
const USED = JSON.parse(fs.readFileSync(path.join(film, 'src/data/take-used.json'), 'utf8')).caps;

const ff = (a) => execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...a], {stdio: ['ignore', 'inherit', 'inherit']});
const probe = (file, entries) => execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', entries, '-of', 'csv=p=0', file], {encoding: 'utf8'}).trim();
const lufs = (file) => {
	const r = spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-i', file, '-af', 'ebur128', '-f', 'null', '-'], {encoding: 'utf8'});
	const m = [...r.stderr.matchAll(/I:\s+(-?[\d.]+) LUFS/g)].at(-1);
	return m ? Number(m[1]) : undefined;
};
const newer = (a, b) => !fs.existsSync(b) || fs.statSync(a).mtimeMs > fs.statSync(b).mtimeMs;
for (const d of ['cap', 'open', 'audio', 'take']) fs.mkdirSync(path.join(PUB, d), {recursive: true});

const caps = {};
for (const [key, folder] of Object.entries(USED)) {
	const dir = path.join(RUN, 'cap', folder);
	const t = JSON.parse(fs.readFileSync(path.join(dir, 'timeline.json'), 'utf8'));
	const video = path.join(PUB, 'cap', `${key}.mp4`);
	const stamp = path.join(PUB, 'cap', `${key}.from`);
	if (newer(path.join(dir, 'video.mp4'), video) || !fs.existsSync(stamp) || fs.readFileSync(stamp, 'utf8') !== folder) {
		// a keyframe every half second, so any moment of the recording can be cut to
		ff(['-i', path.join(dir, 'video.mp4'), '-r', '30', '-g', '15', '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-an', video]);
		fs.writeFileSync(stamp, folder);
	}
	const [pw, ph] = probe(video, 'stream=width,height').split(',').map(Number);
	const cap = {video: `cap/${key}.mp4`, from: folder, w: t.viewport[0], h: t.viewport[1], px: [pw, ph], seconds: t.seconds, events: t.events.map((e) => ({at: e.at, kind: e.kind, label: e.label, box: e.box}))};
	const a = (t.audio || [])[0];
	if (a) {
		const out = path.join(PUB, 'cap', `${key}-voice.wav`);
		// Kori's real voice, levelled to sit just under the founder's (-17.4 LUFS): one gain and a peak limiter
		const was = lufs(path.join(dir, a.file));
		ff(['-i', path.join(dir, a.file), '-af', `volume=${(-18.5 - was).toFixed(2)}dB,alimiter=limit=0.79:attack=3:release=80:level=false`, '-ac', '1', '-ar', '48000', out]);
		cap.voice = {file: `cap/${key}-voice.wav`, start: a.start, lufs: lufs(out)};
	}
	caps[key] = cap;
	console.log(`${key}: ${folder}, ${pw}x${ph}, ${t.seconds.toFixed(1)} s${cap.voice ? `, voice from ${cap.voice.start.toFixed(2)} s at ${cap.voice.lufs} LUFS` : ''}`);
}

// the cold open and the end card, as they are in their folder now
for (const f of ['open.mp4', 'end.mp4']) fs.copyFileSync(path.join(OPEN, f), path.join(PUB, 'open', f));
const dur = (f) => Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], {encoding: 'utf8'}).trim());
const open = {seconds: dur(path.join(OPEN, 'open.mp4')), lufs: lufs(path.join(OPEN, 'open.mp4')), end: dur(path.join(OPEN, 'end.mp4')), stamp: fs.statSync(path.join(OPEN, 'open.mp4')).mtime.toISOString()};
console.log(`open: ${open.seconds.toFixed(2)} s, ${open.lufs} LUFS (${open.stamp}); end card ${open.end.toFixed(2)} s`);

const take = {lufs: lufs(path.join(PUB, 'take/voice.wav'))};
fs.writeFileSync(path.join(film, 'src/data/take-caps.json'), JSON.stringify({caps, open, take}, null, 1));
