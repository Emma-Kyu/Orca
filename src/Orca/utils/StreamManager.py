import asyncio
import secrets

from .Events import ClientStreamMessageEvent
from .STT import STTHyperparameters

class StreamSession:
	def __init__(self, stream_id: int, ws, payload: dict):
		self.stream_id = stream_id
		self.ws = ws

		self.client_id = payload["client_id"]
		self.input_type = payload["input_type"]
		self.username = payload.get("username")
		self.tag = payload.get("tag")
		self.output = payload.get("output", True)

		self.sample_rate = payload["sample_rate"]
		self.channels = payload["channels"]
		self.format = payload["format"]
		self.language = payload.get("language", "en")

		self.stt_stream = None
		self.transcript_parts = []
		self.pending_audio = bytearray()

		self.rotating = False
		self.closed = False
		self.rotation_task = None

class StreamManager:
	def __init__(self, user_data, stt):
		self.user_data = user_data
		self.stt = stt
		self.streams: dict[int, StreamSession] = {}

	def _create_stream_id(self) -> int:
		while True:
			stream_id = secrets.randbits(32)
			if stream_id != 0 and stream_id not in self.streams:
				return stream_id

	async def _open_stt_stream(self, session: StreamSession):
		return await self.stt.open_stream(
			STTHyperparameters(language=session.language),
			on_commit=lambda event: self._on_commit(session, event),
			on_turn=lambda event: self._on_turn(session, event),
			on_final=lambda event: self._on_final(session, event),
			on_error=lambda event: self._on_error(session, event)
		)

	async def open_stream(self, ws, payload: dict) -> StreamSession:
		if payload["input_type"] != "audio":
			raise ValueError("Only audio input streams are currently supported.")
		if payload["sample_rate"] != 16000:
			raise ValueError("Only 16000 Hz input streams are currently supported.")
		if payload["channels"] != 1:
			raise ValueError("Only mono input streams are currently supported.")
		if payload["format"] != "pcm_s16le":
			raise ValueError("Only pcm_s16le input streams are currently supported.")
		client_matches_socket = any(
			client.client_id == payload["client_id"] and client.socket == ws
			for client in self.user_data.client_manager.clients.values()
		)
		if not client_matches_socket:
			raise ValueError("Unknown client_id.")

		session = StreamSession(self._create_stream_id(), ws, payload)
		session.stt_stream = await self._open_stt_stream(session)
		self.streams[session.stream_id] = session
		return session

	async def send_data(self, ws, stream_id: int, data: bytes):
		session = self.get_stream(stream_id)
		if session is None or session.ws != ws:
			raise ValueError("Unknown input stream.")
		if session.closed:
			raise ValueError("Input stream is closed.")
		if not data:
			return
		if len(data) % 2 != 0:
			raise ValueError("PCM16 payload has an invalid byte length.")

		if session.rotating or session.stt_stream is None:
			session.pending_audio.extend(data)
			return

		await session.stt_stream.send_audio(data)

	async def _finish_stream(self, session: StreamSession):
		if session.closed:
			return

		session.closed = True
		self.streams.pop(session.stream_id, None)
		session.transcript_parts.clear()
		session.pending_audio.clear()

		if session.rotation_task is not None and session.rotation_task != asyncio.current_task():
			try:
				await session.rotation_task
			except asyncio.CancelledError:
				pass
			except Exception:
				pass

		if session.stt_stream is not None:
			try:
				await session.stt_stream.cancel()
			except Exception:
				pass

	async def close_stream(self, ws, stream_id: int):
		session = self.get_stream(stream_id)
		if session is None or session.ws != ws:
			raise ValueError("Unknown input stream.")
		await self._finish_stream(session)

	async def cancel_stream(self, ws, stream_id: int):
		session = self.get_stream(stream_id)
		if session is None or session.ws != ws:
			raise ValueError("Unknown input stream.")
		await self._finish_stream(session)

	async def cancel_socket(self, ws):
		sessions = [session for session in self.streams.values() if session.ws == ws]
		for session in sessions:
			await self._finish_stream(session)

	async def cancel_all(self):
		for session in list(self.streams.values()):
			await self._finish_stream(session)

	def get_stream(self, stream_id: int) -> StreamSession | None:
		return self.streams.get(stream_id)

	def _on_commit(self, session: StreamSession, event: dict):
		if session.closed or session.rotating:
			return
		if session.stt_stream is None or event.get("stream_id") != session.stt_stream.stream_id:
			return

		text = event.get("text", "")
		if text:
			session.transcript_parts.append(text)

	def _on_turn(self, session: StreamSession, event: dict):
		if session.closed or session.rotating or not event.get("complete", False):
			return
		if session.stt_stream is None or event.get("stream_id") != session.stt_stream.stream_id:
			return

		session.rotating = True
		text = "".join(session.transcript_parts).strip()
		session.transcript_parts.clear()

		if text:
			self.user_data.event_bus.push_event(ClientStreamMessageEvent(session.ws, session, text))

		old_stream = session.stt_stream
		session.rotation_task = asyncio.create_task(self._rotate_stream(session, old_stream))

	async def _rotate_stream(self, session: StreamSession, old_stream):
		try:
			try:
				await old_stream.cancel()
			except Exception:
				pass

			if session.closed:
				return

			new_stream = await self._open_stt_stream(session)

			if session.closed:
				try:
					await new_stream.cancel()
				except Exception:
					pass
				return

			session.stt_stream = new_stream

			while session.pending_audio and not session.closed:
				pending = bytes(session.pending_audio)
				session.pending_audio.clear()
				await new_stream.send_audio(pending)

			session.rotating = False

		except Exception as e:
			session.rotating = False
			if not session.closed:
				await self.user_data.ws.ws.send_json(session.ws, {
					"event": "error",
					"stream_id": session.stream_id,
					"reason": f"Failed to rotate STT stream: {e}"
				})

	def _on_final(self, session: StreamSession, event: dict):
		if session.closed or session.rotating:
			return
		if session.stt_stream is None or event.get("stream_id") != session.stt_stream.stream_id:
			return

		text = event.get("text", "")
		if text:
			session.transcript_parts.append(text)

	def _on_error(self, session: StreamSession, event: dict):
		if session.closed:
			return
		print(f"STT stream {session.stream_id} failed: {event.get('message', 'Unknown error')}")
