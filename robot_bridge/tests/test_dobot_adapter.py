import pytest

from dobot_adapter import DobotAdapter
from fake_robot_client import FakeRobotClient


@pytest.mark.asyncio
async def test_connect_detects_quad_type():
    adapter = DobotAdapter(lambda: FakeRobotClient(robot_type="quad"))
    await adapter.connect()
    assert await adapter.get_robot_config() == "quad"


@pytest.mark.asyncio
async def test_dds_connected_false_until_first_lower_state_message():
    from fake_dds_middleware import FakePyDDSMiddleware, FakeLowerStateData

    middleware = FakePyDDSMiddleware(0)
    adapter = DobotAdapter(lambda: FakeRobotClient(), dds_middleware_factory=lambda: middleware)
    await adapter.connect()

    assert adapter.dds_connected is False

    await adapter.subscribe_lower_state(lambda imu, motors, battery_level: None)
    assert adapter.dds_connected is False  # subscribed, but no message has arrived yet

    middleware.subscriptions["rt/lower/state"](FakeLowerStateData(battery_level=80))
    assert adapter.dds_connected is True


@pytest.mark.asyncio
async def test_connect_detects_wheel_type():
    adapter = DobotAdapter(lambda: FakeRobotClient(robot_type="wheel"))
    await adapter.connect()
    assert await adapter.get_robot_config() == "wheel"


@pytest.mark.asyncio
async def test_connect_calls_enable_safety_ready():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    assert client.safety_ready_called is True


@pytest.mark.asyncio
async def test_get_sdk_state_before_connect_raises():
    adapter = DobotAdapter(lambda: FakeRobotClient())
    with pytest.raises(RuntimeError):
        await adapter.get_sdk_state()


@pytest.mark.asyncio
async def test_set_state_updates_sdk_state():
    adapter = DobotAdapter(lambda: FakeRobotClient())
    await adapter.connect()
    await adapter.set_state("balance_stand")
    assert await adapter.get_sdk_state() == "balance_stand"


@pytest.mark.asyncio
async def test_enable_obstacle_avoidance_toggles():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.enable_obstacle_avoidance(False)
    assert client.get_obstacle_avoidance() is False


@pytest.mark.asyncio
async def test_get_telemetry_snapshot_reflects_client_state():
    adapter = DobotAdapter(lambda: FakeRobotClient(robot_type="quad", battery_percent=55.0))
    await adapter.connect()
    snapshot = await adapter.get_telemetry_snapshot()
    assert snapshot.robot_type == "quad"
    assert snapshot.battery_percent == 55.0
    assert snapshot.pos_body == (0.0, 0.0, 0.0)


@pytest.mark.asyncio
async def test_get_sdk_state_lowercases_real_sdk_uppercase_response():
    """The real dobot_quad SDK's get_current_state_name() returns uppercase
    (e.g. "WALK"), but every downstream comparison (state_machine.py,
    command_sender.py's RESET_ESTOP check) expects lowercase."""

    class _UppercaseStateClient:
        def enable_safety_ready(self):
            pass

        def is_quad_wheel(self):
            return False

        def get_current_state_name(self):
            return "WALK"

    adapter = DobotAdapter(lambda: _UppercaseStateClient())
    await adapter.connect()
    assert await adapter.get_sdk_state() == "walk"


@pytest.mark.asyncio
async def test_get_telemetry_snapshot_lowercases_real_sdk_uppercase_current_state():
    class _RealShapedRobotState:
        pos_body = (0.0, 0.0, 0.0)
        vel_body = (0.0, 0.0, 0.0)
        acc_body = (0.0, 0.0, 0.0)
        omega_body = (0.0, 0.0, 0.0)
        ori_body = (0.0, 0.0, 0.0)
        jpos_leg = [0.0] * 12
        jvel_leg = [0.0] * 12
        jtau_leg = [0.0] * 12
        grf_left = (0.0, 0.0, 0.0)
        grf_right = (0.0, 0.0, 0.0)

    class _UppercaseStateResponse:
        current_state = "PASSIVE"
        current_speed_ratio = 0
        obstacle_avoidance_enabled = True
        robot_state = _RealShapedRobotState()

    class _UppercaseStateClient:
        def enable_safety_ready(self):
            pass

        def is_quad_wheel(self):
            return False

        def get_state(self):
            return _UppercaseStateResponse()

    adapter = DobotAdapter(lambda: _UppercaseStateClient())
    await adapter.connect()
    snapshot = await adapter.get_telemetry_snapshot()
    assert snapshot.current_state == "passive"


@pytest.mark.asyncio
async def test_get_telemetry_snapshot_defaults_battery_when_client_lacks_it():
    """Real dobot_quad.RobotClient has no battery_percent attribute (battery
    is DDS/BMS-only, out of scope this round) -- must degrade to 0.0 rather
    than raising AttributeError, unlike FakeRobotClient's test convenience."""

    class _RealShapedRobotState:
        pos_body = (1.0, 2.0, 0.0)
        vel_body = (0.0, 0.0, 0.0)
        acc_body = (0.0, 0.0, 0.0)
        omega_body = (0.0, 0.0, 0.0)
        ori_body = (0.0, 0.0, 0.0)
        jpos_leg = [0.0] * 12
        jvel_leg = [0.0] * 12
        jtau_leg = [0.0] * 12
        grf_left = (0.0, 0.0, 0.0)
        grf_right = (0.0, 0.0, 0.0)

    class _RealShapedStateResponse:
        current_state = "balance_stand"
        current_speed_ratio = 50
        obstacle_avoidance_enabled = True
        robot_state = _RealShapedRobotState()

    class _RealShapedClient:
        def enable_safety_ready(self):
            pass

        def is_quad_wheel(self):
            return False

        def get_state(self):
            return _RealShapedStateResponse()

    adapter = DobotAdapter(lambda: _RealShapedClient())
    await adapter.connect()
    snapshot = await adapter.get_telemetry_snapshot()
    assert snapshot.battery_percent == 0.0
    assert snapshot.pos_body == (1.0, 2.0, 0.0)


@pytest.mark.asyncio
async def test_disconnect_closes_client_and_clears_state():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.disconnect()
    with pytest.raises(RuntimeError):
        await adapter.get_sdk_state()


@pytest.mark.asyncio
async def test_change_mode_flips_robot_type():
    client = FakeRobotClient(robot_type="quad")
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.change_mode()
    assert client.robot_type == "wheel"


@pytest.mark.asyncio
async def test_set_speed_ratio_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.set_speed_ratio(75)
    assert client.get_state().current_speed_ratio == 75


@pytest.mark.asyncio
async def test_set_speed_ratio_reflected_in_telemetry_snapshot():
    """set_speed_ratio must be observable end-to-end via telemetry, not just
    on the client -- get_telemetry_snapshot() reads FakeRobotClient.get_state(),
    which reads the same _speed_ratio attribute set_speed_ratio writes to."""
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.set_speed_ratio(75)
    snapshot = await adapter.get_telemetry_snapshot()
    assert snapshot.current_speed_ratio == 75


@pytest.mark.asyncio
async def test_send_velocity_sequence_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.send_velocity_sequence([(0.5, 0.0, 0.0, 0.25)], gait="walk", speed_ratio=60)
    assert client.last_velocity_sequence == {
        "steps": [(0.5, 0.0, 0.0, 0.25)],
        "gait": "walk",
        "speed_ratio": 60,
        "stand_down_after": False,
    }


@pytest.mark.asyncio
async def test_line_walk_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.line_walk("forward", 2.0)
    assert client.last_line_walk == {"direction": "forward", "distance": 2.0}


@pytest.mark.asyncio
async def test_rotate_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.rotate("left", 45.0)
    assert client.last_rotate == {"direction": "left", "angle": 45.0}


@pytest.mark.asyncio
async def test_circle_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.circle("right", 2)
    assert client.last_circle == {"direction": "right", "turns": 2}


@pytest.mark.asyncio
async def test_balance_axis_calls_correct_client_method():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.balance_axis("yaw", 15.0, 0.5, "dynamic")
    assert client.last_balance_call == ("yaw", 15.0, 0.5, "dynamic")


@pytest.mark.asyncio
async def test_balance_neutral_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.balance_neutral()
    assert client.last_balance_call[0] == "neutral"


@pytest.mark.asyncio
async def test_balance_sequence_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    steps = [("balance_pitch", 15.0, 0.5, "dynamic")]
    await adapter.balance_sequence(steps)
    assert client.last_balance_sequence == steps


@pytest.mark.asyncio
async def test_dynamic_pose_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.dynamic_pose(2.0, roll_deg=10.0, pitch_deg=5.0, yaw_deg=0.0, height_m=-0.05)
    assert client.last_pose_call == ("dynamic", 2.0, 10.0, 5.0, 0.0, -0.05)


@pytest.mark.asyncio
async def test_static_pose_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.static_pose(3.0, roll_deg=-10.0, pitch_deg=0.0, yaw_deg=5.0, height_m=0.0)
    assert client.last_pose_call == ("static", 3.0, -10.0, 0.0, 5.0, 0.0)


@pytest.mark.asyncio
async def test_get_motions_returns_motion_id_list():
    adapter = DobotAdapter(lambda: FakeRobotClient())
    await adapter.connect()
    motions = await adapter.get_motions()
    assert "walk" in motions
    assert isinstance(motions, list)


class _FakeDdsMessages:
    @staticmethod
    def led_control():
        from fake_dds_middleware import FakeLEDControl
        return FakeLEDControl()

    @staticmethod
    def leds_cmd():
        from fake_dds_middleware import FakeLedsCmd
        return FakeLedsCmd()

    @staticmethod
    def header():
        from fake_dds_middleware import FakeHeader
        return FakeHeader()

    @staticmethod
    def time():
        from fake_dds_middleware import FakeTime
        return FakeTime()

    @staticmethod
    def voice_cmd():
        from fake_dds_middleware import FakeVoiceCmd
        return FakeVoiceCmd()

    @staticmethod
    def voice_priority_normal():
        return 0


@pytest.mark.asyncio
async def test_set_led_creates_writer_once_and_publishes():
    from fake_dds_middleware import FakePyDDSMiddleware

    middleware = FakePyDDSMiddleware(0)
    adapter = DobotAdapter(
        lambda: FakeRobotClient(),
        dds_middleware_factory=lambda: middleware,
        dds_messages=_FakeDdsMessages,
    )
    await adapter.connect()

    await adapter.set_led({"name": "leg_light1", "r": 255, "g": 0, "b": 0, "brightness": 255, "priority": 0})
    await adapter.set_led({"name": "leg_light2", "r": 0, "g": 255, "b": 0, "brightness": 255, "priority": 0})

    assert "rt/leds/cmd" in middleware.created_writers
    assert len(middleware.published["rt/leds/cmd"]) == 2
    first_cmd = middleware.published["rt/leds/cmd"][0]
    assert first_cmd.leds()[0].name() == "leg_light1"
    assert first_cmd.leds()[0].r() == 255


@pytest.mark.asyncio
async def test_speak_publishes_file_path():
    from fake_dds_middleware import FakePyDDSMiddleware

    middleware = FakePyDDSMiddleware(0)
    adapter = DobotAdapter(
        lambda: FakeRobotClient(),
        dds_middleware_factory=lambda: middleware,
        dds_messages=_FakeDdsMessages,
    )
    await adapter.connect()

    await adapter.speak("/tmp/clip.wav")

    assert "rt/voice/cmd" in middleware.created_writers
    published = middleware.published["rt/voice/cmd"][-1]
    assert published.path() == "/tmp/clip.wav"
    assert published.type() == "file"
    assert published.data() == []
    assert published.flag() is False


@pytest.mark.asyncio
async def test_subscribe_lower_state_translates_imu_motors_and_battery():
    from fake_dds_middleware import FakePyDDSMiddleware, FakeLowerStateData, FakeMotorStateData

    middleware = FakePyDDSMiddleware(0)
    adapter = DobotAdapter(lambda: FakeRobotClient(), dds_middleware_factory=lambda: middleware)
    await adapter.connect()

    received = []
    await adapter.subscribe_lower_state(lambda imu, motors, battery_level: received.append((imu, motors, battery_level)))

    assert "rt/lower/state" in middleware.subscriptions
    fake_state = FakeLowerStateData(
        motors=[FakeMotorStateData(mode=4, q=i * 0.1, motor_temp=30 + i) for i in range(16)],
        battery_level=72,
    )
    middleware.subscriptions["rt/lower/state"](fake_state)

    assert len(received) == 1
    imu, motors, battery_level = received[0]
    assert imu.accelerometer == (0.0, 0.0, 9.8)
    assert len(motors) == 16
    assert motors[5].q == pytest.approx(0.5)
    assert motors[5].motor_temp == 35
    assert battery_level == 72


@pytest.mark.asyncio
async def test_subscribe_lower_state_caches_battery_for_telemetry_snapshot():
    """Regression test: get_telemetry_snapshot() previously always reported
    battery_percent=0.0 on the real robot (no gRPC field exists) -- once a
    real DDS BMS reading arrives via subscribe_lower_state(), it must use
    that instead."""
    from fake_dds_middleware import FakePyDDSMiddleware, FakeLowerStateData

    middleware = FakePyDDSMiddleware(0)
    adapter = DobotAdapter(lambda: FakeRobotClient(), dds_middleware_factory=lambda: middleware)
    await adapter.connect()
    await adapter.subscribe_lower_state(lambda imu, motors, battery_level: None)

    middleware.subscriptions["rt/lower/state"](FakeLowerStateData(battery_level=63))

    snapshot = await adapter.get_telemetry_snapshot()
    assert snapshot.battery_percent == 63.0


@pytest.mark.asyncio
async def test_subscribe_rgb_frame_passes_through_jpeg_bytes_unmodified():
    from fake_dds_middleware import FakePyDDSMiddleware, FakeCompressedImageData

    middleware = FakePyDDSMiddleware(0)
    adapter = DobotAdapter(lambda: FakeRobotClient(), dds_middleware_factory=lambda: middleware)
    await adapter.connect()

    received = []
    await adapter.subscribe_rgb_frame("front", lambda jpeg_bytes, frame_id: received.append((jpeg_bytes, frame_id)))

    assert "rt/camera/camera2/image_compressed" in middleware.subscriptions
    middleware.subscriptions["rt/camera/camera2/image_compressed"](
        FakeCompressedImageData(data=b"\xff\xd8\xff\xe0fakejpeg", frame_id="camera2_optical_frame"),
    )

    assert received == [(b"\xff\xd8\xff\xe0fakejpeg", "camera2_optical_frame")]


@pytest.mark.asyncio
async def test_subscribe_rgb_frame_back_camera_uses_camera3_topic():
    from fake_dds_middleware import FakePyDDSMiddleware

    middleware = FakePyDDSMiddleware(0)
    adapter = DobotAdapter(lambda: FakeRobotClient(), dds_middleware_factory=lambda: middleware)
    await adapter.connect()

    await adapter.subscribe_rgb_frame("back", lambda jpeg_bytes, frame_id: None)

    assert "rt/camera/camera3/image_compressed" in middleware.subscriptions


@pytest.mark.asyncio
async def test_subscribe_depth_frame_passes_through_raw_fields():
    from fake_dds_middleware import FakePyDDSMiddleware, FakeImageData

    middleware = FakePyDDSMiddleware(0)
    adapter = DobotAdapter(lambda: FakeRobotClient(), dds_middleware_factory=lambda: middleware)
    await adapter.connect()

    received = []
    await adapter.subscribe_depth_frame("front", lambda w, h, enc, data: received.append((w, h, enc, data)))

    middleware.subscriptions["rt/camera/camera2/image_depth"](
        FakeImageData(width=640, height=480, encoding="16UC1", data=b"\x00\x01"),
    )

    assert received == [(640, 480, "16UC1", b"\x00\x01")]


@pytest.mark.asyncio
async def test_subscribe_voice_state_passes_through_audio_and_angle():
    from fake_dds_middleware import FakePyDDSMiddleware, FakeVoiceStateData

    middleware = FakePyDDSMiddleware(0)
    adapter = DobotAdapter(lambda: FakeRobotClient(), dds_middleware_factory=lambda: middleware)
    await adapter.connect()

    received = []
    await adapter.subscribe_voice_state(lambda pcm_bytes, angle_deg: received.append((pcm_bytes, angle_deg)))

    assert "rt/voice/state" in middleware.subscriptions
    middleware.subscriptions["rt/voice/state"](FakeVoiceStateData(data=b"\x00\x00\x01\x01", angle=42.5))

    assert received == [(b"\x00\x00\x01\x01", 42.5)]
