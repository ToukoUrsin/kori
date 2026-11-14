# The demo film

Everything in the film is recorded from the live app.

- `capture/record.mjs` drives the real app in Chrome and records the screen (3x), the coach's real voice and the
  moment of every tap and spoken question. Questions are spoken into a fake microphone, so the ElevenLabs agent
  really hears them. `capture/run.sh <scenario>` runs it in a container.
- `scenarios/` are the scripted sessions.
- Recordings are large and not in git. On the build machine they are in `/bulk2/runs/spankki/film/<scenario>/`
  (`video.mp4`, the audio clips, `timeline.json` and a mixed `preview.mp4`).
