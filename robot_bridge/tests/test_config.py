import os

from config import BridgeConfig


def test_from_env_uses_defaults_when_unset(monkeypatch):
    for key in [
        "ROBOT_IP", "CLOUD_MQTT_URL", "BRIDGE_ID", "SITE_ID", "ROBOT_ID",
        "DDS_INTERFACE", "TELEMETRY_POLL_HZ", "HEARTBEAT_INTERVAL_S",
        "SAFETY_MAX_SPEED_RATIO", "SAFETY_MIN_BATTERY_PCT",
        "STALE_TELEMETRY_THRESHOLD_S", "CMD_TIMEOUT_S", "RECONNECT_BACKOFF_MAX_S",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = BridgeConfig.from_env()

    assert config.robot_ip == "192.168.5.2:50051"
    assert config.cloud_mqtt_url == "mqtt://localhost:1883"
    assert config.bridge_id == "bridge-dev-01"
    assert config.site_id == "site-dev"
    assert config.robot_id == "robot-dev-01"
    assert config.dds_interface == "eth0"
    assert config.telemetry_poll_hz == 10
    assert config.heartbeat_interval_s == 5.0
    assert config.safety_max_speed_ratio == 80
    assert config.safety_min_battery_pct == 15.0
    assert config.stale_telemetry_threshold_s == 3.0
    assert config.cmd_timeout_s == 10.0
    assert config.reconnect_backoff_max_s == 60.0


def test_from_env_reads_overrides(monkeypatch):
    monkeypatch.setenv("TELEMETRY_POLL_HZ", "5")
    monkeypatch.setenv("SITE_ID", "site-test")

    config = BridgeConfig.from_env()

    assert config.telemetry_poll_hz == 5
    assert config.site_id == "site-test"
