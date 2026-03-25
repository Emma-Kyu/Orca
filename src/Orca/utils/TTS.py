import time
import re
import numpy as np
import os
import math

from kokoro import KPipeline
from dataclasses import dataclass

@dataclass
class TTSClientConfig:
	model_path: str
	voice_pack: str
	pitch_shift: float

class TTSClient:
	def __init__(self, config: TTSClientConfig):
		self.pipeline = KPipeline(
			model_path=config.model_path,
			config_path=os.path.join(os.path.dirname(config.model_path), "config.json"),
			voice_path=config.voice_pack,
			lang_code="a"
		)
		self.sample_rate = 24000
		self.pitch_shift = config.pitch_shift

		# Waiting time for different punctuation
		self.PUNCTUATION_PAUSE = {
			".": 0.4,
			"!": 0.4,
			"?": 0.5,
			";": 0.2,
			":": 0.2
		}

		# Default if nothing matches
		self.DEFAULT_PAUSE = 0.5

		print(f"TTS initialised")

	def split_text(self, text: str) -> list[str]:
		splitters = {".", "!", "?", ":", ";"}
		out, current = [], []
		i = 0
		n = len(text)

		while i < n:
			ch = text[i]
			current.append(ch)

			# Handle ellipsis or consecutive dots
			if ch == ".":
				start = i
				while i + 1 < n and text[i + 1] == ".":
					i += 1
					current.append(".")
				clause = "".join(current).strip()
				if clause and not all(c in splitters for c in clause):
					out.append(clause)
				current.clear()

			# Handle other splitting punctuation
			elif ch in splitters - {"."}:
				clause = "".join(current).strip()
				if clause and not all(c in splitters for c in clause):
					out.append(clause)
				current.clear()

			i += 1

		# Add any trailing fragment (if not empty and not just punctuation)
		if current:
			clause = "".join(current).strip()
			if clause and not all(c in splitters for c in clause):
				out.append(clause)

		return out

	def _ellipsis_pause(self, dot_count: int) -> float:
		return math.sqrt(min(0, dot_count - 1)) / 2 + 0.5

	def get_required_tail_sec(self, text: str) -> float:
		if not text:
			return self.DEFAULT_PAUSE

		s = text.rstrip()
		if not s:
			return self.DEFAULT_PAUSE

		# Count trailing dots
		dot_count = 0
		for ch in reversed(s):
			if ch == ".":
				dot_count += 1
			else:
				break

		# Ellipsis path: 2 or more trailing dots
		if dot_count >= 2:
			return self._ellipsis_pause(dot_count)

		# Single punctuation path
		last_char = s[-1]
		if last_char in self.PUNCTUATION_PAUSE:
			return self.PUNCTUATION_PAUSE[last_char]

		return self.DEFAULT_PAUSE

	def trim_and_pad(self, audio, text=""):
		# Samples for the window
		RMS_WINDOW_SIZE = 256
		# Silence threshold
		RMS_THRESHOLD = 0.005
		# Additional padding
		PRE_PAD_SEC = 0.1

		if audio is None or len(audio) == 0:
			return np.asarray([], dtype=np.float32)

		audio = np.asarray(audio, dtype=np.float32)
		sr = self.sample_rate

		# 1. Windowed RMS to detect voiced regions
		window = RMS_WINDOW_SIZE
		n = len(audio)
		rms = np.array([
			np.sqrt(np.mean(audio[i:i + window] ** 2))
			for i in range(0, n, window)
		])

		active = np.where(rms > RMS_THRESHOLD)[0]
		if active.size == 0:
			return np.asarray([], dtype=np.float32)

		speech_start_idx = max(0, active[0] * window)
		speech_end_idx   = min(n, (active[-1] + 1) * window)

		# 2. Pick how long the tail SHOULD be
		required_tail_sec = self.get_required_tail_sec(text)
		required_tail_samples = int(required_tail_sec * sr)

		# 3. Slice start/end from original audio
		start_idx = max(0, int(speech_start_idx - PRE_PAD_SEC * sr))
		desired_end_idx = speech_end_idx + required_tail_samples
		end_idx_in_audio = min(n, desired_end_idx)

		trimmed = audio[start_idx:end_idx_in_audio]

		# 4. If we ran out of source audio before desired_end_idx, append zeros
		if desired_end_idx > n:
			shortfall = desired_end_idx - n
			if shortfall > 0:
				trimmed = np.concatenate([
					trimmed,
					np.zeros(shortfall, dtype=np.float32)
				], axis=0)

		return np.asarray(trimmed, dtype=np.float32)

	def _resample_linear(self, audio: np.ndarray, ratio: float) -> np.ndarray:
		if ratio == 1.0:
			return audio.astype(np.float32, copy=False)

		n_in = audio.shape[0]
		n_out = max(1, int(round(n_in / ratio)))
		x_old = np.linspace(0.0, 1.0, num=n_in, endpoint=False, dtype=np.float64)
		x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False, dtype=np.float64)

		idx = np.searchsorted(x_old, x_new, side="right") - 1
		idx = np.clip(idx, 0, n_in - 2)

		x0 = x_old[idx]
		x1 = x_old[idx + 1]
		y0 = audio[idx]
		y1 = audio[idx + 1]

		den = (x1 - x0)
		den[den == 0] = 1.0
		frac = (x_new - x0) / den

		out = y0 + (y1 - y0) * frac
		return out.astype(np.float32)

	def _apply_pitch_shift(self, audio: np.ndarray) -> np.ndarray:
		ratio = 2.0 ** (self.pitch_shift / 12.0)
		if ratio == 1.0:
			return audio
		shifted = self._resample_linear(audio, ratio)
		return shifted.astype(np.float32)

	def text_to_audio(self, text: str):
		for clause in self.split_text(text):
			if not clause.strip():
				continue
			for _, _, audio in self.pipeline(clause):
				trimmed = self.trim_and_pad(audio, text=clause)
				if trimmed.size == 0:
					continue
				shifted = self._apply_pitch_shift(trimmed)
				if shifted.size == 0:
					continue
				yield shifted
