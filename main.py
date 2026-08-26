import argparse
from collections.abc import Sequence

from scservo_sdk import PortHandler, sms_sts

from src.actions.router import execute_action
from src.application import Joint, RobotArm, ServoBus
from src.infrastructure.scservo_bus import ScServoBus
from robot_config import JOINT_CONFIGS

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 1_000_000
HARDWARE_FREE_ACTIONS = frozenset({"list"})
STATUS_ACTION = "status"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Lê os parâmetros da interface de linha de comando."""
    parser = argparse.ArgumentParser(description="Controlador do Braço Robótico 6-DOF.")
    parser.add_argument(
        "--action",
        default="status",
        help=(
            "Ação a ser executada: status, list, test, mirror, calibrate "
            "ou <nome_da_acao_gravada> (padrão: 'status')"
        ),
    )
    parser.add_argument(
        "--port", default=DEFAULT_PORT, help="Porta serial de comunicação"
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=DEFAULT_BAUDRATE,
        help="Taxa de transmissão em baud",
    )
    return parser.parse_args(argv)


def create_arm(servo_bus: ServoBus) -> RobotArm:
    """Compõe o braço usando um único barramento compartilhado."""
    joints = [Joint(servo_bus=servo_bus, config=config) for config in JOINT_CONFIGS]
    return RobotArm(servo_bus=servo_bus, joints=joints)


def print_arm_status(arm: RobotArm) -> None:
    print("=== Estado Atual do Braço Robótico (6-DOF) ===")
    for joint in arm.joints:
        print(
            f"- {joint.name} (ID {joint.servo_id}): "
            f"posição={joint.current_position()} counts | "
            f"ângulo={joint.current_angle():.2f}°"
        )


def normalize_action(action: str) -> str:
    """Normaliza a ação recebida pela CLI antes do despacho."""
    return action.strip().lower()


def validate_robot_configuration() -> None:
    """Garante que há juntas calibradas antes de usar o hardware."""
    if not JOINT_CONFIGS:
        raise RuntimeError(
            "Nenhuma junta calibrada. "
            "Preencha JOINT_CONFIGS somente depois "
            "da calibração física."
        )


def connect_servo_bus(port_name: str, baudrate: int) -> tuple[PortHandler, ServoBus]:
    """Abre e configura a conexão serial usada pelo braço.

    O chamador é responsável por sempre fechar a porta retornada.
    """
    port = PortHandler(port_name)

    if not port.openPort():
        port.closePort()
        raise RuntimeError(f"Erro abrindo a porta {port_name}")

    if not port.setBaudRate(baudrate):
        port.closePort()
        raise RuntimeError(f"Erro configurando baudrate {baudrate}")

    return port, ScServoBus(sms_sts(port))


def dispatch_robot_action(action: str, arm: RobotArm) -> None:
    """Executa ações que dependem de uma instância já inicializada do braço."""
    if action == STATUS_ACTION:
        print_arm_status(arm)
        return

    execute_action(action, arm)


def run_hardware_action(action: str, port_name: str, baudrate: int) -> None:
    """Executa uma ação mantendo o ciclo de vida da serial em um só lugar."""
    validate_robot_configuration()
    port, servo_bus = connect_servo_bus(port_name, baudrate)

    try:
        arm = create_arm(servo_bus)
        dispatch_robot_action(action, arm)
    finally:
        port.closePort()


def main() -> None:
    """Ponto de entrada da aplicação: CLI, boot e despacho de ações."""
    args = parse_args()
    action = normalize_action(args.action)

    # Ações que não dependem de hardware podem ser executadas sem inicializar o braço
    if action in HARDWARE_FREE_ACTIONS:
        execute_action(action)
        return

    run_hardware_action(action, args.port, args.baudrate)


if __name__ == "__main__":
    main()
