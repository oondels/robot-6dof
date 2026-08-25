import argparse

from scservo_sdk import PortHandler, sms_sts

from src.actions.router import execute_action
from src.application import Joint, RobotArm, ServoBus
from src.infrastructure.scservo_bus import ScServoBus
from robot_config import JOINT_CONFIGS

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 1_000_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlador do Braço Robótico 6-DOF.")
    parser.add_argument(
        "--action",
        default="status",
        help="Ação a ser executada: status, test, mirror, list ou <nome_da_acao_gravada> (padrão: 'status')",
    )
    parser.add_argument("--port", default=DEFAULT_PORT, help="Porta serial de comunicação")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE, help="Taxa de transmissão em baud")
    return parser.parse_args()


def create_arm(servo_bus: ServoBus) -> RobotArm:
    """Compõe o braço usando um único barramento compartilhado."""
    joints = [
        Joint(
            servo_bus=servo_bus,
            config=config,
        )
        for config in JOINT_CONFIGS
    ]
    return RobotArm(servo_bus=servo_bus, joints=joints)


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

    # Ação de listagem não requer abertura de hardware
    if args.action == "list":
        execute_action("list")
        return

    # ! TODO: Mover para apos a criacao da instancia do RobotArm, pois a calibracao precisa de hardware
    # *: Fazer correta configuracao da acao calibrate para recener como instancia nos args RobotArm
    if args.action == "calibrate":
        execute_action("calibrate")
        return

    # Demais ações requerem configuração de juntas e hardware
    if not JOINT_CONFIGS:
        raise RuntimeError(
            "Nenhuma junta calibrada. "
            "Preencha JOINT_CONFIGS somente depois "
            "da calibração física."
        )

    port = PortHandler(args.port)
    sdk_servo = sms_sts(port)
    servo_bus = ScServoBus(sdk_servo)

    try:
        if not port.openPort():
            raise RuntimeError(f"Erro abrindo a porta {args.port}")

        if not port.setBaudRate(args.baudrate):
            raise RuntimeError(f"Erro configurando baudrate {args.baudrate}")
        
        # Cria objeto RobotArm com as juntas configuradas
        arm = create_arm(servo_bus)

        if args.action == "status":
            print_arm_status(arm)
        else:
            execute_action(args.action, arm)

    finally:
        port.closePort()


if __name__ == "__main__":
    main()
