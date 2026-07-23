# Low-Level SDK Playground

Standalone tool to exercise the Dobot Quad **low-level** DDS API (E1-E9:
RGB/depth camera, LED, IMU, motor state, battery, voice, raw motor
commands) directly, ahead of / alongside `robot_bridge/`'s real low-level
integration (`dobot_adapter.py`'s `subscribe_lower_state`/
`subscribe_rgb_frame`/etc., `low_level_reader.py`, `stream_manager.py`).
Same relationship to `robot_bridge/` that `sdk_playground/` has for the
high-level SDK (see CLAUDE.md's SDK Isolation section) -- talks to
`dds_middleware_python` directly, never imported by `robot_bridge/`.

Full setup + usage guide: `docs/09-low-level-sdk.md`.

## Setup

Requires a Jetson Orin Nano Super or Raspberry Pi (or any Ubuntu 22.04
aarch64/x86_64 host) wired to the robot via Ethernet (`192.168.5.0/24`) with
the DDS middleware installed -- see `docs/09-low-level-sdk.md` for the full
platform setup. Cannot run on a Windows dev machine or over WiFi.

```bash
pip install -r requirements.txt
pip install ../vendor/dobot_quad_sdk/dist/dds_middleware_python-*.whl
pip install cyclonedds
```

## Feature tester (menu-driven)

```bash
python low_level_feature_tester.py --config config/dds_config.yaml
# or, without a config file:
python low_level_feature_tester.py --domain-id 0
```

Covers all 9 low-level examples (E1-E9). Raw motor command control (E9) is
gated behind a typed `MOTORCMD` confirmation and requires `kill_robot.py`
to have already been run against the robot -- see the in-tool warning and
`docs/09-low-level-sdk.md`'s safety section before using it.

## Tests

```bash
pytest
```

Runs entirely against fakes (`tests/fake_dds_messages.py`) -- no DDS
middleware or robot connection required.
