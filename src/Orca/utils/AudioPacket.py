import json
import struct

MESSAGE_AUDIO = 0x01
MESSAGE_INPUT_STREAM_DATA = 0x02
AUDIO_HEADER = struct.Struct("!BI")
INPUT_STREAM_HEADER = struct.Struct("!BI")
MAX_METADATA_BYTES = 64 * 1024


def encode_audio_packet(metadata: dict, pcm: bytes) -> bytes:
	metadata_bytes = json.dumps(metadata, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

	if len(metadata_bytes) > MAX_METADATA_BYTES:
		raise ValueError("Audio metadata is too large.")

	return AUDIO_HEADER.pack(MESSAGE_AUDIO, len(metadata_bytes)) + metadata_bytes + pcm


def decode_audio_packet(data: bytes) -> tuple[dict, bytes]:
	if len(data) < AUDIO_HEADER.size:
		raise ValueError("Binary audio packet is too short.")

	message_type, metadata_size = AUDIO_HEADER.unpack_from(data)

	if message_type != MESSAGE_AUDIO:
		raise ValueError(f"Unknown binary message type: {message_type}")

	if metadata_size > MAX_METADATA_BYTES:
		raise ValueError("Audio metadata is too large.")

	metadata_start = AUDIO_HEADER.size
	metadata_end = metadata_start + metadata_size

	if metadata_end > len(data):
		raise ValueError("Binary audio packet has invalid metadata length.")

	try:
		metadata = json.loads(data[metadata_start:metadata_end].decode("utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError) as exc:
		raise ValueError("Binary audio packet metadata is invalid JSON.") from exc

	if not isinstance(metadata, dict):
		raise ValueError("Binary audio packet metadata must be an object.")

	return metadata, data[metadata_end:]


def encode_input_stream_packet(stream_id: int, payload: bytes) -> bytes:
	return INPUT_STREAM_HEADER.pack(MESSAGE_INPUT_STREAM_DATA, stream_id) + payload


def decode_input_stream_packet(data: bytes) -> tuple[int, bytes]:
	if len(data) < INPUT_STREAM_HEADER.size:
		raise ValueError("Binary input stream packet is too short.")

	message_type, stream_id = INPUT_STREAM_HEADER.unpack_from(data)

	if message_type != MESSAGE_INPUT_STREAM_DATA:
		raise ValueError(f"Unknown binary message type: {message_type}")

	return stream_id, data[INPUT_STREAM_HEADER.size:]
