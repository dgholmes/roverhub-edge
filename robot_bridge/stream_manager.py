from __future__ import annotations

import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional

logger = logging.getLogger("robot_bridge.stream_manager")

MJPEG_BOUNDARY = "roverhubframe"
POLL_INTERVAL_S = 0.05  # ~20fps poll of the latest-frame buffer per connection


class _FrameBuffer:
    """Thread-safe single-slot latest-frame holder. dobot_adapter's
    subscribe_rgb_frame() callback fires from a DDS-internal thread (the
    real dds_middleware_python's callback threading model isn't documented
    by the vendored SDK), while HTTP requests are served on
    ThreadingHTTPServer's own per-connection threads -- a lock protects the
    shared reference between them."""

    def __init__(self):
        self._lock = threading.Lock()
        self._jpeg: Optional[bytes] = None

    def update(self, jpeg_bytes: bytes) -> None:
        with self._lock:
            self._jpeg = jpeg_bytes

    def latest(self) -> Optional[bytes]:
        with self._lock:
            return self._jpeg


class StreamManager:
    """Dev/test video relay: serves the latest JPEG frame received from each
    camera's DDS subscription (dobot_adapter.subscribe_rgb_frame, E1) as an
    MJPEG (multipart/x-mixed-replace) HTTP stream at GET /video/{camera}.
    Frames arrive already JPEG-compressed by the robot's own camera stack --
    this never re-encodes, it's a byte-for-byte relay of whatever the SDK
    handed us.

    This serves a direct edge-to-browser HTTP connection, which only works
    when the browser can reach the edge device's IP directly (same LAN --
    e.g. a Jetson/Raspberry Pi wired to the robot and the dev machine on the
    same test network). This is NOT the production topology described in
    docs/02-system-architecture.md (edge never accepts inbound connections;
    the planned production path is GStreamer+NVENC+SRT -> MediaMTX ->
    browser WebRTC, R1 scope). Treat this as a local dev/test shortcut to get
    a real video feed working now, not the final production video pipeline.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8090):
        self._host = host
        self._port = port
        self._buffers: Dict[str, _FrameBuffer] = {}
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def frame_handler(self, camera: str):
        """Returns a callback suitable for
        dobot_adapter.subscribe_rgb_frame(camera, <this>) -- updates the
        named camera's latest-frame buffer, creating it on first use so
        GET /video/{camera} starts returning 200s as soon as a subscription
        for that camera exists."""
        buffer = self._buffers.setdefault(camera, _FrameBuffer())

        def _on_frame(jpeg_bytes: bytes, frame_id: str) -> None:
            buffer.update(jpeg_bytes)

        return _on_frame

    @property
    def port(self) -> int:
        """Actual bound port -- differs from the constructor's `port` when
        constructed with port=0 (OS-assigned, used by tests)."""
        if self._server is not None:
            return self._server.server_address[1]
        return self._port

    def start(self) -> None:
        if self._server is not None:
            return
        manager = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args) -> None:
                pass  # BaseHTTPRequestHandler logs every request to stderr by default

            def handle_error(self, request, client_address) -> None:
                # socketserver's default handle_error prints a full traceback
                # to stderr for ANY exception, including a client simply
                # closing the connection mid-stream (expected and constant
                # for a long-lived MJPEG connection) -- only that specific,
                # already-handled case reaches here as a fallback (do_GET's
                # own try/except catches most of it); suppress the noise.
                pass

            def do_GET(self) -> None:
                parts = self.path.strip("/").split("/")
                if len(parts) != 2 or parts[0] != "video":
                    self.send_response(404)
                    self.end_headers()
                    return
                buffer = manager._buffers.get(parts[1])
                if buffer is None:
                    self.send_response(404)
                    self.end_headers()
                    return

                self.send_response(200)
                self.send_header("Age", "0")
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}")
                self.end_headers()
                try:
                    while True:
                        jpeg = buffer.latest()
                        if jpeg is not None:
                            self.wfile.write(f"--{MJPEG_BOUNDARY}\r\n".encode())
                            self.wfile.write(b"Content-Type: image/jpeg\r\n")
                            self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                            self.wfile.write(jpeg)
                            self.wfile.write(b"\r\n")
                        time.sleep(POLL_INTERVAL_S)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # client navigated away / closed the connection

        self._server = ThreadingHTTPServer((self._host, self._port), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("stream_manager serving MJPEG video on http://%s:%s/video/{camera}", self._host, self.port)

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
