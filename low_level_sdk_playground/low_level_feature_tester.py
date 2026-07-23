"""Menu-driven CLI exercising every low-level (DDS) SDK feature: E1-E9.

Usage:
    python low_level_feature_tester.py --config config/dds_config.yaml
    python low_level_feature_tester.py --domain-id 0

Requires a real dds_middleware_python installation and a wired Ethernet
connection to the robot (192.168.5.0/24) -- see docs/09-low-level-sdk.md for
setup on a Jetson Orin Nano Super or Raspberry Pi. There is no --simulate
mode here (unlike sdk_playground/feature_tester.py): the vendored SDK has no
low-level equivalent of SimulatedRobotClient, so this can only be run
against a real robot with a real DDS connection.
"""
from __future__ import annotations

import math
import time
import wave

from low_level_shared import (
    ABS2HW, DEPTH_TOPICS, LED_NAMES, LEDS_CMD_TOPIC, LOWER_CMD_TOPIC,
    LOWER_STATE_TOPIC, NUM_ACTUATED_MOTORS, NUM_LOWER_MOTORS, RGB_TOPICS,
    VOICE_CMD_TOPIC, VOICE_STATE_TOPIC, build_arg_parser, config_from_args,
    connect, format_all_motors, format_bms, format_compressed_image_meta,
    format_depth_image_meta, format_imu, format_voice_state_meta,
    hw_to_logical, logical_to_hw,
)


def _run_until_interrupt(label: str) -> None:
    print(f"{label} Press Ctrl+C to return to the menu.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nReturning to menu.")


def menu_rgb_image(middleware) -> None:
    """E1: RGB (compressed JPEG) image subscription -- saves frames to rgb_images/."""
    import os

    import cv2
    import numpy as np

    camera = input("Camera (front/back) [front]: ").strip().lower() or "front"
    topic = RGB_TOPICS.get(camera)
    if topic is None:
        print(f"Unknown camera '{camera}'. Use 'front' or 'back'.")
        return
    os.makedirs("rgb_images", exist_ok=True)

    def _callback(data) -> None:
        print(format_compressed_image_meta(data))
        np_arr = np.array(data.data(), dtype=np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image is not None:
            filename = f"rgb_images/rgb_{data.header().stamp().sec()}_{data.header().stamp().nanosec()}.png"
            cv2.imwrite(filename, image)
            print(f"Saved to {filename}")
        else:
            print("Failed to decode image!")

    middleware.subscribeCompressedImage(topic, _callback)
    _run_until_interrupt(f"Subscribed to {topic}.")


def menu_depth_image(middleware) -> None:
    """E2: Depth image subscription -- saves colorized frames to depth_images/."""
    import os

    import cv2
    import numpy as np

    camera = input("Camera (front/back) [front]: ").strip().lower() or "front"
    topic = DEPTH_TOPICS.get(camera)
    if topic is None:
        print(f"Unknown camera '{camera}'. Use 'front' or 'back'.")
        return
    os.makedirs("depth_images", exist_ok=True)
    qos_config = {"reliability": "best_effort", "history_kind": "keep_last", "history_depth": 5, "durability": "volatile"}

    def _callback(depth_msg) -> None:
        print(format_depth_image_meta(depth_msg))
        if "16UC1" in depth_msg.encoding():
            raw_data = np.array(depth_msg.data(), dtype=np.uint8)
            depth_img = raw_data.view(np.uint16).reshape((depth_msg.height(), depth_msg.width()))
            depth_vis = cv2.normalize(depth_img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            depth_color = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)
            filename = f"depth_images/depth_{depth_msg.header().stamp().sec()}_{depth_msg.header().stamp().nanosec()}.png"
            cv2.imwrite(filename, depth_color)
            print(f"Saved to {filename}")

    middleware.subscribeImage(topic, _callback, qos_config)
    _run_until_interrupt(f"Subscribed to {topic}.")


def menu_led_control(middleware) -> None:
    """E3: LED control. Requires kill_robot.py to have already been run
    against the robot's high-level gRPC address, or LED control has no effect."""
    print("!!! Run kill_robot.py (in sdk_playground or high_level/python) against the robot first, or this has no effect. !!!")
    print("Available lights:", ", ".join(LED_NAMES))
    name = input("Light name: ").strip()
    if name not in LED_NAMES:
        print(f"Unknown light '{name}'.")
        return
    r = int(input("R [0-255] (0 for fill_light1/3, on/off only): ") or "0")
    g = int(input("G [0-255]: ") or "0")
    b = int(input("B [0-255]: ") or "0")
    brightness = int(input("Brightness [0-255]: ") or "255")

    import dds_middleware_python as dds

    qos_config = {"reliability": "reliable", "history_kind": "keep_last", "history_depth": 1, "durability": "volatile"}
    middleware.createLedsCmdWriter(LEDS_CMD_TOPIC, qos_config)
    led = dds.LEDControl()
    led.name(name)
    led.mode(0)
    led.brightness(brightness)
    led.r(r)
    led.g(g)
    led.b(b)
    led.priority(0)
    cmd = dds.LedsCmd()
    cmd.leds([led])
    middleware.publishLedsCmd(cmd)
    print(f"Published: {name} r={r} g={g} b={b} brightness={brightness}")


def menu_imu(middleware) -> None:
    """E4: IMU subscription (live readout) -- rt/lower/state.imu_state()."""
    def _callback(state) -> None:
        print(format_imu(state.imu_state()))
        print("---")

    middleware.subscribeLowerState(LOWER_STATE_TOPIC, _callback)
    _run_until_interrupt(f"Subscribed to {LOWER_STATE_TOPIC} (IMU).")


def menu_motor_state(middleware) -> None:
    """E5: Motor state subscription (all 16 motors, live readout)."""
    def _callback(state) -> None:
        print(format_all_motors(state.motor_state()))
        print("---")

    middleware.subscribeLowerState(LOWER_STATE_TOPIC, _callback)
    _run_until_interrupt(f"Subscribed to {LOWER_STATE_TOPIC} (motors).")


def menu_battery(middleware) -> None:
    """E6: BMS/battery subscription (live readout) -- Python bindings only
    expose battery_level (see low_level.md's E6 note)."""
    def _callback(state) -> None:
        print(format_bms(state.bms_state()))
        print("---")

    middleware.subscribeLowerState(LOWER_STATE_TOPIC, _callback)
    _run_until_interrupt(f"Subscribed to {LOWER_STATE_TOPIC} (battery).")


def menu_voice_playback(middleware) -> None:
    """E7: Voice playback -- file mode only. Streaming mode (live mic
    capture -> PCM -> publish) needs an audio-capture library this tool
    doesn't vendor; file mode alone is enough to prove the pipeline."""
    import dds_middleware_python as dds

    qos_config = {"reliability": "reliable", "history_kind": "keep_last", "history_depth": 5, "durability": "volatile"}
    middleware.createVoiceCmdWriter(VOICE_CMD_TOPIC, qos_config)
    path = input("Audio file path ON THE ROBOT HOST (not this machine), e.g. /root/test.wav: ").strip()
    if not path:
        print("No path given.")
        return
    voice_cmd = dds.VoiceCmd()
    voice_cmd.type("file")
    voice_cmd.path(path)
    voice_cmd.data([])
    # DDS entity discovery takes ~100-1000ms; publishing immediately after
    # creating the writer can lose the message (see E7's own doc note).
    time.sleep(1)
    middleware.publishVoiceCmd(voice_cmd)
    print(f"Requested playback of {path}")


def menu_voice_capture(middleware) -> None:
    """E8: microphone capture -> WAV file. (The vendored SDK's own file on
    disk is named e8_voice_sub.py, but its internal docstring calls itself
    e9 -- a naming inconsistency in the SDK itself. This menu follows the
    E8 numbering from low_level.md and the actual file listing.)"""
    qos_config = {"reliability": "best_effort", "history_kind": "keep_last", "history_depth": 1, "durability": "volatile"}
    out_path = input("Output WAV path [voice_capture.wav]: ").strip() or "voice_capture.wav"
    wav_file = wave.open(out_path, "wb")
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(24000)

    def _callback(voice_state_msg) -> None:
        print(format_voice_state_meta(voice_state_msg))
        wav_file.writeframes(bytes(voice_state_msg.data_()))

    middleware.subscribeVoiceState(VOICE_STATE_TOPIC, _callback, qos_config)
    try:
        _run_until_interrupt(f"Subscribed to {VOICE_STATE_TOPIC}, writing to {out_path}.")
    finally:
        wav_file.close()
        print(f"Saved {out_path}")


def menu_raw_motor_command(middleware) -> None:
    """E9: raw joint PD control -- sinusoidal swing test.

    DANGER: requires the robot's main controller to already be killed
    (kill_robot.py), or the main controller and this program send
    conflicting commands to the same motors simultaneously -- control
    conflicts, unpredictable movement, hardware damage, personal injury.
    See low_level.md's E9 section for the full pre-execution checklist.
    """
    print("=" * 70)
    print("DANGER: raw motor command control.")
    print("You MUST have already run kill_robot.py against the robot before this.")
    print("Confirm: robot is on flat ground, area is clear of people, you have Ctrl+C ready.")
    print("=" * 70)
    confirm = input("Type MOTORCMD to proceed, anything else aborts: ").strip()
    if confirm != "MOTORCMD":
        print("Aborted.")
        return

    import dds_middleware_python as dds

    qos_config = {"reliability": "reliable", "history_kind": "keep_last", "history_depth": 1, "durability": "volatile"}
    middleware.createLowerCmdWriter(LOWER_CMD_TOPIC, qos_config)

    q_init = [0.0] * NUM_LOWER_MOTORS
    state = {"count": 0}

    def _collect_initial(lower_state) -> None:
        if state["count"] < 10:
            motor_states = lower_state.motor_state()
            for i in range(NUM_ACTUATED_MOTORS):
                hw = ABS2HW[i]
                q_init[hw] = hw_to_logical(motor_states, hw)
            state["count"] += 1

    middleware.subscribeLowerState(LOWER_STATE_TOPIC, _collect_initial)

    print("Collecting initial position...")
    waited = 0.0
    while state["count"] < 10 and waited < 5.0:
        time.sleep(0.01)
        waited += 0.01
    if state["count"] < 10:
        print("Did not receive enough lower_state messages -- aborting (is the robot connected?).")
        return
    print("Initial position collected:", [round(q_init[ABS2HW[i]], 4) for i in range(NUM_ACTUATED_MOTORS)])

    def _damp_cmd():
        cmd = dds.LowerCmd()
        for i in range(NUM_ACTUATED_MOTORS):
            hw = ABS2HW[i]
            cmd[hw].mode(0)
            cmd[hw].q(logical_to_hw(0.0, hw))
            cmd[hw].dq(0.0)
            cmd[hw].tau(0.0)
            cmd[hw].kp(0.0)
            cmd[hw].kd(0.5)
        return cmd

    def _swing_cmd(s: float):
        cmd = dds.LowerCmd()
        for i in range(NUM_ACTUATED_MOTORS):
            hw = ABS2HW[i]
            qdes = q_init[hw] + math.sin(2 * math.pi * s) * 0.2
            cmd[hw].mode(0)
            cmd[hw].q(logical_to_hw(qdes, hw))
            cmd[hw].dq(0.0)
            cmd[hw].tau(0.0)
            cmd[hw].kp(30.0)
            cmd[hw].kd(1.2)
        return cmd

    print("Starting swing test -- Ctrl+C to stop and enter damping mode.")
    try:
        for _ in range(10):
            middleware.publishLowerCmd(_damp_cmd())
            time.sleep(0.0022)
        for i in range(5000):
            middleware.publishLowerCmd(_swing_cmd(i / 500.0))
            time.sleep(0.0022)
        print("Swing complete, entering damping mode.")
    except KeyboardInterrupt:
        print("\nInterrupted, entering damping mode.")
    for _ in range(50):
        middleware.publishLowerCmd(_damp_cmd())
        time.sleep(0.0022)
    print("Done.")


MENU_HANDLERS = {
    "1": menu_rgb_image,
    "2": menu_depth_image,
    "3": menu_led_control,
    "4": menu_imu,
    "5": menu_motor_state,
    "6": menu_battery,
    "7": menu_voice_playback,
    "8": menu_voice_capture,
    "9": menu_raw_motor_command,
}


def _print_menu() -> None:
    print("\n=== RoverHub Low-Level SDK Playground ===")
    print("1) E1 RGB image subscribe (save frames)")
    print("2) E2 Depth image subscribe (save colorized frames)")
    print("3) E3 LED control")
    print("4) E4 IMU subscribe (live readout)")
    print("5) E5 Motor state subscribe (16 motors, live readout)")
    print("6) E6 Battery/BMS subscribe (live readout)")
    print("7) E7 Voice playback (file mode)")
    print("8) E8 Voice capture (save to WAV)")
    print("9) E9 Raw motor command test (DANGER -- requires kill_robot.py first)")
    print("0) Quit")


def run(config) -> None:
    middleware = connect(config)
    print("Connected to DDS middleware.")
    while True:
        _print_menu()
        choice = input("> ").strip()
        if choice == "0":
            break
        handler = MENU_HANDLERS.get(choice)
        if handler is None:
            print("Unknown option.")
            continue
        try:
            handler(middleware)
        except ValueError as exc:
            print(f"Invalid input: {exc}")
        except KeyboardInterrupt:
            print("\nCancelled.")


def main() -> None:
    parser = build_arg_parser("RoverHub Low-Level SDK Playground - menu-driven DDS feature tester")
    args = parser.parse_args()
    config = config_from_args(args)
    run(config)


if __name__ == "__main__":
    main()
