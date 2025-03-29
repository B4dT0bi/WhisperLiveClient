import json
import threading
import time
import uuid

import websocket

import whisper_live.utils as utils
from loguru import logger


# Copied from https://github.com/B4dT0bi/WhisperLive/blob/main/whisper_live/client.py

class Client:
    """
    Handles communication with a server using WebSocket.
    """
    INSTANCES = {}
    END_OF_AUDIO = "END_OF_AUDIO"

    def __init__(
            self,
            host=None,
            port=None,
            lang=None,
            translate=False,
            model="small",
            srt_file_path="output.srt",
            use_vad=True,
            log_transcription=True,
            max_clients=4,
            max_connection_time=600,
    ):
        """
        Initializes a Client instance for audio recording and streaming to a server.

        If host and port are not provided, the WebSocket connection will not be established.
        When translate is True, the task will be set to "translate" instead of "transcribe".
        he audio recording starts immediately upon initialization.

        Args:
            host (str): The hostname or IP address of the server.
            port (int): The port number for the WebSocket server.
            lang (str, optional): The selected language for transcription. Default is None.
            translate (bool, optional): Specifies if the task is translation. Default is False.
            model (str, optional): The whisper model to use (e.g., "small", "medium", "large"). Default is "small".
            srt_file_path (str, optional): The file path to save the output SRT file. Default is "output.srt".
            use_vad (bool, optional): Whether to enable voice activity detection. Default is True.
            log_transcription (bool, optional): Whether to log transcription output to the console. Default is True.
            max_clients (int, optional): Maximum number of client connections allowed. Default is 4.
            max_connection_time (int, optional): Maximum allowed connection time in seconds. Default is 600.
        """
        self.error_message = None
        self.server_backend = None
        self.recording = False
        self.task = "transcribe"
        self.uid = str(uuid.uuid4())
        self.waiting = False
        self.last_response_received = None
        self.disconnect_if_no_response_for = 15
        self.language = lang
        self.model = model
        self.server_error = False
        self.srt_file_path = srt_file_path
        self.use_vad = use_vad
        self.last_segment = None
        self.last_received_segment = None
        self.log_transcription = log_transcription
        self.max_clients = max_clients
        self.max_connection_time = max_connection_time
        self.callbacks = {
            "handle_status_messages": None,
            "process_segments": None,
            "on_error": None,
            "on_close": None,
            "server_disconnect_overtime": None,
            "server_ready": None,
        }

        if translate:
            self.task = "translate"

        self.audio_bytes = None

        if host is not None and port is not None:
            socket_url = f"ws://{host}:{port}"
            self.client_socket = websocket.WebSocketApp(
                socket_url,
                on_open=lambda ws: self.on_open(ws),
                on_message=lambda ws, message: self.on_message(ws, message),
                on_error=lambda ws, error: self.on_error(ws, error),
                on_close=lambda ws, close_status_code, close_msg: self.on_close(
                    ws, close_status_code, close_msg
                ),
            )
        else:
            logger.error("No host or port specified.")
            return

        Client.INSTANCES[self.uid] = self

        # start websocket client in a thread
        self.ws_thread = threading.Thread(target=self.client_socket.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()

        self.transcript = []
        logger.info("* recording")

    def register_callback(self, event_name, callback):
        if event_name in self.callbacks:
            self.callbacks[event_name] = callback
        else:
            logger.warning(f"Unknown callback event: {event_name}")

    def _invoke_callback_async(self, name, *args, **kwargs):
        callback = self.callbacks.get(name)
        if callback:
            threading.Thread(target=callback, args=args, kwargs=kwargs, daemon=True).start()

    def handle_status_messages(self, message_data):
        """Handles server status messages."""
        status = message_data["status"]
        if status == "WAIT":
            self.waiting = True
            logger.info(f"Server is full. Estimated wait time {round(message_data['message'])} minutes.")
        elif status == "ERROR":
            logger.error(f"Message from Server: {message_data['message']}")
            self.server_error = True
        elif status == "WARNING":
            logger.warning(f"Message from Server: {message_data['message']}")
        self._invoke_callback_async("handle_status_messages", message_data)

    def process_segments(self, segments):
        """Processes transcript segments."""
        text = []
        for i, seg in enumerate(segments):
            if not text or text[-1] != seg["text"]:
                text.append(seg["text"])
                if i == len(segments) - 1 and not seg.get("completed", False):
                    self.last_segment = seg
                elif (self.server_backend == "faster_whisper" and seg.get("completed", False) and
                      (not self.transcript or
                       float(seg['start']) >= float(self.transcript[-1]['end']))):
                    self.transcript.append(seg)
        # update last received segment and last valid response time
        if self.last_received_segment is None or self.last_received_segment != segments[-1]["text"]:
            self.last_response_received = time.time()
            self.last_received_segment = segments[-1]["text"]

        if self.log_transcription:
            # Truncate to last 3 entries for brevity.
            text = text[-6:]
            utils.clear_screen()
            utils.print_transcript(text)
        self._invoke_callback_async("process_segments", segments)

    def on_message(self, ws, message):
        """
        Callback function called when a message is received from the server.

        It updates various attributes of the client based on the received message, including
        recording status, language detection, and server messages. If a disconnect message
        is received, it sets the recording status to False.

        Args:
            ws (websocket.WebSocketApp): The WebSocket client instance.
            message (str): The received message from the server.

        """
        message = json.loads(message)

        if self.uid != message.get("uid"):
            logger.error("invalid client uid")
            return

        if "status" in message.keys():
            self.handle_status_messages(message)
            return

        if "message" in message.keys() and message["message"] == "DISCONNECT":
            logger.info("Server disconnected due to overtime.")
            self.recording = False
            self._invoke_callback_async("server_disconnect_overtime")

        if "message" in message.keys() and message["message"] == "SERVER_READY":
            self.last_response_received = time.time()
            self.recording = True
            self.server_backend = message["backend"]
            logger.info(f"Server Running with backend {self.server_backend}")
            self._invoke_callback_async("server_ready")
            return

        if "language" in message.keys():
            self.language = message.get("language")
            lang_prob = message.get("language_prob")
            logger.info(
                f"Server detected language {self.language} with probability {lang_prob}"
            )
            return

        if "segments" in message.keys():
            self.process_segments(message["segments"])

    def on_error(self, ws, error):
        logger.error(f"WebSocket Error: {error}")
        self.server_error = True
        self.error_message = error
        self._invoke_callback_async("on_error", ws, error)

    def on_close(self, ws, close_status_code, close_msg):
        logger.info(f"Websocket connection closed: {close_status_code}: {close_msg}")
        self.recording = False
        self.waiting = False
        self._invoke_callback_async("on_close", ws, close_status_code, close_msg)

    def on_open(self, ws):
        """
        Callback function called when the WebSocket connection is successfully opened.

        Sends an initial configuration message to the server, including client UID,
        language selection, and task type.

        Args:
            ws (websocket.WebSocketApp): The WebSocket client instance.

        """
        logger.info("Opened connection")
        ws.send(
            json.dumps(
                {
                    "uid": self.uid,
                    "language": self.language,
                    "task": self.task,
                    "model": self.model,
                    "use_vad": self.use_vad,
                    "max_clients": self.max_clients,
                    "max_connection_time": self.max_connection_time,
                }
            )
        )

    def send_packet_to_server(self, message):
        """
        Send an audio packet to the server using WebSocket.

        Args:
            message (bytes): The audio data packet in bytes to be sent to the server.

        """
        try:
            self.client_socket.send(message, websocket.ABNF.OPCODE_BINARY)
        except Exception as e:
            logger.error(e)

    def close_websocket(self):
        """
        Close the WebSocket connection and join the WebSocket thread.

        First attempts to close the WebSocket connection using `self.client_socket.close()`. After
        closing the connection, it joins the WebSocket thread to ensure proper termination.

        """
        try:
            self.client_socket.close()
        except Exception as e:
            logger.error("Error closing WebSocket:", e)

        try:
            self.ws_thread.join()
        except Exception as e:
            logger.error("Error joining WebSocket thread:", e)

    def get_client_socket(self):
        """
        Get the WebSocket client socket instance.

        Returns:
            WebSocketApp: The WebSocket client socket instance currently in use by the client.
        """
        return self.client_socket

    def write_srt_file(self, output_path="output.srt"):
        """
        Writes out the transcript in .srt format.

        Args:
            output_path (optional): The path to the target file.  Default is "output.srt".

        """
        if self.server_backend == "faster_whisper":
            if not self.transcript and self.last_segment is not None:
                self.transcript.append(self.last_segment)
            elif self.last_segment and self.transcript[-1]["text"] != self.last_segment["text"]:
                self.transcript.append(self.last_segment)
            utils.create_srt_file(self.transcript, output_path)

    def wait_before_disconnect(self):
        """Waits a bit before disconnecting in order to process pending responses."""
        assert self.last_response_received
        while time.time() - self.last_response_received < self.disconnect_if_no_response_for:
            continue
