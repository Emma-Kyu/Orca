def _build_prompt(prompt: str, replacements: dict) -> str:
	for key, value in replacements.items():
		prompt = prompt.replace(key, value)
	return prompt

class Context:
	def __init__(self, system_prompt: str, replacements: dict[str, str] = {}):
		self.raw_system_prompt = system_prompt
		self.messages = []

		if self.raw_system_prompt:
			self.add_message("system", _build_prompt(self.raw_system_prompt, replacements))

	def update_system_prompt_replacements(self, replacements: dict[str, str]):
		# Ensure the system prompt exists, it's in context and the first message is a system prompt
		if self.raw_system_prompt and len(self.messages) >= 1 and self.messages[0]["role"] == "system":
			self.messages[0]["content"] = _build_prompt(self.raw_system_prompt, replacements)


	def add_message(self, role: str, message: str):
		self.messages.append({"role": role, "content": message})

	def push_user(self, message: str):
		self.add_message("user", message)

	def push_assistant(self, message: str):
		self.add_message("assistant", message)

	def push_system(self, message: str):
		self.add_message("system", message)

	def prompt(self) -> list[dict]:
		return self.messages

	def length(self) -> int:
		# Includes system prompt
		return len(self.messages)

	def reset(self):
		self.messages = [ self.messages[0] ]

	def get(self, index: int):
		""" Get a specific message """
		return self.messages[index]

	def slice(start: int, end: int) -> list[dict[str, str]]:
		""" Slice a part of the prompt, while also preserving the system prompt """
		if start <= 1:
			start = 1
		out = [ self.messages[0] ]
		out.append(self.messages[start:end])
		return out