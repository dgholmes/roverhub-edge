from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from config import BridgeConfig
from shared.schemas.low_level_telemetry import ImuState, MotorState
from shared.schemas.telemetry import TelemetrySnapshot

ClientFactory = Callable[[], object]

# low_level.md's topic table (E1/E2): camera2 = front, camera3 = back.
RGB_TOPICS = {"front": "rt/camera/camera2/image_compressed", "back": "rt/camera/camera3/image_compressed"}
DEPTH_TOPICS = {"front": "rt/camera/camera2/image_depth", "back": "rt/camera/camera3/image_depth"}
NUM_LOWER_MOTORS = 16


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
        # Set by subscribe_lower_state()'s callback once a real DDS BMS
        # reading has arrived -- None until then (no DDS connection yet, or
        # low-level not wired up on this host), in which case
        # get_telemetry_snapshot() falls back to the gRPC-only 0.0 default.
        self._latest_dds_battery_level: Optional[int] = None

    async def connect(self) -> None:
        self._client = self._client_factory()
        self._client.enable_safety_ready()
        self._robot_type = "wheel" if self._client.is_quad_wheel() else "quad"

    async def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._robot_type = None

    @property
    def dds_connected(self) -> bool:
        """True once at least one real rt/lower/state message has arrived
        via subscribe_lower_state() -- the vendored SDK has no separate DDS
        connection-status API, so "we've actually received data" is the
        best available signal. False on gRPC-only hosts (low_level_enabled
        off) and before the first message on a low-level-enabled host."""
        return self._latest_dds_battery_level is not None

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

    async def subscribe_lower_state(self, on_state: Callable[[ImuState, list, int], None]) -> None:
        """Subscribes once to rt/lower/state -- E4 (IMU), E5 (16 motors), and
        E6 (BMS battery level) all read this exact same DDS topic/message,
        so one subscription serves all three. on_state is called with
        (imu, motors, battery_level) on every DDS callback firing; callers
        wanting a lower publish rate must decimate themselves (see
        low_level_reader.py) -- rt/lower/state publishes far faster than is
        useful over MQTT (E4/E5/E6's own sample code throttles console
        output to every 500ms). Also caches battery_level so
        get_telemetry_snapshot() can report real battery instead of the
        gRPC-only 0.0 fallback."""
        self._require_connected()
        middleware = self._get_dds_middleware()

        def _callback(state) -> None:
            imu_raw = state.imu_state()
            imu = ImuState(
                quaternion=tuple(imu_raw.quaternion()),
                gyroscope=tuple(imu_raw.gyroscope()),
                accelerometer=tuple(imu_raw.accelerometer()),
                rpy=tuple(imu_raw.rpy()),
            )
            motor_states_raw = state.motor_state()
            motors = [
                MotorState(
                    mode=motor_states_raw[i].mode(),
                    q=motor_states_raw[i].q(),
                    dq=motor_states_raw[i].dq(),
                    ddq=motor_states_raw[i].ddq(),
                    tau_est=motor_states_raw[i].tau_est(),
                    q_raw=motor_states_raw[i].q_raw(),
                    dq_raw=motor_states_raw[i].dq_raw(),
                    ddq_raw=motor_states_raw[i].ddq_raw(),
                    motor_temp=motor_states_raw[i].motor_temp(),
                )
                for i in range(NUM_LOWER_MOTORS)
            ]
            battery_level = state.bms_state().battery_level()
            self._latest_dds_battery_level = battery_level
            on_state(imu, motors, battery_level)

        middleware.subscribeLowerState("rt/lower/state", _callback)

    async def subscribe_rgb_frame(self, camera: str, on_frame: Callable[[bytes, str], None]) -> None:
        """camera: "front" or "back" (RGB_TOPICS). Frames arrive already
        JPEG-compressed by the robot's own camera stack (E1: Format: jpeg)
        -- on_frame receives the raw JPEG bytes as-is, no re-encoding
        needed, ready to relay directly (see stream_manager.py)."""
        self._require_connected()
        middleware = self._get_dds_middleware()
        topic = RGB_TOPICS[camera]

        def _callback(data) -> None:
            on_frame(bytes(data.data()), data.header().frame_id())

        middleware.subscribeCompressedImage(topic, _callback)

    async def subscribe_depth_frame(self, camera: str, on_frame: Callable[[int, int, str, bytes], None]) -> None:
        """camera: "front" or "back" (DEPTH_TOPICS). on_frame receives
        (width, height, encoding, raw_bytes) -- encoding is "16UC1" per E2
        (16-bit depth values). Not started by default in main.py (no
        current consumer) -- available for the low-level playground and
        future features."""
        self._require_connected()
        middleware = self._get_dds_middleware()
        topic = DEPTH_TOPICS[camera]
        qos_config = {
            "reliability": "best_effort", "history_kind": "keep_last",
            "history_depth": 5, "durability": "volatile",
        }

        def _callback(depth_msg) -> None:
            on_frame(depth_msg.width(), depth_msg.height(), depth_msg.encoding(), bytes(depth_msg.data()))

        middleware.subscribeImage(topic, _callback, qos_config)

    async def subscribe_voice_state(self, on_audio: Callable[[bytes, float], None]) -> None:
        """rt/voice/state (E8 -- microphone capture). on_audio receives
        (pcm_bytes, angle_deg): 16-bit/24kHz/mono PCM and the DDS-reported
        sound-source direction. Not started by default in main.py (no
        current consumer) -- available for the low-level playground and
        future features."""
        self._require_connected()
        middleware = self._get_dds_middleware()
        qos_config = {
            "reliability": "best_effort", "history_kind": "keep_last",
            "history_depth": 1, "durability": "volatile",
        }

        def _callback(voice_state_msg) -> None:
            on_audio(bytes(voice_state_msg.data_()), voice_state_msg.angle_())

        middleware.subscribeVoiceState("rt/voice/state", _callback, qos_config)

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
            acc_body=tuple(state.robot_state.acc_body),
            omega_body=tuple(state.robot_state.omega_body),
            ori_body=tuple(state.robot_state.ori_body),
            jpos_leg=list(state.robot_state.jpos_leg),
            jvel_leg=list(state.robot_state.jvel_leg),
            jtau_leg=list(state.robot_state.jtau_leg),
            grf_left=tuple(state.robot_state.grf_left),
            grf_right=tuple(state.robot_state.grf_right),
            # Battery has no gRPC field at all -- it's only available via the
            # DDS BMS subscription (subscribe_lower_state(), E6). When
            # low-level is wired up (Jetson/Raspberry Pi with DDS
            # middleware) and at least one lower_state message has arrived,
            # _latest_dds_battery_level is real. Otherwise (gRPC-only host,
            # or DDS not started yet) fall back to FakeRobotClient's
            # battery_percent test convenience, or 0.0 -- the real
            # dobot_quad.RobotClient has no such attribute either.
            battery_percent=(
                float(self._latest_dds_battery_level)
                if self._latest_dds_battery_level is not None
                else getattr(self._client, "battery_percent", 0.0)
            ),
            captured_at=datetime.now(timezone.utc).isoformat(),
        )

    def _require_connected(self) -> None:
        if self._client is None:
            raise RuntimeError("DobotAdapter.connect() must be called first")

    def _get_dds_middleware(self):
        if self._dds_middleware is None:
            self._dds_middleware = self._dds_middleware_factory()
        return self._dds_middleware
