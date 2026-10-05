import io
import wave
import asyncio
import inspect
import struct
import uuid
import requests

from dataclasses import dataclass
from pathlib import Path

from .WebSocketCommon import WSClient
from .start_subprocess import start_subprocess

MESSAGE_AUDIO = 0x01
AUDIO_HEADER = struct.Struct("!BI")

@dataclass
class STTHyperparameters:
	language: str = "en"

	@classmethod
	def from_dict(cls, config: dict):
		hp = config.get("hyperparameters", {})

		return cls(
			language = hp.get("language", config.get("language", "en"))
		)

@dataclass
class STTClientConfig:
	# Executable location
	backend_location: str = "./vendor/bin/StreamingSTT"

	# Connectivity
	host: str = "127.0.0.1"
	port: int = 8001
	endpoint: str = "/v1/audio/transcriptions"
	stream_endpoint: str = "/v1/audio/streams"

	# Models
	model: str = ""
	mmproj: str = ""
	vad: str = ""
	smart_turn: str = ""

	# Runtime
	gpu_layers: int = 999
	smart_turn_threads: int = 1
	smart_turn_threshold: float = 0.2
	smart_turn_silence_ms: int = 50
	smart_turn_force_end_ms: int = 1500

	log_dir: str = "./"

class STTStream:
	def __init__(self, client, stream_id: int, on_commit=None, on_turn=None, on_final=None, on_error=None):
		self.client = client
		self.stream_id = stream_id

		self.on_commit = on_commit
		self.on_turn = on_turn
		self.on_final = on_final
		self.on_error = on_error

		self.closed = False
		self._done = asyncio.get_running_loop().create_future()

	def _emit(self, callback, event):
		if callback is None:
			return

		try:
			result = callback(event)
			if inspect.isawaitable(result):
				asyncio.create_task(result)
		except Exception as e:
			print(f"STT stream callback failed: {e}")

	def _handle_commit(self, event):
		self._emit(self.on_commit, event)

	def _handle_turn(self, event):
		self._emit(self.on_turn, event)

	def _handle_final(self, event):
		self.closed = True
		self._emit(self.on_final, event)
		if not self._done.done():
			self._done.set_result(event)

	def _handle_cancelled(self, event):
		self.closed = True
		if not self._done.done():
			self._done.set_result(event)

	def _handle_error(self, event):
		self._emit(self.on_error, event)

	async def send_audio(self, audio: bytes):
		if self.closed:
			return
		if not audio:
			return

		packet = AUDIO_HEADER.pack(MESSAGE_AUDIO, self.stream_id) + audio
		await self.client.ws.send_binary(packet)

	async def end(self):
		if self.closed:
			return

		await self.client.ws.send_json({
			"type": "end",
			"stream_id": self.stream_id
		})
		await self._done

	async def cancel(self):
		if self.closed:
			return

		await self.client.ws.send_json({
			"type": "cancel",
			"stream_id": self.stream_id
		})
		self.closed = True
		self.client.streams.pop(self.stream_id, None)
		if not self._done.done():
			self._done.set_result(None)

class STTClient:
	def __init__(self, config: STTClientConfig):
		self.endpoint = f"http://{config.host}:{config.port}{config.endpoint}"
		self.stream_endpoint = f"ws://{config.host}:{config.port}{config.stream_endpoint}"
		self.session = requests.Session()
		self.ws = WSClient(self.stream_endpoint)

		self.sample_rate = 16000
		self.channels = 1
		self.sample_width = 2
		self.audio_format = "pcm_s16le"

		self.streams: dict[int, STTStream] = {}
		self.pending_streams: dict[str, asyncio.Future] = {}

		@self.ws.on("json")
		async def _on_json(data):
			self._handle_stream_event(data)

		@self.ws.on("disconnect")
		async def _on_disconnect(_):
			error = ConnectionError("StreamingSTT WebSocket disconnected.")

			for request in list(self.pending_streams.values()):
				if not request.done():
					request.set_exception(error)
			self.pending_streams.clear()

			for stream in list(self.streams.values()):
				stream._handle_error({
					"type": "error",
					"stream_id": stream.stream_id,
					"message": str(error)
				})
				stream.closed = True
				if not stream._done.done():
					stream._done.set_exception(error)
			self.streams.clear()

		cmd = [
			f"{config.backend_location}\\StreamingSTT",
			"--model", str(config.model),
			"--mmproj", str(config.mmproj),
			"--vad", str(config.vad),
			"--host", config.host,
			"--port", str(config.port),
			"--n-gpu-layers", str(config.gpu_layers)
		]

		if config.smart_turn:
			cmd += [
				"--smart-turn", str(config.smart_turn),
				"--smart-turn-threads", str(config.smart_turn_threads),
				"--smart-turn-threshold", str(config.smart_turn_threshold),
				"--smart-turn-silence-ms", str(config.smart_turn_silence_ms),
				"--smart-turn-force-end-ms", str(config.smart_turn_force_end_ms)
			]

		self.process = start_subprocess(cmd, config.log_dir)

		print(f"STT server running at: {self.endpoint}")

	async def start(self):
		await self.ws.connect()

	async def aclose(self):
		await self.ws.close()

	def close(self):
		self.session.close()

		if self.process.poll() is None:
			self.process.terminate()
			self.process.wait()

	def _handle_stream_event(self, data: dict):
		event_type = data.get("type")

		if event_type == "started":
			request_id = data.get("request_id")
			request = self.pending_streams.pop(request_id, None)
			if request is not None and not request.done():
				request.set_result(int(data["stream_id"]))
			return

		if event_type == "error" and data.get("request_id") is not None:
			request_id = data.get("request_id")
			request = self.pending_streams.pop(request_id, None)
			if request is not None and not request.done():
				request.set_exception(RuntimeError(data.get("message", "StreamingSTT stream failed.")))
			return

		stream_id = data.get("stream_id")
		if stream_id is None:
			return

		stream = self.streams.get(int(stream_id))
		if stream is None:
			return

		if event_type == "commit":
			stream._handle_commit(data)
		elif event_type == "turn":
			stream._handle_turn(data)
		elif event_type == "final":
			self.streams.pop(stream.stream_id, None)
			stream._handle_final(data)
		elif event_type == "cancelled":
			self.streams.pop(stream.stream_id, None)
			stream._handle_cancelled(data)
		elif event_type == "error":
			stream._handle_error(data)

	async def open_stream(self, hyperparameters: STTHyperparameters | None = None, on_commit=None, on_turn=None, on_final=None, on_error=None) -> STTStream:
		await self.start()

		hyperparameters = hyperparameters or STTHyperparameters()
		request_id = f"req-{uuid.uuid4().hex[:12]}"
		request = asyncio.get_running_loop().create_future()
		self.pending_streams[request_id] = request

		try:
			await self.ws.send_json({
				"type": "start",
				"request_id": request_id,
				"sample_rate": self.sample_rate,
				"channels": self.channels,
				"format": self.audio_format,
				"language": hyperparameters.language
			})
			stream_id = await request
		except Exception:
			self.pending_streams.pop(request_id, None)
			raise

		stream = STTStream(
			self,
			stream_id,
			on_commit=on_commit,
			on_turn=on_turn,
			on_final=on_final,
			on_error=on_error
		)
		self.streams[stream_id] = stream
		return stream

	def _pcm_to_wav(self, audio: bytes) -> bytes:
		buffer = io.BytesIO()

		with wave.open(buffer, "wb") as wav:
			wav.setnchannels(self.channels)
			wav.setsampwidth(self.sample_width)
			wav.setframerate(self.sample_rate)
			wav.writeframes(audio)

		return buffer.getvalue()

	def transcribe(self, hyperparameters: STTHyperparameters, audio: bytes) -> str:
		if not audio:
			return ""
		wav = self._pcm_to_wav(audio)
		response = self.session.post(
			self.endpoint,
			files = { "file": ("audio.wav", wav, "audio/wav") },
			data = { "language": hyperparameters.language }
		)
		response.raise_for_status()
		return response.json().get("text", "").strip()
