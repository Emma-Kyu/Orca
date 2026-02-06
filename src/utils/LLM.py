import requests
import json

from dataclasses import dataclass, field
from typing import Iterator

from .start_subprocess import start_subprocess

@dataclass
class LLMHyperparameters:
	temperature: float = 0.8
	min_p: float = 0.1
	top_k: int = 40
	presence_penalty: float = 0.0
	repetition_penalty: float = 1.0
	repeat_last_n: int = 64

	# XTC
	xtc_threshold: float = 0.1
	xtc_probability: float = 0.0

	# DRY sampling
	dry_multiplier: float = 0.0
	dry_base: float = 1.75
	dry_allowed_length: int = 2
	dry_penalty_last_n: int = -1
	dry_sequence_breakers: list[str] = field(
		default_factory=lambda: ['\n', ':', '"', '*']
	)

	# Misc
	n_predict: int = 512
	logit_bias: list = field(default_factory=list)
	samplers: list[str] = field(
		default_factory=lambda: [
			"dry", "top_k", "typ_p", "top_p",
			"min_p", "xtc", "temperature"
		]
	)

	# Legacy fallback
	seed: int = -1

	@classmethod
	def from_dict(cls, params: dict):
		return cls(**params)

	def to_payload(self, messages: list[dict]) -> dict:
		return {
			"messages": messages,

			"temperature": self.temperature,

			"xtc_threshold": self.xtc_threshold,
			"xtc_probability": self.xtc_probability,

			"min_p": self.min_p,
			"top_k": self.top_k,

			"presence_penalty": self.presence_penalty,
			"repeat_penalty": self.repetition_penalty,
			"repeat_last_n": self.repeat_last_n,

			"id_slot": 0,
			"cache_prompt": True,
			"stream": True,
			"n_predict": self.n_predict,
			"seed": self.seed,
			"logit_bias": self.logit_bias,
			"samplers": self.samplers,

			# DRY specific
			"dry_multiplier": self.dry_multiplier,
			"dry_base": self.dry_base,
			"dry_allowed_length": self.dry_allowed_length,
			"dry_penalty_last_n": self.dry_penalty_last_n,
			"dry_sequence_breakers": self.dry_sequence_breakers,
		}

@dataclass
class LLMClientConfig:
	# Executable location
	backend_location: str = "./vendor/bin/llama.cpp"
	
	# Connectivity
	host: str = "127.0.0.1"
	port: int = 8000
	endpoint: str = "/chat/completions" # LLama.cpp default

	# Data
	model: str = "UnnamedLLM.gguf"
	alias: str = "UnnamedLLM"
	context_length: int = 4096

	log_dir: str = "./"

class LLMClient:
	def __init__(self, config: LLMClientConfig):
		self.endpoint = f"http://{config.host}:{config.port}{config.endpoint}"
		self.session = requests.Session()

		cmd = [
			f"{config.backend_location}\\llama-server",
			# Optimisations
			"-b", "2048", "-ub", "512", "-ngl", "255", "-sm", "none", "-fa", "1", "--cache-ram", "0", "-kvu", "-nocb",
			"-ctk", "q8_0", "-ctv", "q8_0", "--no-mmap", "--threads-http", "1", "--parallel", "1", "--cache-reuse", "128",
			# Connectivity
			"--host", config.host, "--port", str(config.port),
			"-m", config.model, "-c", str(config.context_length), "--alias", config.alias,
			"--no-prefill-assistant"
		]
		# TODO does python have destructors?
		self.process = start_subprocess(cmd, config.log_dir)
		print(f"LLM server running at: {self.endpoint}")

	def close(self):
		self.process.terminate()
		self.process.wait()

	def send_generation_request(self, messages: list[dict], hyperparameters: LLMHyperparameters) -> requests.Response:
		response = self.session.post(self.endpoint, json = hyperparameters.to_payload(messages), stream = True)
		return response

	def get_streaming_response(self, response: requests.Response) -> Iterator[str]:
		response.raise_for_status()
		for line in response.iter_lines():
			if not line:
				continue
			if line == b"[DONE]":
				break
			line = line.removeprefix(b"data:").lstrip()
			# Convert to string
			line = line.decode("utf-8", errors="ignore").strip()
			# Parse JSON
			try:
				chunk = json.loads(line)
				yield chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
			except Exception:
				continue