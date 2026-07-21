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


class DobotAdapter:
    """Sole SDK import boundary at runtime. client_factory constructs the
    underlying client (real in production via real_client_factory, fake
    in tests) so no other module needs to know which one is in use."""

    def __init__(self, client_factory: ClientFactory):
        self._client_factory = client_factory
        self._client = None
        self._robot_type: Optional[str] = None

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
        return self._client.get_current_state_name()

    async def get_robot_config(self) -> str:
        self._require_connected()
        return self._robot_type

    async def set_state(self, target: str) -> None:
        self._require_connected()
        self._client.set_target_state(target)

    async def enable_obstacle_avoidance(self, enabled: bool) -> None:
        self._require_connected()
        self._client.set_obstacle_avoidance(enabled)

    async def get_telemetry_snapshot(self) -> TelemetrySnapshot:
        self._require_connected()
        state = self._client.get_state()
        return TelemetrySnapshot(
            current_state=state.current_state,
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
