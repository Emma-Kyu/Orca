import aiohttp_cors, aiohttp.web

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

Handler = Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.StreamResponse]]

@dataclass
class AIOAppConfig:
	host: str
	port: int

	post_endpoints: dict[str, Handler] = field(default_factory=dict)
	get_endpoints: dict[str, Handler] = field(default_factory=dict)
	put_endpoints: dict[str, Handler] = field(default_factory=dict)
	delete_endpoints: dict[str, Handler] = field(default_factory=dict)

	enable_cors: bool = False
	cors_policies: dict[str, aiohttp_cors.ResourceOptions] = field(default_factory=dict)

class AIOApp:
	def __init__(self, config: AIOAppConfig):
		self.host = config.host
		self.port = int(config.port)
		self.app = aiohttp.web.Application()
		self._runner = None
		self._site = None

		if config.enable_cors and not config.cors_policies:
			raise ValueError("CORS enabled but no cors_policies provided")

		self.cors = None
		if config.enable_cors:
			# If CORS is enabled, use whatever policies the caller provided.
			self.cors = aiohttp_cors.setup(self.app, defaults=config.cors_policies)

		for endpoint, function in config.post_endpoints.items():
			self.add_post(endpoint, function)
		for endpoint, function in config.get_endpoints.items():
			self.add_get(endpoint, function)
		for endpoint, function in config.put_endpoints.items():
			self.add_put(endpoint, function)
		for endpoint, function in config.delete_endpoints.items():
			self.add_delete(endpoint, function)

	def _maybe_cors(self, route: aiohttp.web.AbstractRoute):
		if self.cors is not None:
			self.cors.add(route)

	def add_post(self, endpoint: str, function: Handler):
		route = self.app.router.add_post(endpoint, function)
		self._maybe_cors(route)

	def add_get(self, endpoint: str, function: Handler):
		route = self.app.router.add_get(endpoint, function)
		self._maybe_cors(route)

	def add_put(self, endpoint: str, function: Handler):
		route = self.app.router.add_put(endpoint, function)
		self._maybe_cors(route)

	def add_delete(self, endpoint: str, function: Handler):
		route = self.app.router.add_delete(endpoint, function)
		self._maybe_cors(route)

	async def start(self):
		if self._runner:
			return
		self._runner = aiohttp.web.AppRunner(self.app)
		await self._runner.setup()
		self._site = aiohttp.web.TCPSite(self._runner, self.host, self.port)
		await self._site.start()
		print(f"HTTP running at http://{self.host}:{self.port}")
		print("Active endpoints:")
		for route in self.app.router.routes():
			if route.method in ("POST", "GET", "PUT", "DELETE"):
				info = route.resource.get_info()
				path = info.get("path") or info.get("formatter", "unknown")
				print(f"  - {route.method} {path}")

	async def stop(self):
		if not self._runner:
			return
		await self._runner.cleanup()
		self._runner = None
		self._site = None

	async def run(self):
		await self.start()
		try:
			# Never reached under normal managed use
			await aiohttp.web._run_app(self.app)
		finally:
			await self.stop()