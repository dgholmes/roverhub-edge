from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable, List, Optional

from shared.schemas.low_level_telemetry import ImuState, LowerStateFrame, MotorState

LowerStateFrameHandler = Callable[[LowerStateFrame], None]


class LowLevelReader:
    """Bridges dobot_adapter.subscribe_lower_state()'s raw per-callback
    firing rate (rt/lower/state publishes far faster than is useful over
    MQTT -- E4/E5/E6's own sample code throttles console output to every
    500ms for exactly this reason) down to config.lower_state_publish_hz
    before constructing and forwarding a LowerStateFrame. Synchronous by
    design: unlike command handling, publishing a lower_state frame needs
    no asyncio event loop (paho-mqtt's Client.publish() is thread-safe), so
    this can be called directly from whatever thread the real DDS
    middleware invokes its callback on."""

    def __init__(self, config, on_frame: LowerStateFrameHandler, clock: Callable[[], float] = time.monotonic):
        self._config = config
        self._on_frame = on_frame
        self._clock = clock
        self._last_published_at: Optional[float] = None

    def on_lower_state(self, imu: ImuState, motors: List[MotorState], battery_level: int) -> None:
        now = self._clock()
        min_interval = 1.0 / self._config.lower_state_publish_hz
        if self._last_published_at is not None and (now - self._last_published_at) < min_interval:
            return
        self._last_published_at = now
        frame = LowerStateFrame(
            robot_id=self._config.robot_id,
            site_id=self._config.site_id,
            imu=imu,
            motors=motors,
            battery_level=battery_level,
            captured_at=datetime.now(timezone.utc).isoformat(),
        )
        self._on_frame(frame)
