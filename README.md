
# whisper-live-client

A lightweight Python client for [WhisperLive](https://github.com/collabora/WhisperLive),  
designed for client-only use cases with significantly fewer dependencies than the official server library.

## Features

- Sends PCM audio to a WhisperLive WebSocket endpoint
- Real-time transcription support with simple callback interface
- Fewer dependencies – ideal for minimal environments or custom frontends
- Focused on client-side use

## Installation

```bash
pip install whisper-live-client
```

_or install from source:_

```bash
git clone https://github.com/B4dT0bi/whisper-live-client
cd whisper-live-client
pip install .
```

## Usage

```python
from whisper_live.transcription_client import TranscriptionClient

def my_segment_callback(segments):
    print(f"Received segments:{segments}")

    transcription_client = TranscriptionClient(
        host="localhost",         # or your server address
        port=9090,                # or your server port
        lang="en",                # or your desired language
        model="small",            # or your desired model
        use_vad=True,             # use voice activity detection
        pyaudio_input_device_id=1 # optional: specify input device ID for PyAudio
    )
    transcription_client.register_callback("process_segments", my_segment_callback) # register callback
    transcription_client() # start the client
```

## Dependencies

This library uses only a minimal set of runtime dependencies:

- `websockets` – WebSocket client
- `numpy` – for handling audio data

Optional (for examples):

- `pyaudio` – audio capture in demos

This is in contrast to the official WhisperLive server code, which depends on heavy libs like `torch`.

## 📜 License

MIT License

---

> **Disclaimer:** This is an independent client library and is not affiliated with Collabora or OpenAI.
