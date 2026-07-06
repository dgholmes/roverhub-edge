# SDK Playground — Usage Guide

This is a walkthrough for `feature_tester.py` and `teleop.py`. For a quick
command reference, see `README.md` — this guide is the fuller "how do I
actually use this thing" companion.

## What this is for

Before RoverHub's real edge bridge (`robot_bridge/dobot_adapter.py`, still
an empty Phase-1 placeholder) gets built, we need to know exactly how the
Dobot Quad high-level SDK behaves: which calls block, which states are
mutually exclusive, what the velocity/balance limits actually feel like.
This playground answers those questions by letting you either (a) poke at
every SDK method one at a time through a menu, or (b) drive the robot
around live with a keyboard and mouse. Both work against a simulated robot
(`--simulate`) or the real one.

Neither tool touches the vendored SDK (`vendor/dobot_quad_sdk/`, read-only)
or the real edge bridge (`robot_bridge/`, still empty). They're standalone.

## Setup

```bash
cd sdk_playground
pip install -r requirements.txt
```

This installs `pynput` (keyboard/mouse capture) and `pytest`. The SDK
itself (`dobot_quad`, `grpcio`) comes from the `dobot-quad-highlevel`
package already installed from the vendored submodule at
`vendor/dobot_quad_sdk/high_level/python`.

Sanity-check the install:

```bash
pytest -v
```

You should see all tests pass (85 at the time of writing) — everything
runs against `SimulatedRobotClient`, so this works with no robot on the
network.

## Connecting to something

Every command takes the same three flags:

| Flag | Meaning |
|---|---|
| `--simulate` | Use the in-memory fake robot instead of a real connection |
| `--sim-robot-type quad\|wheel` | Which robot type to simulate (default `quad`) |
| `--address HOST:PORT` | Real robot's gRPC address (ignored with `--simulate`) |

```bash
# No hardware needed:
python feature_tester.py --simulate
python feature_tester.py --simulate --sim-robot-type wheel

# Real robot over the Rover-* WiFi network (dev):
python feature_tester.py --address 192.168.1.6:50051

# Real robot over wired Ethernet (production topology):
python feature_tester.py --address 192.168.5.2:50051
```

`teleop.py` takes the exact same flags.

## Walkthrough: `feature_tester.py`

This is a numbered menu loop. Run it, and you'll see:

```
Connected (SIMULATED). Mode: quad

==================== RoverHub SDK Playground - Feature Tester ====================
 1) Connection & Info
 2) State Machine
 3) Motion Enumeration
 4) Configuration
 5) Velocity Sequence
 6) Line Walk / Rotation
 7) Balance & Pose
 8) Engineering (dangerous)
 0) Quit
>
```

**A typical first session** — check what state the robot is in, stand it
up, walk it forward, and look at telemetry:

```
> 1                      # Connection & Info
a) get_current_state_name  b) get_state (full telemetry) ...
> a
stand_down

> 2                      # State Machine
Convenience wrappers: passive, ready, stand_down, balance_stand, walk, ...
> balance_stand
balance_stand -> balance_stand (success=True)

> 5                      # Velocity Sequence
gait ['walk', 'flying_trot'] (enter=walk):
velocity_sequence(walk) -> success=True

> 1
b
current_state:      stand_down
speed_ratio:        60
...
pos_body [m]:       ['2.40', '0.00', '0.00']
```

(The demo velocity sequence walks forward 2m, pauses, then back 2m, then
`stand_down`s — that's why `pos_body` ends up non-zero mid-sequence but the
state settles back to `stand_down` after.)

**Menu 3 (Motion Enumeration)** just dumps whatever `get_motions()` returns
right now — the SDK docs are explicit that available motions depend on
current state/configuration, so this is the one place to check "what can I
actually call right now" rather than trusting a hardcoded list.

**Menu 7 (Balance & Pose)** refuses outright if the connected robot is in
wheel configuration (`is_quad_wheel()` is true) — balance/posture motions
aren't supported on MINI_QUAD_WHEEL per the SDK. Try it with
`--sim-robot-type wheel` to see the refusal message.

**Menu 8 (Engineering) is deliberately awkward to use.** `kill_robot`
terminates the robot's controller process — it's not a recoverable E-stop,
it's closer to unplugging it. The menu makes you type the literal word
`KILL` (case-sensitive, exact match) before it'll send the command:

```
> 8
!!! kill_robot terminates the robot controller. NOT recoverable like E-stop. !!!
Type KILL to confirm, anything else to abort:
> nah
Aborted: kill_robot requires typing KILL exactly to confirm.
```

Quitting (`0`) always walks the robot to `stand_down` then `passive` before
disconnecting, whether or not you did anything dangerous.

## Walkthrough: `teleop.py`

This is real-time control — no menus, just keys and mouse movement, with a
single status line that refreshes in place:

```
[WALK] state=walk speed_ratio=50 obstacle_avoidance=on gait=walk keys=w
```

**Two modes, because the robot's state machine forces it.** The SDK has
one state for walking (`walk`/`flying_trot`/`wheel_loco`) and a different,
mutually exclusive state for standing still and posing (`balance_stand`).
You can't do both at once, so teleop has two modes and `Tab` switches
between them:

- **WALK mode** (you start here): `W`/`A`/`S`/`D` drive forward/back/strafe,
  `Q`/`E` turn left/right. Held keys are re-sampled roughly 4 times a
  second and turned into a `velocity_sequence` call scaled to whatever
  gait you're in (walk allows backward motion; `flying_trot`/`wheel_loco`
  don't — that's a real SDK limit, not a bug here).
- **POSTURE mode** (`Tab` to enter): the robot goes to `balance_stand`, and
  mouse movement drives `balance_yaw`/`balance_pitch`. Scrolling drives
  `balance_height`.

**Why mouse-look feels jerky, not smooth:** `balance_yaw`/`balance_pitch`
are SDK calls with a *minimum* 0.5-second duration each — there's no
continuous "point the head here" API at this level. Teleop batches your
mouse movement and fires periodic "look" gestures instead of a live-tracked
camera. That's the ceiling of the high-level API; true continuous joint
control is the low-level DDS interface, which is intentionally out of
scope for this tool.

**Full control reference:**

| Input | Effect | Notes |
|---|---|---|
| `W` / `S` | Forward / backward | Backward is zero on flying_trot & wheel_loco |
| `A` / `D` | Strafe left / right | |
| `Q` / `E` | Turn left / right | |
| `G` | Cycle gait | walk ↔ flying_trot (quad), or the single wheel_loco option (wheel) |
| `[` / `]` | Speed ratio −10 / +10 | Clamped to [10, 100] |
| `O` | Toggle obstacle avoidance | |
| `Tab` | Switch WALK ↔ POSTURE | No-op on wheel robots — posture isn't supported there |
| Mouse move (POSTURE) | Periodic look gesture | balance_yaw / balance_pitch |
| Mouse scroll (POSTURE) | Height adjust | balance_height |
| `Space` | **Immediate soft-stop** | Calls `passive()` — recoverable, not `kill_robot` |
| `Esc` | Clean shutdown | stand_down → passive → disconnect |

**A typical session:** launch it, hold `W` for a second to see the status
line's `state` flip to `walk` and `pos_body` start moving (check via
`feature_tester.py` in a second terminal, or just trust the status line),
tap `G` to switch to `flying_trot` and notice `S` stops doing anything
(backward is disabled on that gait), `Tab` into POSTURE and wiggle the
mouse to see periodic balance nudges, `Tab` back to WALK, and `Esc` to exit
cleanly. If anything looks wrong mid-session, `Space` immediately drops to
`passive` — safe to hit any time.

**On a wheel robot** (`--sim-robot-type wheel` or a real MINI_QUAD_WHEEL),
`G` only ever gives you `wheel_loco`, and `Tab` does nothing — POSTURE mode
is unavailable because balance motions aren't supported on that
configuration.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'pynput'` or `'dobot_quad'`** —
  run `pip install -r requirements.txt` from inside `sdk_playground/`. For
  `dobot_quad` specifically, it should already be installed from the
  vendored submodule; if not, see `docs/03-sdk-integration.md` §12.
- **Connection hangs or errors immediately against a real robot** — check
  you're actually on the right network. WiFi dev is SSID `Rover-*`,
  password `12345678`, robot at `192.168.1.6:50051`. Wired production is
  `192.168.5.2:50051` and requires being physically on the
  `192.168.5.0/24` Ethernet segment.
- **`ValueError: Unknown state '...'`** — you tried a state name that
  doesn't exist for the connected robot's configuration (e.g. `wheel_loco`
  on a quad robot, or vice versa). Check `get_robot_type()`/
  `is_quad_wheel()` in menu 1 of `feature_tester.py` first.
- **Nothing happens when you press WASD in teleop** — the status line's
  `state` should show `walk`/`flying_trot`/`wheel_loco`; if it's stuck on
  something else, the robot may still be mid-transition from startup
  (`enter_walk_mode()` drives `ready → balance_stand → <gait>` before
  accepting velocity commands — this takes a moment).

## Where this leads

Everything learned here — which calls block, the tick-based re-issuing
trick for continuous velocity, the WALK/POSTURE mutual exclusivity, the
quad/wheel divergence — is meant to directly inform the real
`robot_bridge/dobot_adapter.py` when Phase 1 building starts. See
`docs/superpowers/specs/2026-07-05-edge-sdk-playground-design.md` §11 in
the main project repo for the carry-forward notes.
