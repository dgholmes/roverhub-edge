from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from config import BridgeConfig
from dobot_adapter import DobotAdapter
from shared.schemas.telemetry import TelemetryFrame, TelemetrySnapshot
from state_machine import compute_abstract_state

logger = logging.getLogger("robot_bridge.telemetry_reader")

FrameHandler = Callable[[TelemetryFrame], Awaitable[None]]
StateChangeHandler = Callable[[str, str], Awaitable[None]]
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class TelemetryReader:
    """Polls dobot_adapter at config.telemetry_poll_hz, classifies gRPC
    freshness, emits TelemetryFrame objects to on_frame, and (if
    on_state_change is provided) derives the abstract state from the same
    poll and reports it whenever it changes. If a poll fails, the last
    known snapshot is reused and freshness degrades based on elapsed time
    -- no frame is emitted until the first success."""

    def __init__(
        self,
        adapter: DobotAdapter,
        config: BridgeConfig,
        on_frame: FrameHandler,
        clock: Clock = _default_clock,
        on_state_change: Optional[StateChangeHandler] = None,
        estop_active_provider: Callable[[], bool] = lambda: False,
    ):
        self._adapter = adapter
        self._config = config
        self._on_frame = on_frame
        self._clock = clock
        self._on_state_change = on_state_change
        self._estop_active_provider = estop_active_provider
        self._last_snapshot: Optional[TelemetrySnapshot] = None
        self._last_received_at: Optional[float] = None
        self._last_abstract_state: Optional[str] = None
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
            logger.exception("telemetry poll failed; reusing last known snapshot if any")

        if self._last_snapshot is None:
            return

        frame = TelemetryFrame(
            robot_id=self._config.robot_id,
            site_id=self._config.site_id,
            robot_type=self._last_snapshot.robot_type,
            pos_body=self._last_snapshot.pos_body,
            vel_body=self._last_snapshot.vel_body,
            acc_body=self._last_snapshot.acc_body,
            omega_body=self._last_snapshot.omega_body,
            ori_body=self._last_snapshot.ori_body,
            jpos_leg=self._last_snapshot.jpos_leg,
            jvel_leg=self._last_snapshot.jvel_leg,
            jtau_leg=self._last_snapshot.jtau_leg,
            grf_left=self._last_snapshot.grf_left,
            grf_right=self._last_snapshot.grf_right,
            speed_ratio=self._last_snapshot.current_speed_ratio,
            battery_percent=self._last_snapshot.battery_percent,
            obstacle_avoidance_enabled=self._last_snapshot.obstacle_avoidance_enabled,
            grpc_freshness=self._classify_freshness(now_ts),
            captured_at=self._last_snapshot.captured_at,
        )
        result = self._on_frame(frame)
        if inspect.isawaitable(result):
            await result

        if self._on_state_change is not None:
            abstract_state = compute_abstract_state(
                sdk_state=self._last_snapshot.current_state,
                estop_active=self._estop_active_provider(),
                obstacle_avoidance_enabled=self._last_snapshot.obstacle_avoidance_enabled,
            )
            if abstract_state != self._last_abstract_state:
                self._last_abstract_state = abstract_state
                await self._on_state_change(self._last_snapshot.current_state, abstract_state)

    def _classify_freshness(self, now_ts: float) -> str:
        if self._last_received_at is None:
            return "missing"
        age = now_ts - self._last_received_at
        return "live" if age <= self._config.stale_telemetry_threshold_s else "stale"
