from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from config import BridgeConfig
from shared.schemas.telemetry import TelemetrySnapshot

ClientFactory = Callable[[], object]


def real_client_factory(config: BridgeConfig):
    """Constructs a real dobot_quad.RobotClient. The only place in
    robot_bridge/ that references the dobot_quad package by name -- see
    Global Constraints (SDK import boundary)."""
    from dobot_quad import RobotClient

    return RobotClient(config.robot_ip)


def real_dds_middleware_factory():
    """Constructs the real dds_middleware_python.PyDDSMiddleware. Only
    reachable in production -- dds_middleware_python cannot be installed on
    this dev machine (Linux/Jetson-specific .deb package), so this path has
    never been exercised, only the fake in tests/fake_dds_middleware.py."""
    import dds_middleware_python as dds

    return dds.PyDDSMiddleware(0)


class _RealDdsMessages:
    """Lazily imports dds_middleware_python's message constructors -- only
    reachable in production."""

    @staticmethod
    def led_control():
        import dds_middleware_python as dds
        return dds.LEDControl()

    @staticmethod
    def leds_cmd():
        import dds_middleware_python as dds
        return dds.LedsCmd()

    @staticmethod
    def header():
        import dds_middleware_python as dds
        return dds.Header()

    @staticmethod
    def time():
        import dds_middleware_python as dds
        return dds.Time()

    @staticmethod
    def voice_cmd():
        import dds_middleware_python as dds
        return dds.VoiceCmd()

    @staticmethod
    def voice_priority_normal():
        """The real dds.VoicePriority.kNormal enum value (e7_voice_pub.py's
        usage for ordinary, non-urgent audio) -- exposed as its own factory
        method since the fake has no equivalent enum to construct against."""
        import dds_middleware_python as dds
        return dds.VoicePriority.kNormal


class DobotAdapter:
    """Sole SDK import boundary at runtime -- covers both the high-level
    gRPC client and the low-level DDS middleware (LED/voice)."""

    def __init__(
        self,
        client_factory: ClientFactory,
        dds_middleware_factory=real_dds_middleware_factory,
        dds_messages=_RealDdsMessages,
    ):
        self._client_factory = client_factory
        self._dds_middleware_factory = dds_middleware_factory
        self._dds_messages = dds_messages
        self._client = None
        self._robot_type: Optional[str] = None
        self._dds_middleware = None
        self._led_writer_created = False
        self._voice_writer_created = False

    async def connect(self) -> None:
        self._client = self._client_factory()
        self._client.enable_safety_ready()
        self._robot_type = "wheel" if self._client.is_quad_wheel() else "quad"

    async def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._robot_type = None

    async def get_sdk_state(self) -> str:
        self._require_connected()
        return self._client.get_current_state_name().lower()

    async def get_robot_config(self) -> str:
        self._require_connected()
        return self._robot_type

    async def set_state(self, target: str) -> None:
        self._require_connected()
        self._client.set_target_state(target)

    async def enable_obstacle_avoidance(self, enabled: bool) -> None:
        self._require_connected()
        self._client.set_obstacle_avoidance(enabled)

    async def change_mode(self) -> None:
        self._require_connected()
        self._client.change_mode()
        self._robot_type = "wheel" if self._client.is_quad_wheel() else "quad"

    async def set_speed_ratio(self, ratio: int) -> None:
        self._require_connected()
        self._client.set_speed_ratio(ratio)

    async def send_velocity_sequence(self, steps, gait: str, speed_ratio: int) -> None:
        self._require_connected()
        self._client.velocity_sequence(steps, gait=gait, speed_ratio=speed_ratio, stand_down_after=False)

    async def line_walk(self, direction: str, distance: float) -> None:
        self._require_connected()
        self._client.line_walk(direction, distance)

    async def rotate(self, direction: str, angle: float) -> None:
        self._require_connected()
        self._client.rotate(direction, angle)

    async def circle(self, direction: str, turns: int) -> None:
        self._require_connected()
        self._client.circle(direction, turns)

    async def balance_axis(self, axis: str, value: float, duration: float, mode: str) -> None:
        self._require_connected()
        method = getattr(self._client, f"balance_{axis}")
        method(value, duration=duration, mode=mode)

    async def balance_neutral(self) -> None:
        self._require_connected()
        self._client.balance_neutral()

    async def balance_sequence(self, steps) -> None:
        self._require_connected()
        self._client.balance_sequence(steps)

    async def dynamic_pose(self, duration: float, roll_deg: float, pitch_deg: float, yaw_deg: float, height_m: float) -> None:
        self._require_connected()
        self._client.dynamic_pose(duration, roll_deg=roll_deg, pitch_deg=pitch_deg, yaw_deg=yaw_deg, height_m=height_m)

    async def static_pose(self, duration: float, roll_deg: float, pitch_deg: float, yaw_deg: float, height_m: float) -> None:
        self._require_connected()
        self._client.static_pose(duration, roll_deg=roll_deg, pitch_deg=pitch_deg, yaw_deg=yaw_deg, height_m=height_m)

    async def get_motions(self) -> list:
        self._require_connected()
        response = self._client.get_motions()
        motions = getattr(response, "motions", None)
        if motions is not None:
            return [m.motion_id for m in motions]
        return list(getattr(response, "motion_ids", []))

    async def set_led(self, pattern: dict) -> None:
        self._require_connected()
        middleware = self._get_dds_middleware()
        if not self._led_writer_created:
            middleware.createLedsCmdWriter("rt/leds/cmd", {
                "reliability": "reliable", "history_kind": "keep_last",
                "history_depth": 1, "durability": "volatile",
            })
            self._led_writer_created = True

        led = self._dds_messages.led_control()
        led.name(pattern["name"])
        led.mode(0)
        led.brightness(pattern.get("brightness", 255))
        led.r(pattern.get("r", 0))
        led.g(pattern.get("g", 0))
        led.b(pattern.get("b", 0))
        led.priority(pattern.get("priority", 0))
        cmd = self._dds_messages.leds_cmd()
        cmd.leds([led])
        middleware.publishLedsCmd(cmd)

    async def speak(self, file_path: str) -> None:
        self._require_connected()
        middleware = self._get_dds_middleware()
        if not self._voice_writer_created:
            middleware.createVoiceCmdWriter("rt/voice/cmd", {
                "reliability": "reliable", "history_kind": "keep_last",
                "history_depth": 5, "durability": "volatile",
            })
            self._voice_writer_created = True

        header = self._dds_messages.header()
        stamp = self._dds_messages.time()
        now = datetime.now(timezone.utc).timestamp()
        stamp.sec(int(now))
        stamp.nanosec(int((now - int(now)) * 1e9))
        header.stamp(stamp)
        header.frame_id("voice_cmd")

        # Matches e7_voice_pub.py's file-mode VoiceCmd: priority/task_id/
        # type/data/flag are all required fields on the real message, not
        # just header+path.
        voice = self._dds_messages.voice_cmd()
        voice.header(header)
        voice.priority(self._dds_messages.voice_priority_normal())
        voice.task_id("roverhub")
        voice.type("file")
        voice.path(file_path)
        voice.data([])
        voice.flag(False)
        middleware.publishVoiceCmd(voice)

    async def get_telemetry_snapshot(self) -> TelemetrySnapshot:
        self._require_connected()
        state = self._client.get_state()
        return TelemetrySnapshot(
            # Normalize case here, at the sole SDK boundary -- the real SDK
            # returns state names uppercase (e.g. "WALK"), but every
            # downstream comparison (state_machine.py, command_sender.py's
            # RESET_ESTOP precondition) uses lowercase names matching the
            # docs and the fake test client. Found by running against a
            # physical robot for the first time.
            current_state=state.current_state.lower(),
            current_speed_ratio=state.current_speed_ratio,
            obstacle_avoidance_enabled=state.obstacle_avoidance_enabled,
            robot_type=self._robot_type,
            pos_body=tuple(state.robot_state.pos_body),
            vel_body=tuple(state.robot_state.vel_body),
            # Battery has no gRPC field -- it's only available via the DDS BMS
            # subscription (e6_bms_state_sub.py), which is out of scope this
            # round (no DDS integration). FakeRobotClient exposes a
            # battery_percent attribute as a test-only convenience; the real
            # dobot_quad.RobotClient has no such attribute, so this reports
            # 0.0 (unavailable) rather than crashing telemetry/heartbeat.
            battery_percent=getattr(self._client, "battery_percent", 0.0),
            captured_at=datetime.now(timezone.utc).isoformat(),
        )

    def _require_connected(self) -> None:
        if self._client is None:
            raise RuntimeError("DobotAdapter.connect() must be called first")

    def _get_dds_middleware(self):
        if self._dds_middleware is None:
            self._dds_middleware = self._dds_middleware_factory()
        return self._dds_middleware
