"""Lightweight fake DDS message objects for testing low_level_shared.py's
pure formatting functions without a real dds_middleware_python installation.
Deliberately self-contained (not shared with robot_bridge/tests/
fake_dds_middleware.py) -- this tool is meant to be copy-pasted onto a
Jetson/Raspberry Pi standalone, independent of robot_bridge/."""
from __future__ import annotations


class FakeImu:
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


class FakeMotor:
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


class FakeBms:
    def __init__(self, battery_level=80):
        self._battery_level = battery_level

    def battery_level(self):
        return self._battery_level


class FakeLowerState:
    def __init__(self, imu=None, motors=None, battery_level=80):
        self._imu = imu if imu is not None else FakeImu()
        self._motors = motors if motors is not None else [FakeMotor() for _ in range(16)]
        self._bms = FakeBms(battery_level)

    def imu_state(self):
        return self._imu

    def motor_state(self):
        return self._motors

    def bms_state(self):
        return self._bms


class FakeTime:
    def __init__(self, sec=0, nanosec=0):
        self._sec = sec
        self._nanosec = nanosec

    def sec(self):
        return self._sec

    def nanosec(self):
        return self._nanosec


class FakeHeader:
    def __init__(self, frame_id="camera2_optical_frame", stamp=None):
        self._frame_id = frame_id
        self._stamp = stamp if stamp is not None else FakeTime()

    def frame_id(self):
        return self._frame_id

    def stamp(self):
        return self._stamp


class FakeCompressedImage:
    def __init__(self, data=b"", fmt="jpeg", frame_id="camera2_optical_frame"):
        self._data = data
        self._format = fmt
        self._header = FakeHeader(frame_id=frame_id)

    def header(self):
        return self._header

    def format(self):
        return self._format

    def data(self):
        return self._data


class FakeDepthImage:
    def __init__(self, width=640, height=480, encoding="16UC1", data=b"", step=1280, is_bigendian=False):
        self._width = width
        self._height = height
        self._encoding = encoding
        self._data = data
        self._step = step
        self._is_bigendian = is_bigendian

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


class FakeVoiceState:
    def __init__(self, data=b"", angle=0.0):
        self._data = data
        self._angle = angle

    def data_(self):
        return self._data

    def angle_(self):
        return self._angle
