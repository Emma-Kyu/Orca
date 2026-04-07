import yaml
import asyncio
import argparse
import os

from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from .utils.LLM import LLMClient, LLMClientConfig, LLMHyperparameters
from .utils.STT import STTClient, STTClientConfig, STTHyperparameters
from .utils.TTS import TTSClient, TTSClientConfig

from .utils.AIOApp import AIOApp, AIOAppConfig

from .utils.Context import Context
from .utils.EventBus import EventBus, EventBusConfig
from .utils.WebSocket import WebSocket, WebSocketConfig

from .utils.ClientManager import ClientManager
from .utils.FunctionRegistry import FunctionRegistry

from .utils.BarrierTracker import BarrierTracker

from .utils.Events import (
	ClientConnectEvent, ClientDisconnectEvent, ClientMessageEvent, FunctionReturnEvent, RebuildPromptEvent,
	Schema_ConnectEvent, Schema_DisconnectEvent, Schema_MessageEvent, Schema_FunctionResultEvent
)

from .utils.ScriptManager import ScriptManager

from .utils.start_subprocess import start_subprocess

class Orca:
	def __init__(self, config: dict | str):
		if isinstance(config, dict):
			self.config = config
		elif isinstance(config, str):
			with open(config, "r") as file:
				self.config = yaml.safe_load(file.read())

		self.backend_path = Path(__file__).resolve().parents[2] / "vendor" / "bin"

		self.subprocesses = []

		# subprocesses
		self.llm = None
		self.stt = None
		self.tts = None

		# connectivity
		self.http = None
		self.ws = None

		# prompts
		now = datetime.now()
		self.system_prompt_replacements = {
			"<date>": now.strftime("%Y-%m-%d"),
			"<time>": now.strftime("%I:%M %p")
		}
		self.context = Context(self.config["chat"]["system_prompt"], self.system_prompt_replacements)

		self.client_manager = ClientManager()
		self.script_manager = ScriptManager(self, self.config.get("scripts", []))
		self.function_registry = FunctionRegistry()
		self.barriers = BarrierTracker()

		# events
		self.event_bus = EventBus(EventBusConfig(
			user_data=self
		))
		self._shutdown_evt = asyncio.Event()
		self._event_task: asyncio.Task | None = None

	async def run(self):
		try:
			await self.start()
			await self._shutdown_evt.wait()
		except asyncio.CancelledError:
			pass
		finally:
			await self.stop()

	async def start(self):
		host = os.getenv("HOST_ADDRESS", "127.0.0.1")
		subprocess_log_dir = os.getenv("SUBPROCESS_LOG_DIR")
		backend_path = Path(__file__).parent.parent

		self.llm = LLMClient(LLMClientConfig(
			backend_location=backend_path / os.getenv("LLAMA_BACKEND"),
			host=host,
			port=int(os.getenv("LLM_PORT")),
			model=self.config["chat"]["model_path"],
			alias=self.config["name"],
			context_length=self.config["chat"]["context_length"],
			log_dir=subprocess_log_dir
		))

		self.stt = STTClient(STTClientConfig(
			backend_location=backend_path / os.getenv("WHISPER_BACKEND"),
			host=host,
			port=int(os.getenv("STT_PORT")),
			model=self.config["stt"]["model_path"],
			vad=self.config["stt"]["vad_path"],
			log_dir=subprocess_log_dir
		))
		self.tts = TTSClient(TTSClientConfig(
			model_path=self.config["tts"]["model_path"],
			voice_pack=self.config["tts"]["voice_pack"],
			pitch_shift=self.config["tts"]["pitch_shift"]
		))

		self.http = AIOApp(AIOAppConfig(
			host=host,
			port=int(os.getenv("HTTP_PORT"))
		))

		self.ws = WebSocket(WebSocketConfig(
			host=host,
			port=int(os.getenv("WEBSOCKET_PORT"))
		))

		async def _on_connect(ws, payload):
			self.event_bus.push_event(ClientConnectEvent(ws, payload))
		async def _on_disconnect(ws, payload):
			self.event_bus.push_event(ClientDisconnectEvent(ws))
		async def _on_message(ws, payload):
			self.event_bus.push_event(ClientMessageEvent(ws, payload))
		async def _on_function_result(ws, payload):
			self.event_bus.push_event(FunctionReturnEvent(payload))

		async def _on_open_input_stream(ws, payload):
			pass
		async def _on_close_input_stream(ws, payload):
			pass
		async def _on_input_stream_data(ws, payload):
			pass


		self.ws.add_event("connect", _on_connect, Schema_ConnectEvent)
		self.ws.add_event("disconnect", _on_disconnect, Schema_DisconnectEvent)
		self.ws.add_event("message", _on_message, Schema_MessageEvent)
		self.ws.add_event("function_result", _on_function_result, Schema_FunctionResultEvent)

		self.ws.register_on_disconnect("disconnect")

		# self.ws.add_event("open_input_stream", _on_open_input_stream, Schema_OpenInputStream)
		# self.ws.add_event("close_input_stream", _on_close_input_stream, Schema_CloseInputStream)
		# self.ws.add_event("input_stream_data", _on_input_stream_data, Schema_InputStreamData)

		# Load scripts
		self.script_manager.load_scripts()

		self.event_bus.push_event(RebuildPromptEvent())

		# Turn on connectivity
		await self.http.start()
		await self.ws.start()

		self._event_task = asyncio.create_task(self.event_loop())

	async def stop(self):
		self._shutdown_evt.set()

		# Unblock event loop if it's waiting on the queue
		try:
			self.event_bus.stop()
		except Exception:
			pass

		# Stop the event task
		if self._event_task:
			self._event_task.cancel()
			try:
				await self._event_task
			except asyncio.CancelledError:
				pass
			finally:
				self._event_task = None

		# Turn off connectivity
		await self.http.stop()
		await self.ws.stop()

		# Close subprocesses
		for p in self.subprocesses:
			try:
				p.terminate()
			except Exception:
				pass

		# Close subprocesses
		for p in (self.llm, self.stt):
			try:
				p.close()
			except Exception:
				pass

	async def event_loop(self):
		while not self._shutdown_evt.is_set():
			await self.event_bus.process_queue();

	def start_subprocess(self, cmd):
		p = start_subprocess(cmd, os.getenv("SUBPROCESS_LOG_DIR"))
		self.subprocesses.append(p)
		return p

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
	app = Orca(config)
	asyncio.run(app.run())

if __name__ == "__main__":
	main()