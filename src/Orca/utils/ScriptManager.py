import importlib.util
import sys
from pathlib import Path

from .ScriptClient import ScriptClient
from .ScriptRuntime import ScriptRuntime

class ScriptManager:
	def __init__(self, app, scripts: list[str]):
		self.app = app
		self.scripts = scripts
		self.clients: dict[str, ScriptClient] = {}

	def load_scripts(self):
		for script_path in self.scripts:
			module = self._load_module(script_path)

			runtime = ScriptRuntime(self.app)
			client = ScriptClient(runtime)

			if hasattr(module, "setup"):
				module.setup(client)

				if not client.name:
					raise ValueError(f"{script_path} did not set client.name")

				# Register docs AFTER setup
				if client._docs:
					self.app.function_registry.register_client(
						client.name,
						client._docs
					)

				self.clients[client.name] = client
			else:
				print(f"[ScriptManager] {script_path} has no setup(client)")

	def _load_module(self, path: str):
		path = Path(path).resolve()
		spec = importlib.util.spec_from_file_location(path.stem, path)
		module = importlib.util.module_from_spec(spec)

		sys.modules[path.stem] = module
		spec.loader.exec_module(module)

		return module

	def get_all(self):
		return self.clients.values()