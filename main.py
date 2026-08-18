from typing import Any

from scservo_sdk import PortHandler, sms_sts

from models.Joint import Joint
from models.RobotArm import RobotArm
from robot_config import JOINT_CONFIGS

PORT = "/dev/ttyUSB0"
BAUDRATE = 1_000_000


def create_arm(servo: Any) -> RobotArm:
    joints = [
        Joint(
            servo=servo,
            config=config,
        )
        for config in JOINT_CONFIGS
    ]
    return RobotArm(joints)


def main() -> None:
    if not JOINT_CONFIGS:
        raise RuntimeError(
            "Nenhuma junta calibrada. "
            "Preencha JOINT_CONFIGS somente depois "
            "da calibração física."
        )

    port = PortHandler(PORT)
    servo = sms_sts(port)

    try:
        if not port.openPort():
            raise RuntimeError(f"Erro abrindo a porta {PORT}")

        if not port.setBaudRate(BAUDRATE):
            raise RuntimeError(f"Erro configurando baudrate {BAUDRATE}")

        arm = create_arm(servo)
        print("=== Estado Atual do Braço Robótico (6-DOF) ===")
        for joint in arm.joints:
            print(
                f"- {joint.name} (ID {joint.servo_id}): "
                f"posição={joint.current_position()} counts | "
                f"ângulo={joint.current_angle():.2f}°"
            )

    finally:
        port.closePort()


if __name__ == "__main__":
    main()
