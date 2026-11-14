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
  (recording seconds), with camera keys (`zoom`), mute and a note per part. Scene lengths follow from the footage and
  the narration. Two parts of the same recording with a gap are a cut, and the film marks it ("5 s wait cut");
  `cut: false` is for a jump that skipped no waiting (another screen).
- `src/footage.tsx` is the stage: the phone stands in the left half, the words in the right half. The camera
  (`zoom: [{at, z, y, d}]`) scales the whole phone and centres app pixel `y`, so the full width of the app stays
  readable; at `z` 1.75 about 540 app pixels are in view. It keeps its place across cuts; `d: 0` is a hard cut.
  The parts play with their real sound, the cut chips and the live strip (the calculation picked and "N numbers
  checked", from the recording's own events).
- Narration: `scripts/make-vo.mjs` (ElevenLabs, cached by text in `public/audio/vo/`). Lines marked `PART_B` are not
  generated until `--part-b`; until then they are silent but keep their time and caption. `--print` lists them.
  Run with `hsec exec --only ELEVENLABS_API_KEY -- node scripts/make-vo.mjs [--part-b]`.
- Proof: `src/data/backtest-months.json`, the app's own backtest per month, made by `scripts/backtest-months.py`
  (fails unless its totals equal `docs/backtest.json`).
- `public/audio/tick.mp3` (the sound on a cut) is made with ffmpeg: two short decaying sine tones.

## Making a new cut

1. Record, in the container: `capture/run.sh voice3`, `loop`, `lesson2`, `figures`, `peers`, `host`, `teach`.
2. `node scripts/import-caps.mjs` (all of them, or name the ones that changed).
3. Point the slots in `src/Film.tsx` at them (the comments there say what each must show), set the segment times
   from `caps.json` (`said`, `events`, `screen`), and the beats. The transcriber's word starts can be up to 0.7 s
   early: set cuts in speech from the silences in `public/cap/<name>-coach.mp3`.
4. `hsec exec --only ELEVENLABS_API_KEY -- node scripts/make-vo.mjs --part-b` (cached by text: unchanged lines cost
   nothing).
5. `scripts/stills.sh <name> <frame> ...` renders single frames and a contact sheet to
   `/bulk2/runs/spankki/film/stills/<name>/`, in the container.
6. `scripts/render.sh <name>`. Copy the cut that ships to `/bulk2/runs/spankki/film/out/kori.mp4`:
   `scripts/deploy.sh` (repo root) puts it on the site at `/film`.
