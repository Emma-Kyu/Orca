import requests

from dataclasses import dataclass

from .start_subprocess import start_subprocess

@dataclass
class STTHyperparameters:
	beam_size: int = 5
	prompt: str = ""
	suppress_non_speech: bool = False
	temperature: float = 0.0
	vad: bool = True

	@classmethod
	def from_dict(cls, config: dict):
		hp = config.get("hyperparameters", {})
		return cls(
			beam_size = hp.get("beam_size", 5),
			prompt = config.get("prompt", ""),
		)

	def to_payload(self, audio_b64: str) -> dict:
		return {
			"audio": audio_b64,
			"prompt": self.prompt,
			"suppress_non_speech": self.suppress_non_speech,
			"temperature": self.temperature,
			"beam_size": self.beam_size,
			"vad": self.vad
		}

@dataclass
class STTClientConfig:
		# Executable location
		backend_location: str = "./vendor/bin/whisper.cpp"

		# Connectivity
		host: str = "127.0.0.1"
		port: int = 8001
		endpoint: str = "/inference"

		# Data
		model: str = "UnnamedSTT.gguf"
		vad: str = "UnnamedVAD.gguf"

		log_dir: str = "./"

class STTClient:
	def __init__(self, config: STTClientConfig):
		self.endpoint = f"http://{config.host}:{config.port}{config.endpoint}"
		self.session = requests.Session()

		self.sample_rate = 16000

		cmd = [
			f"{config.backend_location}\\whisper-server",
			"-m", config.model,
			"-vm", config.vad,
			"-fa",
			"--port", str(config.port)
		]
		# TODO does python have destructors?
		self.process = start_subprocess(cmd, config.log_dir)
		print(f"STT server running at: {self.endpoint}")

	def close(self):
		self.process.terminate()
		self.process.wait()

	def transcribe(self, hyperparameters: STTHyperparameters, audio_b64: str) -> str:
		response = self.session.post(self.endpoint, json = hyperparameters.to_payload(audio_b64))
		response.raise_for_status()

		return response.json().get("text", "").strip()
