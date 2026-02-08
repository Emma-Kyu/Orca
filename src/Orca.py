import yaml
import asyncio
import argparse
import os

from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from utils.LLM import LLMClient, LLMClientConfig, LLMHyperparameters
from utils.STT import STTClient, STTClientConfig, STTHyperparameters
# from utils.TTS import TTSClient, TTSClientConfig, TTSHyperparameters

from utils.Context import Context
from utils.EventBus import EventBus, EventBusConfig

class Orca:
	def __init__(self, config: dict | str):
		if isinstance(config, dict):
			self.config = config
		elif isinstance(config, str):
			with open(config, "r") as file:
				self.config = yaml.safe_load(file.read())

		# subprocesses
		self.llm = None
		self.stt = None

		self.system_prompt_replacements = {
			"<date>": datetime.today().strftime("%Y-%m-%d"),
			"<time>": datetime.now().strftime("%I:%M %p"),
			# "<functions>": utils.format_functions(self.function_registry.get_all_functions())
		}
		self.context = Context(self.config["chat"]["system_prompt"], self.system_prompt_replacements)

		self.event_bus = EventBus(EventBusConfig(
			user_data=self
		))

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
		self.llm = LLMClient(LLMClientConfig(
			backend_location=Path(__file__).parent.parent / os.getenv("LLAMA_BACKEND"),
			host=os.getenv("HOST_ADDRESS"),
			port=os.getenv("LLM_PORT"),
			model=self.config["chat"]["model_path"],
			alias=self.config["name"],
			context_length=self.config["chat"]["context_length"],
			log_dir=os.getenv("SUBPROCESS_LOG_DIR")
		))

		self.stt = STTClient(STTClientConfig(
			backend_location=Path(__file__).parent.parent / os.getenv("WHISPER_BACKEND"),
			host=os.getenv("HOST_ADDRESS"),
			port=os.getenv("STT_PORT"),
			model=self.config["stt"]["model_path"],
			vad=self.config["stt"]["vad_path"],
			log_dir=os.getenv("SUBPROCESS_LOG_DIR")
		))

		asyncio.create_task(self.event_loop())

	async def stop(self):
		self._shutdown_evt.set()

		for p in (self.llm, self.stt):
			try:
				p.close()
			except Exception:
				pass

	async def event_loop(self):
		while not self._shutdown_evt.is_set():
			await self.event_bus.process_queue();

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