# Orca
An AI orchestrator, primarily designed for Emma, but can work with other configurations

# Setup
Note the parameters are optimised for CUDA and 1x3090. Your config may differ

## Env File
The Env has the following fields.
Those labeled "(default)" are optional and defaults will automatically be used
```
# Hosting addresses
HOST_ADDRESS=127.0.0.1

# Connectivity
WEBSOCKET_PORT=49170 (default)

# Internals
LLM_PORT=15324 (default)
STT_PORT=15325 (default)

# Logs
SUBPROCESS_LOG_DIR=./logs/subprocesses
CONVERSATION_LOG_DIR=./logs/conversations
TTS_LOG_DIR=./logs/tts-output
STT_LOG_DIR=./logs/stt-output
```

# Technologies used
## LLM Serving
## STT Transcription
## TTS generation

