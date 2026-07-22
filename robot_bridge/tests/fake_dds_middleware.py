from __future__ import annotations

from collections import defaultdict


class FakeLEDControl:
    """Property-style getter/setter object, matching e3_led_control_pub.py's
    usage (led.name("leg_light1"), led.r(255), etc. -- called with an arg to
    set, read via the same method with no args)."""

    def __init__(self):
        self._values = {"name": None, "mode": 0, "brightness": 0, "r": 0, "g": 0, "b": 0, "priority": 0}

    def _accessor(self, key, *args):
        if args:
            self._values[key] = args[0]
            return None
        return self._values[key]

    def name(self, *args):
        return self._accessor("name", *args)

    def mode(self, *args):
        return self._accessor("mode", *args)

    def brightness(self, *args):
        return self._accessor("brightness", *args)

    def r(self, *args):
        return self._accessor("r", *args)

    def g(self, *args):
        return self._accessor("g", *args)

    def b(self, *args):
        return self._accessor("b", *args)

    def priority(self, *args):
        return self._accessor("priority", *args)


class FakeLedsCmd:
    def __init__(self):
        self._leds = []

    def leds(self, *args):
        if args:
            self._leds = args[0]
            return None
        return self._leds


class FakeTime:
    def __init__(self):
        self._sec = 0
        self._nanosec = 0

    def sec(self, *args):
        if args:
            self._sec = args[0]
            return None
        return self._sec

    def nanosec(self, *args):
        if args:
            self._nanosec = args[0]
            return None
        return self._nanosec


class FakeHeader:
    def __init__(self):
        self._stamp = None
        self._frame_id = None

    def stamp(self, *args):
        if args:
            self._stamp = args[0]
            return None
        return self._stamp

    def frame_id(self, *args):
        if args:
            self._frame_id = args[0]
            return None
        return self._frame_id


class FakeVoiceCmd:
    def __init__(self):
        self._header = None
        self._file_path = None

    def header(self, *args):
        if args:
            self._header = args[0]
            return None
        return self._header

    def file_path(self, *args):
        if args:
            self._file_path = args[0]
            return None
        return self._file_path


class FakePyDDSMiddleware:
    """Fake dds_middleware_python.PyDDSMiddleware -- see this file's module
    docstring in the task brief for why this fake carries more uncertainty
    than fake_robot_client.py."""

    def __init__(self, domain_id: int):
        self.domain_id = domain_id
        self.created_writers = {}
        self.published = defaultdict(list)

    def createLedsCmdWriter(self, topic: str, qos_config: dict):
        self.created_writers[topic] = qos_config

    def createVoiceCmdWriter(self, topic: str, qos_config: dict):
        self.created_writers[topic] = qos_config

    def publish(self, topic: str, message) -> None:
        self.published[topic].append(message)
