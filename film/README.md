# The demo film

Everything in the film is recorded from the live app.

- `capture/record.mjs` drives the real app in Chrome and records the screen (3x), the coach's real voice and the
  moment of every tap and spoken question. Questions are spoken into a fake microphone, so the ElevenLabs agent
  really hears them. `capture/run.sh <scenario>` runs it in a container.
- `scenarios/` are the scripted sessions.
- Recordings are large and not in git. On the build machine they are in `/bulk2/runs/spankki/film/<scenario>/`
  (`video.mp4`, the audio clips, `timeline.json` and a mixed `preview.mp4`).
- `scripts/import-caps.mjs [names]` brings recordings into the film: `public/cap/<name>.mp4`, the voices, and
  `src/data/caps.json` (who said what when, the screen events). Recordings not made yet are skipped.
- `scripts/render.sh <name>` renders in the `kori-capture` container and masters the sound to -16 LUFS, under -1 dBTP
  (measure, one linear gain, a peak limiter). Output: `/bulk2/runs/spankki/film/out/<name>.mp4`.

## How the film is put together

- `src/Film.tsx` starts with `SLOTS`: the footage of every scene, by recording name and segment times
  (recording seconds), with punch-ins (`zoom`), mute and a note per part. Scene lengths follow from the footage and
  the narration. Two parts of the same recording with a gap are a cut, and the film marks it ("5 s wait cut").
- `src/footage.tsx` plays the parts in a phone with their real sound, the cut chips and the live strip
  (the calculation picked and "N numbers checked", from the recording's own events).
- Narration: `scripts/make-vo.mjs` (ElevenLabs, cached by text in `public/audio/vo/`). Lines marked `PART_B` are not
  generated until `--part-b`; until then they are silent but keep their time and caption. `--print` lists them.
  Run with `hsec exec --only ELEVENLABS_API_KEY -- node scripts/make-vo.mjs [--part-b]`.
- Proof: `src/data/backtest-months.json`, the app's own backtest per month, made by `scripts/backtest-months.py`
  (fails unless its totals equal `docs/backtest.json`).
- `public/audio/tick.mp3` (the sound on a cut) is made with ffmpeg: two short decaying sine tones.

## Part B: the new footage

1. Record, in the container: `capture/run.sh voice3`, `loop`, `lesson2`, `figures`, `peers`, `host`.
2. `node scripts/import-caps.mjs voice3 loop lesson2 figures peers host`.
3. Point the slots in `src/Film.tsx` at them (the comments there say what each must show), set the segment times
   from `caps.json` (`said`, `events`, `screen`), and the beats.
4. `hsec exec --only ELEVENLABS_API_KEY -- node scripts/make-vo.mjs --part-b`.
5. `scripts/render.sh kori-v2b`; contact sheet and loudness as in `/bulk2/runs/spankki/rounds/r2/film/`.
