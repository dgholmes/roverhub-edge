# Edge SDK Playground

Standalone tools to exercise the Dobot Quad **high-level** Python SDK
(`dobot_quad.RobotClient`, gRPC) before the real edge bridge adapter
(`robot_bridge/dobot_adapter.py`) is built. Does not touch the
low-level DDS API, does not touch `robot_bridge/`, and never modifies
anything under `vendor/dobot_quad_sdk/`.

See the design spec:
`docs/superpowers/specs/2026-07-05-edge-sdk-playground-design.md`.

## Setup

```bash
pip install -r requirements.txt
```

(`grpcio`/`protobuf` are already provided by the `dobot-quad-highlevel`
package installed from `vendor/dobot_quad_sdk/high_level/python`.)

## Feature tester (menu-driven)

Exercises every `RobotClient` method by category (state machine, motion
enumeration, velocity sequence, line walk/rotation, balance/pose,
configuration, telemetry query). `kill_robot` is gated behind a typed
`KILL` confirmation in the Engineering menu — it terminates the robot
controller and is not part of normal operation.

```bash
# Against a simulated robot (no hardware required):
python feature_tester.py --simulate
python feature_tester.py --simulate --sim-robot-type wheel

# Against the real robot:
python feature_tester.py --address 192.168.1.6:50051   # WiFi dev (Rover-* SSID)
python feature_tester.py --address 192.168.5.2:50051   # wired Ethernet (production)
```

## Teleop (real-time keyboard + mouse)

```bash
python teleop.py --simulate
python teleop.py --address 192.168.1.6:50051
```

Controls:

| Input | Effect |
|---|---|
| `W`/`A`/`S`/`D` | Walk velocity (forward/back/strafe) — WALK mode |
| `Q`/`E` | Yaw rate (turn left/right) — WALK mode |
| `G` | Cycle gait (walk / flying_trot, or wheel_loco on wheel robots) |
| `[` / `]` | Speed ratio -10 / +10 |
| `O` | Toggle obstacle avoidance |
| `Tab` | Switch WALK <-> POSTURE mode |
| Mouse move (POSTURE mode) | Throttled balance_yaw / balance_pitch gestures |
| Mouse scroll (POSTURE mode) | balance_height |
| `Space` | Immediate soft-stop (`passive`/emergency — recoverable) |
| `Esc` | Clean shutdown (stand_down -> passive -> disconnect) |

**Mouse-look is not a continuous camera.** `balance_yaw`/`balance_pitch`
are discrete blocking SDK gestures with a minimum 0.5s duration — moving
the mouse in POSTURE mode produces periodic "look" nods, not smooth
tracking. True continuous joint control requires the low-level DDS API,
which is out of scope for this tool.

## Running the tests

```bash
pip install -r requirements.txt   # includes pytest
pytest -v
```

All tests run against `SimulatedRobotClient` — no hardware required.
`SimulatedRobotClient` reuses the real SDK's own validation functions and
constants (`dobot_quad.robot_client.validate_state`, `clamp_balance_value`,
etc.), so a passing test suite here reflects the same input constraints the
real robot enforces.

## Real-hardware verification (pending)

Hardware was not reachable from the development machine at the time this
tool was built. Once the robot is on the network, re-run both tools with
`--address` pointing at it (see Setup above) and walk through the same
manual checklists used for `--simulate` in
`docs/superpowers/plans/2026-07-05-edge-sdk-playground.md` (Tasks 3 and 4,
Step 5 of each).
