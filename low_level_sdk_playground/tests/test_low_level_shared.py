import math

from tests.fake_dds_messages import (
    FakeBms, FakeCompressedImage, FakeDepthImage, FakeImu, FakeLowerState,
    FakeMotor, FakeVoiceState,
)
from low_level_shared import (
    ABS2HW, MOTOR_OFFSET, config_from_args, format_all_motors, format_bms,
    format_compressed_image_meta, format_depth_image_meta, format_imu,
    format_lower_state, format_voice_state_meta, hw_to_logical, logical_to_hw,
)


def test_format_imu_includes_all_four_fields():
    imu = FakeImu(quaternion=(0.9998, 0.0012, -0.0156, 0.0023), gyroscope=(0.0021, -0.0034, 0.0012),
                  accelerometer=(0.12, -0.08, 9.78), rpy=(0.0024, -0.0312, 0.0046))
    text = format_imu(imu)
    assert "0.9998" in text
    assert "-0.0034" in text
    assert "9.78" in text


def test_format_all_motors_covers_all_sixteen():
    motors = [FakeMotor(motor_temp=30 + i) for i in range(16)]
    text = format_all_motors(motors)
    assert "Motor[ 0]" in text
    assert "Motor[15]" in text
    assert text.count("Motor[") == 16


def test_format_bms_shows_battery_level():
    assert "85" in format_bms(FakeBms(battery_level=85))


def test_format_lower_state_bundles_imu_motors_and_battery():
    state = FakeLowerState(battery_level=72)
    text = format_lower_state(state)
    assert "Quaternion" in text
    assert "Motor[15]" in text
    assert "72" in text


def test_format_compressed_image_meta_includes_format_and_size():
    img = FakeCompressedImage(data=b"\xff\xd8\xff" * 100, fmt="jpeg", frame_id="camera2_optical_frame")
    text = format_compressed_image_meta(img)
    assert "jpeg" in text
    assert "300 bytes" in text
    assert "camera2_optical_frame" in text


def test_format_depth_image_meta_includes_dimensions_and_encoding():
    depth = FakeDepthImage(width=640, height=480, encoding="16UC1")
    text = format_depth_image_meta(depth)
    assert "640x480" in text
    assert "16UC1" in text


def test_format_voice_state_meta_includes_size_and_angle():
    voice = FakeVoiceState(data=b"\x00" * 4800, angle=42.5)
    text = format_voice_state_meta(voice)
    assert "4800 bytes" in text
    assert "42.50" in text


def test_hw_to_logical_and_logical_to_hw_are_inverse_operations():
    """E9's motor-offset conversion must round-trip: reading a hardware
    angle back to logical, then converting that logical angle back to
    hardware, must reproduce the original hardware angle."""
    hw = ABS2HW[3]
    motors = [FakeMotor(q=1.0 if i == hw else 0.0) for i in range(16)]
    logical = hw_to_logical(motors, hw)
    assert logical == 1.0 - MOTOR_OFFSET[hw]
    assert math.isclose(logical_to_hw(logical, hw), 1.0)


def test_config_from_args_prefers_domain_id_when_given():
    class _Args:
        domain_id = 3
        config = "config/dds_config.yaml"

    config = config_from_args(_Args())
    assert config.use_config_file is False
    assert config.domain_id == 3


def test_config_from_args_uses_config_file_by_default():
    class _Args:
        domain_id = None
        config = "custom/dds_config.yaml"

    config = config_from_args(_Args())
    assert config.use_config_file is True
    assert config.config_path == "custom/dds_config.yaml"
