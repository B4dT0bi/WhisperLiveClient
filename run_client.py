import argparse

from loguru import logger

from whisper_live.transcription_client import TranscriptionClient


def main():
    parser = argparse.ArgumentParser(description="Run the Transcription Client.")
    parser.add_argument('--host', type=str, required=True, help="The hostname or IP address of the server.")
    parser.add_argument('--port', type=int, required=True, help="The port number to connect to on the server.")
    parser.add_argument('--pyaudio_input_device_id', type=int, default=None, help="The PyAudio input device ID.")
    parser.add_argument('--lang', type=str, default=None, help="The primary language for transcription.")
    parser.add_argument('--translate', action='store_true',
                        help="If set, the task will be translation instead of transcription.")
    parser.add_argument('--model', type=str, default="small", help="The whisper model to use (e.g., 'small', 'base').")
    parser.add_argument('--use_vad', action='store_true', help="Whether to enable voice activity detection.")
    parser.add_argument('--save_output_recording', action='store_true',
                        help="Whether to save the microphone recording.")
    parser.add_argument('--output_recording_filename', type=str, default="./output_recording.wav",
                        help="Path to save the output recording WAV file.")
    parser.add_argument('--output_transcription_path', type=str, default="./output.srt",
                        help="File path to save the output transcription (SRT file).")
    parser.add_argument('--log_transcription', action='store_true',
                        help="Whether to log transcription output to the console.")
    parser.add_argument('--max_clients', type=int, default=4, help="Maximum number of client connections allowed.")
    parser.add_argument('--max_connection_time', type=int, default=600,
                        help="Maximum allowed connection time in seconds.")
    parser.add_argument('--mute_audio_playback', action='store_true',
                        help="If set, mutes audio playback during file playback.")

    args = parser.parse_args()

    transcription_client = TranscriptionClient(
        host=args.host,
        port=args.port,
        lang=args.lang,
        translate=args.translate,
        model=args.model,
        use_vad=args.use_vad,
        save_output_recording=args.save_output_recording,
        output_recording_filename=args.output_recording_filename,
        output_transcription_path=args.output_transcription_path,
        log_transcription=args.log_transcription,
        max_clients=args.max_clients,
        max_connection_time=args.max_connection_time,
        mute_audio_playback=args.mute_audio_playback,
        pyaudio_input_device_id=args.pyaudio_input_device_id
    )
    transcription_client.register_callback("process_segments", my_segment_callback)
    transcription_client()


def my_segment_callback(segments):
    logger.info(f"Received segments:{segments}")


if __name__ == "__main__":
    main()
