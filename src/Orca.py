import yaml
import asyncio
import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from utils.LLM import LLMClient, LLMClientConfig

class Orca:
	def __init__(self, config: dict | str):
		if isinstance(config, dict):
			self.config = config
		elif isinstance(config, str):
			with open(config, "r") as file:
				self.config = yaml.safe_load(file.read())

		# subprocesses
		self.llm = None

		self._shutdown_evt = asyncio.Event()

	async def run(self):
		try:
			await self.start()
			await self._shutdown_evt.wait()
		except asyncio.CancelledError:
			pass
		finally:
			await self.stop()

	async def start(self):
		print(Path.cwd())

		script_dir = Path(__file__).parent.resolve()
		print(Path(__file__).parent.resolve())

		self.llm = LLMClient(LLMClientConfig(
			backend_location=Path(__file__).parent.parent / os.getenv("LLAMA_BACKEND"),
			host=os.getenv("HOST_ADDRESS"),
			port=os.getenv("LLM_PORT"),
			model=self.config["chat"]["model_path"],
			alias=self.config["name"],
			context_length=self.config["chat"]["context_length"],
			log_dir=os.getenv("SUBPROCESS_LOG_DIR")
		))

	async def stop(self):
		self._shutdown_evt.set()

def main():
	# Get config data
	orca_env_path = os.path.join(os.path.dirname(__file__), ".env")
	load_dotenv(dotenv_path=orca_env_path, override=False)

	load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"), override=False)

	parser = argparse.ArgumentParser()
	parser.add_argument("config", help="Path to YAML config")
	args = parser.parse_args()

	# Load config
	with open(args.config, "r") as file:
		config = yaml.safe_load(file.read())

	# Run app
	app = Orca(args.config)
	asyncio.run(app.run())

if __name__ == "__main__":
	main()