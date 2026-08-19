import argparse
from typing import Any

from scservo_sdk import PortHandler, sms_sts

from actions.router import execute_action
from models.Joint import Joint
from models.RobotArm import RobotArm
from robot_config import JOINT_CONFIGS

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 1_000_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlador do Braço Robótico 6-DOF.")
    parser.add_argument(
        "--action",
        choices=["status", "test", "mirror"],
        default="status",
        help="Ação a ser executada pelo robô (padrão: 'status')",
    )
    parser.add_argument("--port", default=DEFAULT_PORT, help="Porta serial de comunicação")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE, help="Taxa de transmissão em baud")
    return parser.parse_args()


def create_arm(servo: Any) -> RobotArm:
    joints = [
        Joint(
            servo=servo,
            config=config,
        )
        for config in JOINT_CONFIGS
    ]
    return RobotArm(joints)


def print_arm_status(arm: RobotArm) -> None:
    print("=== Estado Atual do Braço Robótico (6-DOF) ===")
    for joint in arm.joints:
        print(
            f"- {joint.name} (ID {joint.servo_id}): "
            f"posição={joint.current_position()} counts | "
            f"ângulo={joint.current_angle():.2f}°"
        )


def main() -> None:
    args = parse_args()

    if not JOINT_CONFIGS:
        raise RuntimeError(
            "Nenhuma junta calibrada. "
            "Preencha JOINT_CONFIGS somente depois "
            "da calibração física."
        )

    port = PortHandler(args.port)
    servo = sms_sts(port)

    try:
        if not port.openPort():
            raise RuntimeError(f"Erro abrindo a porta {args.port}")

        if not port.setBaudRate(args.baudrate):
            raise RuntimeError(f"Erro configurando baudrate {args.baudrate}")

        arm = create_arm(servo)

        if args.action == "status":
            print_arm_status(arm)
        else:
            execute_action(args.action, arm)

    finally:
        port.closePort()


if __name__ == "__main__":
    main()
