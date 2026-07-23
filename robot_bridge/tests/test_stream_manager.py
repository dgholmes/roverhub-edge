import http.client
import time

import pytest

from stream_manager import MJPEG_BOUNDARY, StreamManager


@pytest.fixture
def manager():
    m = StreamManager(host="127.0.0.1", port=0)
    m.start()
    yield m
    m.stop()


def test_frame_handler_updates_the_named_camera_buffer(manager):
    handler = manager.frame_handler("front")
    assert manager._buffers["front"].latest() is None

    handler(b"\xff\xd8fakejpeg", "camera2_optical_frame")

    assert manager._buffers["front"].latest() == b"\xff\xd8fakejpeg"


def test_unknown_camera_returns_404(manager):
    conn = http.client.HTTPConnection("127.0.0.1", manager.port, timeout=2)
    conn.request("GET", "/video/nonexistent")
    resp = conn.getresponse()
    assert resp.status == 404
    conn.close()


def test_bad_path_returns_404(manager):
    conn = http.client.HTTPConnection("127.0.0.1", manager.port, timeout=2)
    conn.request("GET", "/not-video")
    resp = conn.getresponse()
    assert resp.status == 404
    conn.close()


def test_mjpeg_stream_relays_the_latest_frame_byte_for_byte(manager):
    """Regression-shaped test for the core promise of stream_manager: a
    frame handed to frame_handler() must show up, unmodified, in the HTTP
    multipart response -- no re-encoding, since frames already arrive
    JPEG-compressed from the robot's own camera stack (E1)."""
    handler = manager.frame_handler("front")
    handler(b"\xff\xd8\xff\xe0firstframe", "camera2_optical_frame")

    conn = http.client.HTTPConnection("127.0.0.1", manager.port, timeout=2)
    conn.request("GET", "/video/front")
    resp = conn.getresponse()

    assert resp.status == 200
    assert f"boundary={MJPEG_BOUNDARY}".encode() in resp.getheader("Content-Type").encode()

    # Read until we've seen the frame bytes appear in the stream, bounded by
    # a real wall-clock timeout so a bug can never hang the test suite.
    deadline = time.monotonic() + 3
    collected = b""
    while b"firstframe" not in collected and time.monotonic() < deadline:
        chunk = resp.read(4096)
        if not chunk:
            break
        collected += chunk

    assert b"firstframe" in collected
    assert MJPEG_BOUNDARY.encode() in collected
    conn.close()


def test_updated_frame_replaces_the_relayed_content(manager):
    handler = manager.frame_handler("front")
    handler(b"\xff\xd8oldframe", "camera2_optical_frame")

    conn = http.client.HTTPConnection("127.0.0.1", manager.port, timeout=2)
    conn.request("GET", "/video/front")
    resp = conn.getresponse()

    handler(b"\xff\xd8newframe", "camera2_optical_frame")

    deadline = time.monotonic() + 3
    collected = b""
    while b"newframe" not in collected and time.monotonic() < deadline:
        chunk = resp.read(4096)
        if not chunk:
            break
        collected += chunk

    assert b"newframe" in collected
    conn.close()
