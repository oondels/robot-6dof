from typing import Any

from scservo_sdk import PortHandler, sms_sts

from models.Joint import Joint
from robot_config import JOINT_CONFIGS

PORT = "/dev/ttyUSB0"
BAUDRATE = 1_000_000


def create_joints(servo: Any) -> list[Joint]:
    return [
        Joint(
            servo=servo,
            config=config,
        )
        for config in JOINT_CONFIGS
    ]


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
            raise RuntimeError(f"Erro configurando baudrate " f"{BAUDRATE}")

        joints = create_joints(servo)

        for joint in joints:
            print(
                f"{joint.name}: "
                f"posição={joint.current_position()} "
                f"ângulo={joint.current_angle():.2f}°"
            )

    finally:
        port.closePort()


if __name__ == "__main__":
    main()
