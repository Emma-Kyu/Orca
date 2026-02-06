import requests
import json

from dataclasses import dataclass
from typing import Iterator

from .start_subprocess import start_subprocess
from .Hyperparameters import Hyperparameters

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
		print("LLM server terminated")

	def send_generation_request(self, messages: list[dict], hyperparameters: Hyperparameters) -> requests.Response:
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