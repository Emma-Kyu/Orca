import io
import wave
import requests

from dataclasses import dataclass
from pathlib import Path

from .start_subprocess import start_subprocess

@dataclass
class STTHyperparameters:
	language: str = "en"

	@classmethod
	def from_dict(cls, config: dict):
		hp = config.get("hyperparameters", {})

		return cls(
			language = hp.get("language", config.get("language", "en"))
		)

@dataclass
class STTClientConfig:
	# Executable location
	backend_location: str = "./vendor/bin/StreamingSTT"

	# Connectivity
	host: str = "127.0.0.1"
	port: int = 8001
	endpoint: str = "/v1/audio/transcriptions"

	# Models
	model: str = ""
	mmproj: str = ""
	vad: str = ""
	smart_turn: str = ""

	# Runtime
	gpu_layers: int = 999
	smart_turn_threads: int = 1
	smart_turn_threshold: float = 0.5
	smart_turn_silence_ms: int = 50
	smart_turn_force_end_ms: int = 1500

	log_dir: str = "./"

class STTClient:
	def __init__(self, config: STTClientConfig):
		self.endpoint = f"http://{config.host}:{config.port}{config.endpoint}"
		self.session = requests.Session()

		self.sample_rate = 16000
		self.channels = 1
		self.sample_width = 2

		cmd = [
			f"{config.backend_location}\\StreamingSTT",
			"--model", str(config.model),
			"--mmproj", str(config.mmproj),
			"--vad", str(config.vad),
			"--host", config.host,
			"--port", str(config.port),
			"--n-gpu-layers", str(config.gpu_layers)
		]

		if config.smart_turn:
			cmd += [
				"--smart-turn", str(config.smart_turn),
				"--smart-turn-threads", str(config.smart_turn_threads),
				"--smart-turn-threshold", str(config.smart_turn_threshold),
				"--smart-turn-silence-ms", str(config.smart_turn_silence_ms),
				"--smart-turn-force-end-ms", str(config.smart_turn_force_end_ms)
			]

		self.process = start_subprocess(cmd, config.log_dir)

		print(f"STT server running at: {self.endpoint}")

	def close(self):
		self.session.close()

		if self.process.poll() is None:
			self.process.terminate()
			self.process.wait()

	def _pcm_to_wav(self, audio: bytes) -> bytes:
		buffer = io.BytesIO()

		with wave.open(buffer, "wb") as wav:
			wav.setnchannels(self.channels)
			wav.setsampwidth(self.sample_width)
			wav.setframerate(self.sample_rate)
			wav.writeframes(audio)

		return buffer.getvalue()

	def transcribe(self, hyperparameters: STTHyperparameters, audio: bytes) -> str:
		if not audio:
			return ""
		wav = self._pcm_to_wav(audio)
		response = self.session.post(
			self.endpoint,
			files = { "file": ("audio.wav", wav, "audio/wav") },
			data = { "language": hyperparameters.language }
		)
		response.raise_for_status()
		return response.json().get("text", "").strip()