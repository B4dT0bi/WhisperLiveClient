from whisper_live.client import Client
from whisper_live.transcription_tee_client import TranscriptionTeeClient


# Copied from https://github.com/B4dT0bi/WhisperLive/blob/main/whisper_live/transcription_client.py

class TranscriptionClient(TranscriptionTeeClient):
    """
    Client for handling audio transcription tasks via a single WebSocket connection.

    Acts as a high-level client for audio transcription tasks using a WebSocket connection. It can be used
    to send audio data for transcription to a server and receive transcribed text segments.

    Args:
        host (str): The hostname or IP address of the server.
        port (int): The port number to connect to on the server.
        lang (str, optional): The primary language for transcription. Default is None, which defaults to English ('en').
        translate (bool, optional): If True, the task will be translation instead of transcription. Default is False.
        model (str, optional): The whisper model to use (e.g., "small", "base"). Default is "small".
        use_vad (bool, optional): Whether to enable voice activity detection. Default is True.
        save_output_recording (bool, optional): Whether to save the microphone recording. Default is False.
        output_recording_filename (str, optional): Path to save the output recording WAV file. Default is "./output_recording.wav".
        output_transcription_path (str, optional): File path to save the output transcription (SRT file). Default is "./output.srt".
        log_transcription (bool, optional): Whether to log transcription output to the console. Default is True.
        max_clients (int, optional): Maximum number of client connections allowed. Default is 4.
        max_connection_time (int, optional): Maximum allowed connection time in seconds. Default is 600.
        mute_audio_playback (bool, optional): If True, mutes audio playback during file playback. Default is False.

    Attributes:
        client (Client): An instance of the underlying Client class responsible for handling the WebSocket connection.

    Example:
        To create a TranscriptionClient and start transcription on microphone audio:
        ```python
        transcription_client = TranscriptionClient(host="localhost", port=9090)
        transcription_client()
        ```
    """

    def __init__(
            self,
            host,
            port,
            lang=None,
            translate=False,
            model="small",
            use_vad=True,
            save_output_recording=False,
            output_recording_filename="./output_recording.wav",
            output_transcription_path="./output.srt",
            log_transcription=True,
            max_clients=4,
            max_connection_time=600,
            mute_audio_playback=False,
            pyaudio_input_device_id=None
    ):
        self.client = Client(
            host, port, lang, translate, model, srt_file_path=output_transcription_path,
            use_vad=use_vad, log_transcription=log_transcription, max_clients=max_clients,
            max_connection_time=max_connection_time
        )

        if save_output_recording and not output_recording_filename.endswith(".wav"):
            raise ValueError(f"Please provide a valid `output_recording_filename`: {output_recording_filename}")
        if not output_transcription_path.endswith(".srt"):
            raise ValueError(
                f"Please provide a valid `output_transcription_path`: {output_transcription_path}. The file extension should be `.srt`.")
        TranscriptionTeeClient.__init__(
            self,
            [self.client],
            save_output_recording=save_output_recording,
            output_recording_filename=output_recording_filename,
            mute_audio_playback=mute_audio_playback,
            pyaudio_input_device_id=pyaudio_input_device_id
        )
