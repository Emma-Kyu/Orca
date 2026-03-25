import time

from dataclasses import dataclass

@dataclass
class Message:
	def __init__(self, data: dict):
		self.client_id       = data.get("client_id", "unknown")
		self.username     = data.get("username", "unknown")
		self.tag          = data.get("tag", "")
		self.message      = data.get("message", "")
		self.message_str  = None
		self.input_type   = data.get("input_type", "none")
		self.output  	  = data.get("output", True)
		self.timestamp    = data.get("timestamp", time.time())

	def post_process(self) -> str:
		if self.message_str:
			if self.tag:
				return f"{self.username} {self.tag}: {self.message_str}"
			return f"{self.username}: {self.message_str}"
		# audio messages need to be processed first
		return f"{self.username}:"

	def is_valid(self) -> bool:
		if self.input_type not in {"text", "audio", "none"}:
			return False
		if self.input_type == "none" and  not self.output:
			return False
		if self.input_type == "text" and not (isinstance(self.message, str) and self.message.strip()):
			return False
		if self.input_type == "audio" and not (isinstance(self.message, str) and self.message.strip()):
			return False
		return True