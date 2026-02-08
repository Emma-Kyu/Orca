import asyncio, traceback

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Event(ABC):
	@abstractmethod
	async def process(self, user_data):
		...

@dataclass
class EventBusConfig:
	user_data: object | None = None

class EventBus:
	def __init__(self, config: EventBusConfig):
		self.event_queue = asyncio.Queue()
		self.user_data = config.user_data

	async def process_queue(self):
		event: Event = await self.event_queue.get()
		try:
			await event.process(self.user_data)
		except Exception as e:
			print(f"Error while processing {event}: {e}")
			traceback.print_exc()
		finally:
			self.event_queue.task_done()