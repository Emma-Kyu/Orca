import asyncio
import base64
import numpy as np

def float32_to_pcm16(audio_f32: np.ndarray) -> np.ndarray:
	audio_clipped = np.clip(audio_f32, -1.0, 1.0)
	return (audio_clipped * 32767.0).astype(np.int16)

def audio_to_base64(pcm16: np.ndarray) -> str:
	return base64.b64encode(pcm16.tobytes()).decode()

class StreamOutputHandler:
	def __init__(self, ws, tts, client_modalities: dict[str, list]):
		self.ws = ws
		self.tts = tts
		self.buffer = ""
		self.pending = None
		self.loop = asyncio.get_running_loop()
		self.sentence_endings = (".", "!", "?", ";", ":")

		self.speech_length = 0

		# Recording disabled
		# self.recording_pcm16 = []
		# self.recording_transcript = ""

		self.text_sockets = client_modalities.get("text", [])
		self.audio_sockets = client_modalities.get("audio", [])

	async def handle_token(self, token: str):
		if self.text_sockets:
			await self._handle_text(token)
		# Audio stream only if needed
		if self.audio_sockets:
			await self._handle_audio(token)

	async def _handle_text(self, token: str):
		await self.ws.ws.broadcast_json_to(self.text_sockets, { "event": "generation", "token_type": "text", "token": token, "finished": False })

	async def _handle_audio(self, token: str):
		self.buffer += token
		# Recording disabled
		# self.recording_transcript += token

		if self.buffer.endswith(self.sentence_endings):
			if self.pending:
				await self.pending
			self.pending = asyncio.create_task(self._flush_audio(self.buffer.strip()))
			self.buffer = ""

	async def _flush_audio(self, text: str):
		if not text or not self.audio_sockets:
			return

		chunks = await self.loop.run_in_executor(None, self.tts.text_to_audio, text)

		for pcm in chunks:
			if pcm.size == 0:
				continue

			self.speech_length += pcm.size / self.tts.sample_rate

			pcm16 = float32_to_pcm16(pcm)

			audio_b64 = await self.loop.run_in_executor(None, audio_to_base64, pcm16)
			await self.ws.ws.broadcast_json_to(self.audio_sockets, { "event": "generation", "token_type": "audio", "token": audio_b64, "text": text, "finished": False })

			# Recording disabled
			# self.recording_pcm16.append(pcm16)

	async def finalize(self):
		if self.pending:
			await self.pending

		if self.buffer.strip():
			await self._flush_audio(self.buffer.strip())

		# Recording disabled
		# if self.recording_pcm16:
		# 	full_pcm = np.concatenate(self.recording_pcm16).tobytes()
		# 	transcript = self.recording_transcript.strip()
		# 	await self.loop.run_in_executor(None, lambda: self.tts_audio_index.write(full_pcm, self.tts.sample_rate, transcript))

	async def send_finish_token(self):
		if self.text_sockets:
			await self.ws.ws.broadcast_json_to(self.text_sockets, { "event": "generation", "token_type": "text", "token": "", "finished": True })

		if self.audio_sockets:
			await self.ws.ws.broadcast_json_to(self.audio_sockets, { "event": "generation", "token_type": "audio", "token": "", "finished": True })