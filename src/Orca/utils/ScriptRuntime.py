class ScriptRuntime:
	def __init__(self, app):
		self.app = app

	def emit(self, event):
		self.app.event_bus.push_event(event)

	@property
	def context(self):
		return self.app.context

	def register_function(self, client_name, func_name, fn, doc):
		self.app.function_registry.register_local_function(client_name, func_name, fn)