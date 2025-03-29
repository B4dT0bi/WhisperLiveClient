import os
import shutil
import threading
import wave
import time
import av

import pyaudio
import numpy as np

from whisper_live import utils
from whisper_live.client import Client
from loguru import logger


# Copied from https://github.com/B4dT0bi/WhisperLive/blob/main/whisper_live/transcription_tee_client.py

class TranscriptionTeeClient:
    """
    Client for handling audio recording, streaming, and transcription tasks via one or more
    WebSocket connections.

    Acts as a high-level client for audio transcription tasks using a WebSocket connection. It can be used
    to send audio data for transcription to one or more servers, and receive transcribed text segments.
    Args:
        clients (list): one or more previously initialized Client instances

    Attributes:
        clients (list): the underlying Client instances responsible for handling WebSocket connections.
    """

    def __init__(self, clients, save_output_recording=False, output_recording_filename="./output_recording.wav",
                 mute_audio_playback=False, pyaudio_input_device_id=None):
        self.clients = clients
        if not self.clients:
            raise Exception("At least one client is required.")
        self.chunk = 4096
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.record_seconds = 60000
        self.save_output_recording = save_output_recording
        self.output_recording_filename = output_recording_filename
        self.mute_audio_playback = mute_audio_playback
        self.frames = b""
        self.p = pyaudio.PyAudio()
        try:
            self.stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
                input_device_index=pyaudio_input_device_id
            )
        except OSError as error:
            logger.warning(f"Unable to access microphone. {error}")
            self.stream = None

    def __call__(self, audio=None, rtsp_url=None, hls_url=None, save_file=None):
        """
        Start the transcription process.

        Initiates the transcription process by connecting to the server via a WebSocket. It waits for the server
        to be ready to receive audio data and then sends audio for transcription. If an audio file is provided, it
        will be played and streamed to the server; otherwise, it will perform live recording.

        Args:
            audio (str, optional): Path to an audio file for transcription. Default is None, which triggers live recording.

        """
        assert sum(
            source is not None for source in [audio, rtsp_url, hls_url]
        ) <= 1, 'You must provide only one selected source'

        self.wait_for_server_ready()

        if hls_url is not None:
            self.process_hls_stream(hls_url, save_file)
        elif audio is not None:
            resampled_file = utils.resample(audio)
            self.play_file(resampled_file)
        elif rtsp_url is not None:
            self.process_rtsp_stream(rtsp_url)
        else:
            self.record()

    def register_callback(self, event_name, callback):
        for client in self.clients:
            client.register_callback(event_name, callback)

    def wait_for_server_ready(self):
        """
        Wait for the server to be ready to receive audio data.
        """
        logger.info("Waiting for server ready ...")
        for client in self.clients:
            while not client.recording:
                if client.waiting or client.server_error:
                    self.close_all_clients()
                    return

        logger.info("Server Ready!")

    def close_all_clients(self):
        """Closes all client websockets."""
        for client in self.clients:
            client.close_websocket()

    def write_all_clients_srt(self):
        """Writes out .srt files for all clients."""
        for client in self.clients:
            client.write_srt_file(client.srt_file_path)

    def multicast_packet(self, packet, unconditional=False):
        """
        Sends an identical packet via all clients.

        Args:
            packet (bytes): The audio data packet in bytes to be sent.
            unconditional (bool, optional): If true, send regardless of whether clients are recording.  Default is False.
        """
        for client in self.clients:
            if (unconditional or client.recording):
                client.send_packet_to_server(packet)

    def play_file(self, filename):
        """
        Play an audio file and send it to the server for processing.

        Reads an audio file, plays it through the audio output, and simultaneously sends
        the audio data to the server for processing. It uses PyAudio to create an audio
        stream for playback. The audio data is read from the file in chunks, converted to
        floating-point format, and sent to the server using WebSocket communication.
        This method is typically used when you want to process pre-recorded audio and send it
        to the server in real-time.

        Args:
            filename (str): The path to the audio file to be played and sent to the server.
        """

        # read audio and create pyaudio stream
        with wave.open(filename, "rb") as wavfile:
            self.stream = self.p.open(
                format=self.p.get_format_from_width(wavfile.getsampwidth()),
                channels=wavfile.getnchannels(),
                rate=wavfile.getframerate(),
                input=True,
                output=True,
                frames_per_buffer=self.chunk,
            )
            chunk_duration = self.chunk / float(wavfile.getframerate())
            try:
                while any(client.recording for client in self.clients):
                    data = wavfile.readframes(self.chunk)
                    if data == b"":
                        break

                    audio_array = self.bytes_to_float_array(data)
                    self.multicast_packet(audio_array.tobytes())
                    if self.mute_audio_playback:
                        time.sleep(chunk_duration)
                    else:
                        self.stream.write(data)

                wavfile.close()

                for client in self.clients:
                    client.wait_before_disconnect()
                self.multicast_packet(Client.END_OF_AUDIO.encode('utf-8'), True)
                self.write_all_clients_srt()
                self.stream.close()
                self.close_all_clients()

            except KeyboardInterrupt:
                wavfile.close()
                self.stream.stop_stream()
                self.stream.close()
                self.p.terminate()
                self.close_all_clients()
                self.write_all_clients_srt()
                logger.info("Keyboard interrupt.")

    def process_rtsp_stream(self, rtsp_url):
        """
        Connect to an RTSP source, process the audio stream, and send it for transcription.

        Args:
            rtsp_url (str): The URL of the RTSP stream source.
        """
        logger.info("Connecting to RTSP stream...")
        try:
            container = av.open(rtsp_url, format="rtsp", options={"rtsp_transport": "tcp"})
            self.process_av_stream(container, stream_type="RTSP")
        except Exception as e:
            logger.error(f"Failed to process RTSP stream: {e}")
        finally:
            for client in self.clients:
                client.wait_before_disconnect()
            self.multicast_packet(Client.END_OF_AUDIO.encode('utf-8'), True)
            self.close_all_clients()
            self.write_all_clients_srt()
        logger.info("RTSP stream processing finished.")

    def process_hls_stream(self, hls_url, save_file=None):
        """
        Connect to an HLS source, process the audio stream, and send it for transcription.

        Args:
            hls_url (str): The URL of the HLS stream source.
            save_file (str, optional): Local path to save the network stream.
        """
        logger.info("Connecting to HLS stream...")
        try:
            container = av.open(hls_url, format="hls")
            self.process_av_stream(container, stream_type="HLS", save_file=save_file)
        except Exception as e:
            logger.error(f"Failed to process HLS stream: {e}")
        finally:
            for client in self.clients:
                client.wait_before_disconnect()
            self.multicast_packet(Client.END_OF_AUDIO.encode('utf-8'), True)
            self.close_all_clients()
            self.write_all_clients_srt()
        logger.info("HLS stream processing finished.")

    def process_av_stream(self, container, stream_type, save_file=None):
        """
        Process an AV container stream and send audio packets to the server.

        Args:
            container (av.container.InputContainer): The input container to process.
            stream_type (str): The type of stream being processed ("RTSP" or "HLS").
            save_file (str, optional): Local path to save the stream. Default is None.
        """
        audio_stream = next((s for s in container.streams if s.type == "audio"), None)
        if not audio_stream:
            logger.error(f"No audio stream found in {stream_type} source.")
            return

        output_container = None
        if save_file:
            output_container = av.open(save_file, mode="w")
            output_audio_stream = output_container.add_stream(codec_name="pcm_s16le", rate=self.rate)

        try:
            for packet in container.demux(audio_stream):
                for frame in packet.decode():
                    audio_data = frame.to_ndarray().tobytes()
                    self.multicast_packet(audio_data)

                    if save_file:
                        output_container.mux(frame)
        except Exception as e:
            logger.error(f"Error during {stream_type} stream processing: {e}")
        finally:
            # Wait for server to send any leftover transcription.
            time.sleep(5)
            self.multicast_packet(Client.END_OF_AUDIO.encode('utf-8'), True)
            if output_container:
                output_container.close()
            container.close()

    def save_chunk(self, n_audio_file):
        """
        Saves the current audio frames to a WAV file in a separate thread.

        Args:
        n_audio_file (int): The index of the audio file which determines the filename.
                            This helps in maintaining the order and uniqueness of each chunk.
        """
        t = threading.Thread(
            target=self.write_audio_frames_to_file,
            args=(self.frames[:], f"chunks/{n_audio_file}.wav",),
        )
        t.start()

    def finalize_recording(self, n_audio_file):
        """
        Finalizes the recording process by saving any remaining audio frames,
        closing the audio stream, and terminating the process.

        Args:
        n_audio_file (int): The file index to be used if there are remaining audio frames to be saved.
                            This index is incremented before use if the last chunk is saved.
        """
        if self.save_output_recording and len(self.frames):
            self.write_audio_frames_to_file(
                self.frames[:], f"chunks/{n_audio_file}.wav"
            )
            n_audio_file += 1
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        self.close_all_clients()
        if self.save_output_recording:
            self.write_output_recording(n_audio_file)
        self.write_all_clients_srt()

    def record(self):
        """
        Record audio data from the input stream and save it to a WAV file.

        Continuously records audio data from the input stream, sends it to the server via a WebSocket
        connection, and simultaneously saves it to multiple WAV files in chunks. It stops recording when
        the `RECORD_SECONDS` duration is reached or when the `RECORDING` flag is set to `False`.

        Audio data is saved in chunks to the "chunks" directory. Each chunk is saved as a separate WAV file.
        The recording will continue until the specified duration is reached or until the `RECORDING` flag is set to `False`.
        The recording process can be interrupted by sending a KeyboardInterrupt (e.g., pressing Ctrl+C). After recording,
        the method combines all the saved audio chunks into the specified `out_file`.
        """
        n_audio_file = 0
        if self.save_output_recording:
            if os.path.exists("chunks"):
                shutil.rmtree("chunks")
            os.makedirs("chunks")
        try:
            for _ in range(0, int(self.rate / self.chunk * self.record_seconds)):
                if not any(client.recording for client in self.clients):
                    break
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                self.frames += data

                audio_array = self.bytes_to_float_array(data)

                self.multicast_packet(audio_array.tobytes())

                # save frames if more than a minute
                if len(self.frames) > 60 * self.rate:
                    if self.save_output_recording:
                        self.save_chunk(n_audio_file)
                        n_audio_file += 1
                    self.frames = b""
            self.write_all_clients_srt()

        except KeyboardInterrupt:
            self.finalize_recording(n_audio_file)

    def write_audio_frames_to_file(self, frames, file_name):
        """
        Write audio frames to a WAV file.

        The WAV file is created or overwritten with the specified name. The audio frames should be
        in the correct format and match the specified channel, sample width, and sample rate.

        Args:
            frames (bytes): The audio frames to be written to the file.
            file_name (str): The name of the WAV file to which the frames will be written.

        """
        with wave.open(file_name, "wb") as wavfile:
            wavfile: wave.Wave_write
            wavfile.setnchannels(self.channels)
            wavfile.setsampwidth(2)
            wavfile.setframerate(self.rate)
            wavfile.writeframes(frames)

    def write_output_recording(self, n_audio_file):
        """
        Combine and save recorded audio chunks into a single WAV file.

        The individual audio chunk files are expected to be located in the "chunks" directory. Reads each chunk
        file, appends its audio data to the final recording, and then deletes the chunk file. After combining
        and saving, the final recording is stored in the specified `out_file`.


        Args:
            n_audio_file (int): The number of audio chunk files to combine.
            out_file (str): The name of the output WAV file to save the final recording.

        """
        input_files = [
            f"chunks/{i}.wav"
            for i in range(n_audio_file)
            if os.path.exists(f"chunks/{i}.wav")
        ]
        with wave.open(self.output_recording_filename, "wb") as wavfile:
            wavfile: wave.Wave_write
            wavfile.setnchannels(self.channels)
            wavfile.setsampwidth(2)
            wavfile.setframerate(self.rate)
            for in_file in input_files:
                with wave.open(in_file, "rb") as wav_in:
                    while True:
                        data = wav_in.readframes(self.chunk)
                        if data == b"":
                            break
                        wavfile.writeframes(data)
                # remove this file
                os.remove(in_file)
        wavfile.close()
        # clean up temporary directory to store chunks
        if os.path.exists("chunks"):
            shutil.rmtree("chunks")

    @staticmethod
    def bytes_to_float_array(audio_bytes):
        """
        Convert audio data from bytes to a NumPy float array.

        It assumes that the audio data is in 16-bit PCM format. The audio data is normalized to
        have values between -1 and 1.

        Args:
            audio_bytes (bytes): Audio data in bytes.

        Returns:
            np.ndarray: A NumPy array containing the audio data as float values normalized between -1 and 1.
        """
        raw_data = np.frombuffer(buffer=audio_bytes, dtype=np.int16)
        return raw_data.astype(np.float32) / 32768.0
