import json

from connection_manager import ConnectionManager
from shared.schemas.telemetry import TelemetryFrame


class _FakeMqttClient:
    def __init__(self):
        self.connected_to = None
        self.published = []
        self.loop_started = False

    def connect(self, host, port):
        self.connected_to = (host, port)

    def loop_start(self):
        self.loop_started = True

    def loop_stop(self):
        self.loop_started = False

    def disconnect(self):
        self.connected_to = None

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


def test_connect_parses_broker_url_and_starts_loop(make_config):
    fake = _FakeMqttClient()
    manager = ConnectionManager(
        make_config(cloud_mqtt_url="mqtt://broker.local:1883"), lambda: fake,
    )
    manager.connect()
    assert fake.connected_to == ("broker.local", 1883)
    assert fake.loop_started is True


def test_publish_registration_uses_admin_topic(make_config):
    fake = _FakeMqttClient()
    manager = ConnectionManager(
        make_config(bridge_id="bridge-x", site_id="site-x", robot_id="robot-x"), lambda: fake,
    )
    manager.publish_registration("wheel")
    topic, payload, qos = fake.published[0]
    assert topic == "roverhub/admin/bridge-x/register"
    assert qos == 1
    assert json.loads(payload)["robot_type"] == "wheel"


def test_publish_telemetry_uses_site_robot_topic(make_config):
    fake = _FakeMqttClient()
    manager = ConnectionManager(
        make_config(site_id="site-x", robot_id="robot-x"), lambda: fake,
    )
    frame = TelemetryFrame(
        robot_id="robot-x", site_id="site-x", robot_type="quad",
        pos_body=(0.0, 0.0, 0.0), vel_body=(0.0, 0.0, 0.0),
        speed_ratio=0, battery_percent=80.0, obstacle_avoidance_enabled=True,
        grpc_freshness="live", captured_at="2026-07-20T00:00:00Z",
    )
    manager.publish_telemetry(frame)
    topic, payload, qos = fake.published[-1]
    assert topic == "roverhub/site-x/robot-x/telemetry"
    assert qos == 0
