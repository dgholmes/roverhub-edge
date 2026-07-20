from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from config import BridgeConfig
from connection_manager import ConnectionManager, real_mqtt_client_factory
from dobot_adapter import DobotAdapter, real_client_factory
from heartbeat import HeartbeatSender
from shared.schemas.bridge_status import StateUpdate
from telemetry_reader import TelemetryReader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("robot_bridge.main")


async def run(config: BridgeConfig | None = None, client_factory=None, mqtt_client_factory=real_mqtt_client_factory) -> None:
    config = config or BridgeConfig.from_env()
    if client_factory is None:
        client_factory = lambda: real_client_factory(config)

    adapter = DobotAdapter(client_factory)
    connection = ConnectionManager(config, mqtt_client_factory)

    await adapter.connect()
    robot_type = await adapter.get_robot_config()
    connection.connect()
    connection.publish_registration(robot_type)

    async def on_frame(frame):
        connection.publish_telemetry(frame)

    async def on_state_change(sdk_state, abstract_state):
        connection.publish_state(StateUpdate(
            robot_id=config.robot_id, site_id=config.site_id,
            abstract_state=abstract_state, sdk_state=sdk_state,
            updated_at=datetime.now(timezone.utc).isoformat(),
        ))

    async def on_heartbeat(payload):
        connection.publish_heartbeat(payload)

    reader = TelemetryReader(adapter, config, on_frame, on_state_change=on_state_change)
    heartbeat = HeartbeatSender(adapter, config, on_heartbeat)

    logger.info("robot_bridge started: robot_type=%s bridge_id=%s", robot_type, config.bridge_id)
    await asyncio.gather(reader.run_forever(), heartbeat.run_forever())


if __name__ == "__main__":
    asyncio.run(run())
