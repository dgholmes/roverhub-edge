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


class FakeImuStateData:
    """Matches LowerState.imu_state() (E4)."""

    def __init__(self, quaternion=(1.0, 0.0, 0.0, 0.0), gyroscope=(0.0, 0.0, 0.0),
                 accelerometer=(0.0, 0.0, 9.8), rpy=(0.0, 0.0, 0.0)):
        self._quaternion = quaternion
        self._gyroscope = gyroscope
        self._accelerometer = accelerometer
        self._rpy = rpy

    def quaternion(self):
        return self._quaternion

    def gyroscope(self):
        return self._gyroscope

    def accelerometer(self):
        return self._accelerometer

    def rpy(self):
        return self._rpy


class FakeMotorStateData:
    """One entry of LowerState.motor_state() (E5) -- a 16-element array in the real SDK."""

    def __init__(self, mode=4, q=0.0, dq=0.0, ddq=0.0, tau_est=0.0,
                 q_raw=0.0, dq_raw=0.0, ddq_raw=0.0, motor_temp=35):
        self._mode = mode
        self._q = q
        self._dq = dq
        self._ddq = ddq
        self._tau_est = tau_est
        self._q_raw = q_raw
        self._dq_raw = dq_raw
        self._ddq_raw = ddq_raw
        self._motor_temp = motor_temp

    def mode(self):
        return self._mode

    def q(self):
        return self._q

    def dq(self):
        return self._dq

    def ddq(self):
        return self._ddq

    def tau_est(self):
        return self._tau_est

    def q_raw(self):
        return self._q_raw

    def dq_raw(self):
        return self._dq_raw

    def ddq_raw(self):
        return self._ddq_raw

    def motor_temp(self):
        return self._motor_temp


class FakeBmsStateData:
    """Matches LowerState.bms_state() (E6) -- Python bindings only expose battery_level."""

    def __init__(self, battery_level=80):
        self._battery_level = battery_level

    def battery_level(self):
        return self._battery_level


class FakeLowerStateData:
    """Matches rt/lower/state's LowerState message -- E4/E5/E6 all read this
    one message via imu_state()/motor_state()/bms_state()."""

    def __init__(self, imu=None, motors=None, battery_level=80):
        self._imu = imu if imu is not None else FakeImuStateData()
        self._motors = motors if motors is not None else [FakeMotorStateData() for _ in range(16)]
        self._bms = FakeBmsStateData(battery_level)

    def imu_state(self):
        return self._imu

    def motor_state(self):
        return self._motors

    def bms_state(self):
        return self._bms


class FakeCompressedImageData:
    """Matches CompressedImage (E1) -- rt/camera/*/image_compressed."""

    def __init__(self, data=b"", frame_id="camera2_optical_frame", fmt="jpeg", sec=0, nanosec=0):
        self._header = FakeHeader()
        self._header.frame_id(frame_id)
        stamp = FakeTime()
        stamp.sec(sec)
        stamp.nanosec(nanosec)
        self._header.stamp(stamp)
        self._format = fmt
        self._data = data

    def header(self):
        return self._header

    def format(self):
        return self._format

    def data(self):
        return self._data


class FakeImageData:
    """Matches Image (E2) -- rt/camera/*/image_depth."""

    def __init__(self, width=640, height=480, encoding="16UC1", data=b"", step=1280, is_bigendian=False):
        self._header = FakeHeader()
        self._width = width
        self._height = height
        self._encoding = encoding
        self._data = data
        self._step = step
        self._is_bigendian = is_bigendian

    def header(self):
        return self._header

    def width(self):
        return self._width

    def height(self):
        return self._height

    def encoding(self):
        return self._encoding

    def data(self):
        return self._data

    def step(self):
        return self._step

    def is_bigendian(self):
        return self._is_bigendian


class FakeVoiceStateData:
    """Matches VoiceState (E8) -- rt/voice/state."""

    def __init__(self, data=b"", angle=0.0):
        self._data = data
        self._angle = angle

    def data_(self):
        return self._data

    def angle_(self):
        return self._angle


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
        # topic -> callback the adapter registered, so tests can simulate an
        # incoming message with `fake.subscriptions["rt/lower/state"](FakeLowerStateData(...))`.
        self.subscriptions = {}

    def createLedsCmdWriter(self, topic: str, qos_config: dict):
        self.created_writers[topic] = qos_config

    def createVoiceCmdWriter(self, topic: str, qos_config: dict):
        self.created_writers[topic] = qos_config

    def createLowerCmdWriter(self, topic: str, qos_config: dict):
        self.created_writers[topic] = qos_config

    def publishLedsCmd(self, message) -> None:
        self.published["rt/leds/cmd"].append(message)

    def publishLowerCmd(self, message) -> None:
        self.published["rt/lower/cmd"].append(message)

    def subscribeLowerState(self, topic: str, callback) -> None:
        self.subscriptions[topic] = callback

    def subscribeCompressedImage(self, topic: str, callback) -> None:
        self.subscriptions[topic] = callback

    def subscribeImage(self, topic: str, callback, qos_config: dict) -> None:
        self.subscriptions[topic] = callback

    def subscribeVoiceState(self, topic: str, callback, qos_config: dict) -> None:
        self.subscriptions[topic] = callback

    def publishVoiceCmd(self, message) -> None:
        self.published["rt/voice/cmd"].append(message)
