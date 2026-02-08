from .EventBus import Event

# Runs on client connection
class ClientConnectEvent(Event):
	def __init__(self):
		pass

	async def process(self, user_data):
		pass

# Runs on client disconnection
class ClientDisconnectEvent(Event):
	def __init__(self):
		pass

	async def process(self, user_data):
		pass

# Runs a rebuild prompt event, Includes compaction logic
class RebuildPromptEvent(Event):
	def __init__(self):
		pass

	async def process(self, user_data):
		pass

# A message injected by a client, only previleged clients can send system messages
class MessageInjectEvent(Event):
	def __init__(self):
		pass

	async def process(self, user_data):
		pass

# Runs on client sending a message
class ClientMessageEvent(Event):
	def __init__(self):
		pass

	async def process(self, user_data):
		pass

# A function return event that needs to be processed
class FunctionReturnEvent(Event):
	def __init__(self):
		pass

	async def process(self, user_data):
		pass

# Spontaneous generation events caused by wait timers
class SpontaneousGenerationEvent(Event):
	def __init__(self):
		pass

	async def process(self, user_data):
		pass