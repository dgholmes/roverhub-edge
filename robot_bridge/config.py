from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeConfig:
    robot_ip: str
    cloud_mqtt_url: str
    bridge_id: str
    site_id: str
    robot_id: str
    dds_interface: str
    telemetry_poll_hz: int
    heartbeat_interval_s: float
    safety_max_speed_ratio: int
    safety_min_battery_pct: float
    stale_telemetry_threshold_s: float
    cmd_timeout_s: float
    reconnect_backoff_max_s: float

    @staticmethod
    def from_env() -> "BridgeConfig":
        return BridgeConfig(
            robot_ip=os.environ.get("ROBOT_IP", "192.168.5.2:50051"),
            cloud_mqtt_url=os.environ.get("CLOUD_MQTT_URL", "mqtt://localhost:1883"),
            bridge_id=os.environ.get("BRIDGE_ID", "bridge-dev-01"),
            site_id=os.environ.get("SITE_ID", "site-dev"),
            robot_id=os.environ.get("ROBOT_ID", "robot-dev-01"),
            dds_interface=os.environ.get("DDS_INTERFACE", "eth0"),
            telemetry_poll_hz=int(os.environ.get("TELEMETRY_POLL_HZ", "10")),
            heartbeat_interval_s=float(os.environ.get("HEARTBEAT_INTERVAL_S", "5.0")),
            safety_max_speed_ratio=int(os.environ.get("SAFETY_MAX_SPEED_RATIO", "80")),
            safety_min_battery_pct=float(os.environ.get("SAFETY_MIN_BATTERY_PCT", "15.0")),
            stale_telemetry_threshold_s=float(os.environ.get("STALE_TELEMETRY_THRESHOLD_S", "3.0")),
            cmd_timeout_s=float(os.environ.get("CMD_TIMEOUT_S", "10.0")),
            reconnect_backoff_max_s=float(os.environ.get("RECONNECT_BACKOFF_MAX_S", "60.0")),
        )
