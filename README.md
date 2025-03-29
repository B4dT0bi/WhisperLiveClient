
# whisper-live-client

A lightweight Python client for [WhisperLive](https://github.com/collabora/WhisperLive),  
designed for client-only use cases with significantly fewer dependencies than the official server library.

## ✨ Features

- Sends PCM audio to a WhisperLive WebSocket endpoint
- Real-time transcription support with simple callback interface
- Fewer dependencies – ideal for minimal environments or custom frontends
- Focused on client-side use (no server components or protobufs)

## 🚀 Installation

```bash
pip install whisper-live-client
```

_or install from source:_

```bash
git clone https://github.com/youruser/whisper-live-client
cd whisper-live-client
pip install .
```

## 📦 Usage

```python
from whisper_live_client import WhisperLiveClient

def on_transcript(text, is_final):
    print("Transcript:", text, "(final)" if is_final else "(interim)")

client = WhisperLiveClient(
    url="ws://localhost:8080/ws/transcribe",
    on_transcript=on_transcript
)

# Send a frame of PCM audio (float32 array, 16 kHz, mono)
client.send_pcm_frame(my_pcm_frame)

# Close the connection when done
client.close()
```

## 🎧 Audio Format

- PCM float32
- Sample rate: 16000 Hz
- Channels: mono
- Frame size: typically 20–50 ms (e.g. 320–800 samples)

You are responsible for capturing and formatting the audio input accordingly.

## 🛠 Dependencies

This library uses only a minimal set of runtime dependencies:

- `websockets` – WebSocket client
- `numpy` – for handling audio data

Optional (for examples):

- `sounddevice` or `pyaudio` – audio capture in demos

This is in contrast to the official WhisperLive server code, which depends on `aiohttp`, `protobuf`, and other server-related tools.

## 📁 Project Structure

```text
whisper_live_client/
 ├── __init__.py
 └── client.py          # Core client logic
examples/
 └── record_and_send.py # Optional example using sounddevice
```

## 📜 License

MIT License

---

> **Disclaimer:** This is an independent client library and is not affiliated with Collabora or OpenAI.
