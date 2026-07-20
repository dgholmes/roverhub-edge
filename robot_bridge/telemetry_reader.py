from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from config import BridgeConfig
from dobot_adapter import DobotAdapter
from shared.schemas.telemetry import TelemetryFrame, TelemetrySnapshot

FrameHandler = Callable[[TelemetryFrame], Awaitable[None]]
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class TelemetryReader:
    """Polls dobot_adapter at config.telemetry_poll_hz, classifies gRPC
    freshness, and emits TelemetryFrame objects to on_frame. If a poll
    fails, the last known snapshot is reused and freshness degrades based
    on elapsed time -- no frame is emitted until the first success."""

    def __init__(
        self,
        adapter: DobotAdapter,
        config: BridgeConfig,
        on_frame: FrameHandler,
        clock: Clock = _default_clock,
    ):
        self._adapter = adapter
        self._config = config
        self._on_frame = on_frame
        self._clock = clock
        self._last_snapshot: Optional[TelemetrySnapshot] = None
        self._last_received_at: Optional[float] = None
        self._running = False

    async def run_forever(self) -> None:
        self._running = True
        period_s = 1.0 / self._config.telemetry_poll_hz
        while self._running:
            await self.poll_once()
            await asyncio.sleep(period_s)

    def stop(self) -> None:
        self._running = False

    async def poll_once(self) -> None:
        now_ts = self._clock().timestamp()
        try:
            self._last_snapshot = await self._adapter.get_telemetry_snapshot()
            self._last_received_at = now_ts
        except Exception:
            pass

        if self._last_snapshot is None:
            return

        frame = TelemetryFrame(
            robot_id=self._config.robot_id,
            site_id=self._config.site_id,
            robot_type=self._last_snapshot.robot_type,
            pos_body=self._last_snapshot.pos_body,
            vel_body=self._last_snapshot.vel_body,
            speed_ratio=self._last_snapshot.current_speed_ratio,
            battery_percent=self._last_snapshot.battery_percent,
            obstacle_avoidance_enabled=self._last_snapshot.obstacle_avoidance_enabled,
            grpc_freshness=self._classify_freshness(now_ts),
            captured_at=self._last_snapshot.captured_at,
        )
        result = self._on_frame(frame)
        if asyncio.iscoroutine(result):
            await result

    def _classify_freshness(self, now_ts: float) -> str:
        if self._last_received_at is None:
            return "missing"
        age = now_ts - self._last_received_at
        return "live" if age <= self._config.stale_telemetry_threshold_s else "stale"
