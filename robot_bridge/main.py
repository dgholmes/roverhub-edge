from __future__ import annotations

import asyncio
import logging

from config import BridgeConfig
from connection_manager import ConnectionManager, real_mqtt_client_factory
from dobot_adapter import DobotAdapter, real_client_factory
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

    reader = TelemetryReader(adapter, config, on_frame)
    logger.info("robot_bridge started: robot_type=%s bridge_id=%s", robot_type, config.bridge_id)
    await reader.run_forever()


if __name__ == "__main__":
    asyncio.run(run())
