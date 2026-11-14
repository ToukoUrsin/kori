"""Word timings for a recorded voice clip (local Whisper, no API). usage: words.py <audio> <lang> <out.json>"""
import json
import subprocess
import sys

import numpy as np

from faster_whisper import WhisperModel

audio, lang, out = sys.argv[1:4]
model = WhisperModel("small", download_root="/bulk2/runs/spankki/whisper", device="cpu", compute_type="int8", cpu_threads=16)
raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", audio, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
pcm = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
segments, _ = model.transcribe(pcm, language=lang, word_timestamps=True, vad_filter=True, beam_size=5,
                               condition_on_previous_text=False)
words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segments for w in s.words]
json.dump(words, open(out, "w"), ensure_ascii=False)
print(len(words), "words:", " ".join(w["w"] for w in words)[:1500])
