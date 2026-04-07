import re
import asyncio
import uuid

from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field

from .EventBus import Event
from .Message import Message
from .Metrics import Metrics, Unit
from .LLM import LLMHyperparameters
from .STT import STTHyperparameters
from .StreamOutputHandler import StreamOutputHandler
from .StreamingDelimiterParser import DelimiterRule, StreamingDelimiterParser

THINKING_STATE = "THINKING"
FUNCTION_STATE = "FUNCTION"
DELIMITERS = [
	DelimiterRule(FUNCTION_STATE, "`", "`"),
	DelimiterRule(THINKING_STATE, "<thinking>", "<thinking>")
]
CONTROL_FLOW = "__NO_RETURN__"

def normalise(text) -> str:
	replacements = {
		'“': '"',
		'”': '"',
		'‘': "'",
		'’': "'",
		'…': '...',
	}
	for old, new in replacements.items():
		text = text.replace(old, new)
	return text

def preprocess_transcription(text: str) -> str:
	text = re.sub(r"^\s*-\s*", "", text)
	text = re.sub(r'\[.*?\]|\(.*?\)|\*.*?\*', '', text)
	return text.strip()

def format_functions(funcs):
	return f"\n - {'\n - '.join(funcs)}" if funcs else ""

class Schema_BaseEvent(BaseModel):
	event: str

class Schema_ConnectEvent(Schema_BaseEvent):
	event: Literal["connect"]
	client: str
	modalities: list[str] = Field(default_factory=list)
	functions: list[str] = Field(default_factory=list)

class Schema_DisconnectEvent(Schema_BaseEvent):
	event: Literal["disconnect"]

class Schema_MessageEvent(Schema_BaseEvent):
	event: Literal["message"]
	client_id: str
	input_type: Literal["text", "audio", "none"]
	output: bool
	username: str | None
	tag: str | None
	message: str | None

class Schema_FunctionResultEvent(Schema_BaseEvent):
	event: Literal["function"]
	client_id: str
	function_id: str
	result: str

# Runs on client connection
class ClientConnectEvent(Event):
	def __init__(self, ws, payload):
		self.ws = ws
		self.payload = payload

	async def process(self, user_data):
		client_id = user_data.client_manager.connect(self.payload, self.ws)
		user_data.function_registry.register_client(self.payload["client"], self.payload["functions"])

		# Send the ack message
		await user_data.ws.ws.send_json(self.ws, {"event": "connect_ack", "client_id": client_id})


# Runs on client disconnection
class ClientDisconnectEvent(Event):
	def __init__(self, ws):
		self.ws = ws

	async def process(self, user_data):
		client_name = user_data.client_manager.disconnect_socket(self.ws)
		if client_name:
			user_data.function_registry.remove_client(client_name)
			user_data.event_bus.push_event(RebuildPromptEvent())

# Runs a rebuild prompt event, Includes compaction logic
class RebuildPromptEvent(Event):
	def __init__(self):
		pass

	async def process(self, user_data):
		now = datetime.now()
		user_data.system_prompt_replacements = {
			"<date>": now.strftime("%Y-%m-%d"),
			"<time>": now.strftime("%I:%M %p"),
			"<functions>": format_functions(user_data.function_registry.get_all_functions())
		}
		user_data.context.update_system_prompt_replacements(user_data.system_prompt_replacements)

# A message injected by a client, only previleged clients can send system messages
class MessageInjectEvent(Event):
	def __init__(self):
		pass

	async def process(self, user_data):
		pass

# Runs on client sending a message
class ClientMessageEvent(Event):
	def __init__(self, ws, payload):
		self.ws = ws
		self.message = Message(payload)

	async def process(self, user_data):
		msg = self.message
		# validate
		if not msg.is_valid():
			await user_data.ws.ws.send_json(self.ws, {"event": "error", "reason": "Message is invalid. Message may be missing fields"})
			return

		metrics = Metrics()

		# Decode the message
		if msg.input_type == "audio":
			with metrics.time("decode", Unit.MILLISECONDS):
				msg.message_str = user_data.stt.transcribe(STTHyperparameters(), msg.message)
		else:
			msg.message_str = msg.message or ""

		# Pre processing
		if msg.input_type != "none":
			msg.message_str = normalise(msg.message_str.strip())
			msg.message_str = preprocess_transcription(msg.message_str)

		# Nothing to reply to
		if not msg.message_str and msg.input_type != "none":
			return

		# Get the post processed form to send to context
		post_processed = msg.post_process()
		
		if msg.input_type != "none":
			user_data.context.push_user(post_processed)

		print(f"[{user_data.client_manager.get_client_name_from_id(msg.client_id)}] {post_processed if msg.input_type != 'none' else 'spontaneous generation'}")

		if msg.output:
			user_data.event_bus.push_event(GenerationEvent(metrics))
		else:
			user_data.context.push_assistant("<silence>")

# A function return event that needs to be processed
class FunctionReturnEvent(Event):
	def __init__(self, payload):
		self.payload = payload

	async def process(self, user_data):
		client = self.payload["client"]
		function = self.payload["function"]
		function_id = self.payload["function_id"]
		result = self.payload["result"]

		output = f"{client}:{function}: {result}"

		if result is not None:
			print(output)
			user_data.context.push_system(output)

		resolved = user_data.barriers.resolve(function_id)

		if resolved:
			metrics = Metrics()
			user_data.event_bus.push_event(GenerationEvent(metrics))

# Spontaneous generation events caused by wait timers
class SpontaneousGenerationEvent(Event):
	def __init__(self):
		pass

	async def process(self, user_data):
		metrics = Metrics()
		user_data.event_bus.push_event(GenerationEvent(metrics))

# Start a generation with whatever context we have atm
class GenerationEvent(Event):
	def __init__(self, metrics):
		# Piggy back off the old metrics
		self.metrics = metrics

	async def process(self, user_data):
		print(f"{user_data.config['name']}: ", end="")

		self.metrics.start_timer("ttft")

		generation_id = f"gid-{uuid.uuid4().hex[:12]}"

		handler = StreamOutputHandler(generation_id, user_data.ws, user_data.tts, user_data.client_manager.get_client_modalities())
		parser = StreamingDelimiterParser(DELIMITERS)

		response = user_data.llm.send_generation_request(user_data.context.prompt(),
			LLMHyperparameters(
				temperature=1.0,
				min_p=0.05,
				top_k=64,
				presence_penalty=0.1,
				repetition_penalty=1.1,
				repeat_last_n=512,

				# XTC
				xtc_threshold=0.05,
				xtc_probability=0.1,

				# DRY sampling
				dry_multiplier=3.0,
				dry_base=1.75,
				dry_allowed_length=3,
				dry_penalty_last_n=-1,
				dry_sequence_breakers=[ '\n', ':', '"', '*', '<', '>', "<silence>", "`" ],

				# Misc
				n_predict=512,
				logit_bias=[
					# Encourage shorter responses
					[ 128009, 0.1 ],
					# discourage semicolons but still allow for function calls
					[ ":", -1.0 ],
					# Discourage her from expressing so much and causing mood swings
					[ "express", -1.0 ],
					# Discourage excessive memorising
					[ "memorise", -2.0 ],
					# encourage recall 
					[ "recall", 1.0 ],
					# Encourage function calls
					[ "`", 1.0 ]
				],
				samplers=[ "penalties", "top_k", "min_p", "xtc", "temperature" ]
			)
		)

		function_ids = set()
		has_control = False

		accumulated_response = []
		function_buffer = []
		thinking_buffer = []

		for token in user_data.llm.get_streaming_response(response):
			if token is None:
				continue

			accumulated_response.append(token)
			segments = parser.feed(token)

			for event, value, state in segments:
				if event == "EXIT":
					if value == FUNCTION_STATE:
						function_calls = "".join(function_buffer)
						function_buffer = []

						parsed_calls = user_data.function_registry.parse_calls(function_calls)

						for call in parsed_calls:
							if not call["async"]:
								function_ids.add(call["function_id"])

							function_handle = user_data.function_registry.get_handler(f"{call["client"]}:{call["function"]}")

							if function_handle:
								if asyncio.iscoroutinefunction(function_handle):
									result = await function_handle(**call["args"])
								else:
									result = function_handle(**call["args"])

								if result is CONTROL_FLOW:
									has_control = True
									continue

								user_data.event_bus.push_event(FunctionReturnEvent({
									"client": call["client"],
									"function": call["function"],
									"function_id": call["function_id"],
									"result": result
								}))
							elif user_data.client_manager.is_client_connected(call["client"]):
								socket = user_data.client_manager.get_socket(call["client"])
								if socket:
									await socket.send_json({
										"type": "function_call",
										"function_id": call["function_id"],
										"client": call["client"],
										"function": call["function"],
										"args": call["args"],
									})
									if not call["return"]:
										user_data.event_bus.push_event(FunctionReturnEvent({
											"client": call["client"],
											"function": call["function"],
											"function_id": call["function_id"],
											"result": None
										}))
							else:
								user_data.event_bus.push_event(FunctionReturnEvent({
									"client": call["client"],
									"function": "error",
									"function_id": call["function_id"],
									"result": f"Invalid function call: {function_calls}",
								}))
					elif value == THINKING_STATE:
						thinking_trace = "".join(thinking_buffer)
						thinking_buffer = []
				elif event == "CHUNK":
					if state == "TEXT":
						await handler.handle_token(value)
					elif state == FUNCTION_STATE:
						function_buffer.append(value)
					elif state == THINKING_STATE:
						thinking_buffer.append(value)
			print(token, end='', flush=(len(accumulated_response) % 5 == 0))

		if not has_control and len(function_ids) > 0:
			user_data.barriers.create_barrier(generation_id, function_ids)
			asyncio.create_task(self._timeout_generation(user_data, generation_id, 1.0))

		# Finish the response
		await handler.finalize()
		await handler.send_finish_token()
		print("")
		if len(accumulated_response) > 0:
			user_data.context.push_assistant("".join(accumulated_response))

	async def _timeout_generation(self, user_data, gid, timeout):
		await asyncio.sleep(timeout)

		remaining = user_data.barriers.get_outstanding(gid)
		if not remaining:
			return

		# inject timeout messages
		for fid in remaining:
			user_data.context.push_system(f"{fid}: Function return timed out.")

		user_data.barriers.clear_barrier(gid)

		user_data.event_bus.push_event(GenerationEvent(Metrics()))