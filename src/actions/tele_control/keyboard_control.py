import time
from typing import Sequence

from scservo_sdk import PortHandler, sms_sts

from pynput import keyboard

from src.infrastructure.input.keyboard_input import KeyBoardInput, KeyBinding

from src.infrastructure.scservo_bus import ScServoBus

from src.application.joint_config import JointConfig
from src.application.joint import Joint
from src.application.robot_arm import RobotArm

from src.actions.home_pose import move_arm_to_home

KEYBOARD_BINDINGS = (
    KeyBinding(
        name="move_forward",
        key=keyboard.KeyCode.from_char("w"),
    ),
    KeyBinding(
        name="move_backward",
        key=keyboard.KeyCode.from_char("s"),
    ),
    KeyBinding(
        name="move_left",
        key=keyboard.KeyCode.from_char("a"),
    ),
    KeyBinding(
        name="move_right",
        key=keyboard.KeyCode.from_char("d"),
    ),
    KeyBinding(
        name="emergency_stop",
        key=keyboard.Key.esc,
    ),
    KeyBinding(
        name="open_gripper",
        key=keyboard.KeyCode.from_char("t"),
    ),
    KeyBinding(
        name="close_gripper",
        key=keyboard.KeyCode.from_char("g"),
    ),
)

JOINT_CONFIGS: Sequence[JointConfig] = (
    JointConfig(
        name="base_yaw",
        servo_id=1,
        zero_position=2065,
        direction=1,
        min_angle=-105.0,
        max_angle=100.0,
        speed=400,
        acc=30,
        tolerance_deg=1.3,
    ),
    JointConfig(
        name="shoulder_pitch",
        servo_id=2,
        zero_position=2050,
        direction=1,
        min_angle=-1.0,
        max_angle=165.0,
        speed=400,
        acc=30,
        tolerance_deg=1.8,
    ),
    JointConfig(
        name="elbow_pitch",
        servo_id=3,
        zero_position=2033,
        direction=-1,
        min_angle=-1.0,
        max_angle=155.0,
        speed=400,
        acc=30,
        tolerance_deg=5,
    ),
    JointConfig(
        name="wrist_pitch",
        servo_id=4,
        zero_position=2060,
        direction=-1,
        min_angle=-1.0,
        max_angle=155.0,
        speed=400,
        acc=30,
        tolerance_deg=1.8,
    ),
    JointConfig(
        name="wrist_roll",
        servo_id=5,
        zero_position=2164,
        direction=-1,
        min_angle=-160.0,
        max_angle=160.0,
        speed=400,
        acc=30,
        tolerance_deg=1.8,
    ),
    JointConfig(
        name="gripper",
        servo_id=6,
        zero_position=2041,
        direction=1,
        min_angle=-1.0,
        max_angle=110.0,
        speed=400,
        acc=30,
        tolerance_deg=2,
    ),
)

JOG_SPEED_DEG_S = 30.0  # Velocidade de movimento em graus por segundo


def run_control_loop(arm: RobotArm, keyboard: KeyBoardInput):
    arm.enable_torque()
    target_angles = arm.current_angles()

    last_time = time.monotonic()

    while True:
        current_time = time.monotonic()
        delta_time = current_time - last_time
        last_time = current_time

        state = keyboard.read()

        # Parada de Emergência: desabilita torque e sai do loop
        if state.emergency_stop or "emergency_stop" in state.buttons_pressed:
            print(
                "[ALERTA] Parada de emergência acionada!"
            )  # TODO: Configurar logger apropriado
            arm.disable_torque()
            break

        # Movimento contínuo controlado (held button)
        target_changed = False

        if "move_left" in state.buttons_held:
            target_angles["base_yaw"] += JOG_SPEED_DEG_S * delta_time
            target_changed = True

        if "move_right" in state.buttons_held:
            target_angles["base_yaw"] -= JOG_SPEED_DEG_S * delta_time
            target_changed = True

        if "move_forward" in state.buttons_held:
            target_angles["shoulder_pitch"] += JOG_SPEED_DEG_S * delta_time
            target_angles["elbow_pitch"] += JOG_SPEED_DEG_S * delta_time
            target_angles["wrist_pitch"] += JOG_SPEED_DEG_S * delta_time
            target_changed = True

        if "move_backward" in state.buttons_held:
            target_angles["shoulder_pitch"] -= JOG_SPEED_DEG_S * delta_time
            target_angles["elbow_pitch"] -= JOG_SPEED_DEG_S * delta_time
            target_angles["wrist_pitch"] -= JOG_SPEED_DEG_S * delta_time
            target_changed = True

        if "open_gripper" in state.buttons_held:
            target_angles["gripper"] += JOG_SPEED_DEG_S * delta_time
            target_changed = True

        if "close_gripper" in state.buttons_held:
            target_angles["gripper"] -= JOG_SPEED_DEG_S * delta_time
            target_changed = True

        # Movimento não bloqueante com `command` para cada junta
        if target_changed:
            for joint_name, desired_angle in target_angles.items():
                joint = arm.joint(joint_name)

                # Garante que não ultrapassa os limites físicos (Limitando os angulos ao limite máximo e mínimo da junta)
                clamped_angle = max(
                    joint.config.min_angle, min(joint.config.max_angle, desired_angle)
                )
                target_angles[joint_name] = clamped_angle

                # Envio não-bloqueante para o hardware
                joint.command(clamped_angle)


def keyboard_control():
    keyboard = KeyBoardInput(KEYBOARD_BINDINGS)
    keyboard.open()

    port = PortHandler("/dev/ttyUSB0")
    port.openPort()
    port.setBaudRate(1_000_000)

    servo = sms_sts(port)
    servo_bus = ScServoBus(servo)

    joints = [Joint(config, servo_bus) for config in JOINT_CONFIGS]

    arm = RobotArm(servo_bus=servo_bus, joints=joints)

    try:
        run_control_loop(arm, keyboard)

    except KeyboardInterrupt:
        print("\n[AUDIT] Encerrando monitor...")
    finally:
        # Colocar braço em pose home
        move_arm_to_home(arm, output_fn=print)
        
        keyboard.close()
        port.closePort()
        
        


if __name__ == "__main__":
    keyboard_control()
