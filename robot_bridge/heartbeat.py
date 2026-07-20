from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from typing import Awaitable, Callable

from config import BridgeConfig
from dobot_adapter import DobotAdapter
from shared.schemas.bridge_status import HeartbeatPayload

HeartbeatHandler = Callable[[HeartbeatPayload], Awaitable[None]]


class HeartbeatSender:
    """Periodically reports bridge + connection health to the cloud on the
    heartbeat topic (docs/04-edge-bridge.md SS3.10). No DDS integration
    exists this round, so dds_connected is always False."""

    def __init__(self, adapter: DobotAdapter, config: BridgeConfig, on_heartbeat: HeartbeatHandler):
        self._adapter = adapter
        self._config = config
        self._on_heartbeat = on_heartbeat
        self._running = False

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            await self.send_once()
            await asyncio.sleep(self._config.heartbeat_interval_s)

    def stop(self) -> None:
        self._running = False

    async def send_once(self) -> None:
        try:
            await self._adapter.get_sdk_state()
            snapshot = await self._adapter.get_telemetry_snapshot()
            sdk_connected = True
            battery_pct = snapshot.battery_percent
        except Exception:
            sdk_connected = False
            battery_pct = 0.0

        payload = HeartbeatPayload(
            bridge_id=self._config.bridge_id,
            robot_id=self._config.robot_id,
            site_id=self._config.site_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            sdk_connected=sdk_connected,
            dds_connected=False,
            cloud_connected=True,
            battery_pct=battery_pct,
            mission_active=False,
        )
        result = self._on_heartbeat(payload)
        if inspect.isawaitable(result):
            await result
