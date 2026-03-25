class ScriptClient:
	def __init__(self, runtime):
		self.runtime = runtime
		self.name: str
		self._docs: list[str] = []

	def function(self, doc: str):
		def decorator(fn):
			if not self.name:
				raise ValueError("Client name must be set before registering functions")

			func_name = fn.__name__

			self._docs.append(doc)

			self.runtime.register_function(self.name, func_name, fn, doc)

			return fn
		return decorator