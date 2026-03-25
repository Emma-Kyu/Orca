import aiohttp.web

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, ValidationError

from .WebSocketCommon import WSServer

Handler = Callable[[any, any], Awaitable[None]]
Validator = Callable[[any, dict], tuple[bool, str | None]]

def validate_schema(schema: type[BaseModel], data: dict) -> tuple[dict | None, str | None]:
	try:
		return data, None
	except ValidationError as e:
		# Collapse validation errors into a single string for "reason"
		msgs = []
		for err in e.errors():
			loc = ".".join(str(p) for p in err.get("loc", []))
			msgs.append(f"{loc}: {err.get('msg')}")
		return None, "; ".join(msgs)

@dataclass
class WebSocketConfig:
	host: str = "127.0.0.1"
	port: int = 8001

class WebSocket:
	def __init__(self, config: WebSocketConfig):
		self.ws = WSServer(config.host, config.port)

		self.registered_events: dict[str, tuple[Handler, type[BaseModel]]] = {}
		self.validate_handler: Validator | None = None
		self.disconnect_event_name: str = None

		@self.ws.on("json")
		async def _on_message(websock, data):
			event_type = data.get("event")
			if not event_type:
				await self.ws.send_json(websock, { "event": "error", "reason": "Missing required field: event" })
				return

			entry = self.registered_events.get(event_type)
			if not entry:
				print(f'Received unknown event "{event_type}": {data}')
				return

			handler, schema = entry

			# Schema validation is non-negotiable
			payload, err = validate_schema(schema, data)
			if err:
				await self.ws.send_json(websock, { "event": "error", "reason": err })
				return

			# Optional user defined validation
			if self.validate_handler:
				ok, reason = self.validate_handler(websock, payload)
				if not ok:
					await self.ws.send_json(websock, { "event": "error", "reason": reason or "Validation failed" })
					return

			await handler(websock, payload)

		@self.ws.on("disconnect")
		async def _on_disconnect(websock, payload):
			if self.disconnect_event_name and self.disconnect_event_name in self.registered_events:
				handler, _ = self.registered_events.get(self.disconnect_event_name)
				await handler(websock, payload)

	async def start(self):
		await self.ws.start()

	async def stop(self):
		await self.ws.stop()

	def add_event(self, event_name: str, callback: Handler, schema: type[BaseModel]):
		self.registered_events[event_name] = (callback, schema)

	def set_validator(self, validator: Validator | None):
		self.validate_handler = validator

	# Use one of the events as a disconnect event
	def register_on_disconnect(self, event_name: str):
		self.disconnect_event_name = event_name