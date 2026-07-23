from low_level_reader import LowLevelReader
from shared.schemas.low_level_telemetry import ImuState, MotorState


def _imu():
    return ImuState(quaternion=(1, 0, 0, 0), gyroscope=(0, 0, 0), accelerometer=(0, 0, 9.8), rpy=(0, 0, 0))


def _motors(temp=30):
    return [MotorState(mode=4, q=0, dq=0, ddq=0, tau_est=0, q_raw=0, dq_raw=0, ddq_raw=0, motor_temp=temp) for _ in range(16)]


def test_first_call_always_publishes(make_config):
    frames = []
    reader = LowLevelReader(make_config(lower_state_publish_hz=5.0), frames.append, clock=lambda: 0.0)

    reader.on_lower_state(_imu(), _motors(), 80)

    assert len(frames) == 1
    assert frames[0].battery_level == 80


def test_calls_within_the_decimation_window_are_dropped(make_config):
    frames = []
    ticks = iter([0.0, 0.05, 0.1])  # 5Hz => min interval 0.2s
    reader = LowLevelReader(make_config(lower_state_publish_hz=5.0), frames.append, clock=lambda: next(ticks))

    reader.on_lower_state(_imu(), _motors(), 80)  # t=0.0, published
    reader.on_lower_state(_imu(), _motors(), 79)  # t=0.05, too soon, dropped
    reader.on_lower_state(_imu(), _motors(), 78)  # t=0.1, still too soon, dropped

    assert len(frames) == 1


def test_call_after_the_decimation_window_publishes_again(make_config):
    frames = []
    ticks = iter([0.0, 0.25])  # 5Hz => min interval 0.2s
    reader = LowLevelReader(make_config(lower_state_publish_hz=5.0), frames.append, clock=lambda: next(ticks))

    reader.on_lower_state(_imu(), _motors(), 80)
    reader.on_lower_state(_imu(), _motors(), 79)

    assert len(frames) == 2
    assert frames[-1].battery_level == 79


def test_frame_carries_robot_and_site_id_from_config(make_config):
    frames = []
    reader = LowLevelReader(make_config(robot_id="robot-x", site_id="site-x"), frames.append, clock=lambda: 0.0)

    reader.on_lower_state(_imu(), _motors(), 80)

    assert frames[0].robot_id == "robot-x"
    assert frames[0].site_id == "site-x"
