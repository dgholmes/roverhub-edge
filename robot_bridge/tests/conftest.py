import pytest

from config import BridgeConfig


@pytest.fixture
def make_config():
    def _make(**overrides):
        base = dict(
            robot_ip="192.168.5.2:50051", cloud_mqtt_url="mqtt://localhost:1883",
            bridge_id="bridge-dev-01", site_id="site-dev", robot_id="robot-dev-01",
            dds_interface="eth0", telemetry_poll_hz=10, heartbeat_interval_s=5.0,
            safety_max_speed_ratio=80, safety_min_battery_pct=15.0,
            stale_telemetry_threshold_s=3.0, cmd_timeout_s=10.0,
            reconnect_backoff_max_s=60.0,
        )
        base.update(overrides)
        return BridgeConfig(**base)
    return _make
