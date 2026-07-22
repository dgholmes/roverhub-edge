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
    """Matches e7_voice_pub.py's VoiceCmd usage: header, priority (a
    dds.VoicePriority enum value in the real SDK, e.g. kNormal), task_id,
    type ("file"/"streaming"), path, data (list), flag (bool)."""

    def __init__(self):
        self._values = {
            "header": None, "priority": None, "task_id": None,
            "type": None, "path": None, "data": [], "flag": False,
        }

    def _accessor(self, key, *args):
        if args:
            self._values[key] = args[0]
            return None
        return self._values[key]

    def header(self, *args):
        return self._accessor("header", *args)

    def priority(self, *args):
        return self._accessor("priority", *args)

    def task_id(self, *args):
        return self._accessor("task_id", *args)

    def type(self, *args):
        return self._accessor("type", *args)

    def path(self, *args):
        return self._accessor("path", *args)

    def data(self, *args):
        return self._accessor("data", *args)

    def flag(self, *args):
        return self._accessor("flag", *args)


class FakePyDDSMiddleware:
    """Fake dds_middleware_python.PyDDSMiddleware -- see this file's module
    docstring in the task brief for why this fake carries more uncertainty
    than fake_robot_client.py. Real API has no generic publish(topic, msg):
    e3_led_control_pub.py/e7_voice_pub.py call dedicated
    publishLedsCmd(cmd)/publishVoiceCmd(cmd) with no topic argument (the
    topic was already bound at createXCmdWriter time) -- this fake mirrors
    that exactly, hardcoding the one topic each writer type is created on
    since this codebase only ever creates one LED writer and one voice
    writer."""

    def __init__(self, domain_id: int):
        self.domain_id = domain_id
        self.created_writers = {}
        self.published = defaultdict(list)

    def createLedsCmdWriter(self, topic: str, qos_config: dict):
        self.created_writers[topic] = qos_config

    def createVoiceCmdWriter(self, topic: str, qos_config: dict):
        self.created_writers[topic] = qos_config

    def publishLedsCmd(self, message) -> None:
        self.published["rt/leds/cmd"].append(message)

    def publishVoiceCmd(self, message) -> None:
        self.published["rt/voice/cmd"].append(message)
