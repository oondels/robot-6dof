import argparse
from collections.abc import Callable
from typing import Any

from scservo_sdk import PortHandler, sms_sts

from src.models.Joint import Joint
from src.models.joint_config import JointConfig
from robot_config import JOINT_CONFIGS

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 1_000_000


def find_joint_config(name_or_id: str | int) -> JointConfig:
    for config in JOINT_CONFIGS:
        if isinstance(name_or_id, int) and config.servo_id == name_or_id:
            return config
        if isinstance(name_or_id, str):
            if name_or_id.isdigit() and config.servo_id == int(name_or_id):
                return config
            if config.name.lower() == name_or_id.strip().lower():
                return config

    raise ValueError(f"Nenhuma junta calibrada encontrada para '{name_or_id}'.")


def run_motion_test(
    joint: Joint,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    output_fn("==================================================")
    output_fn(f"Teste de Movimento Controlado — Junta '{joint.name}' (ID {joint.servo_id})")
    output_fn(f"Limites operacionais: [{joint.config.min_angle:.1f}°, {joint.config.max_angle:.1f}°]")
    output_fn(f"Velocidade={joint.speed} | Aceleração={joint.acc} | Tolerância={joint.config.tolerance_deg:.1f}°")
    output_fn("==================================================")

    current_pos = joint.current_position()
    current_ang = joint.current_angle()
    output_fn(f"Estado inicial: posição={current_pos} counts, ângulo={current_ang:.2f}°")

    confirm = input_fn("Deseja habilitar o torque para iniciar o teste? (s/n): ")
    if confirm.strip().lower() not in ("s", "sim", "y", "yes"):
        output_fn("Teste cancelado pelo operador antes de habilitar o torque.")
        return

    joint.enable_torque()

    try:
        while True:
            cmd = input_fn(
                f"\nDigite o ângulo alvo em graus [{joint.config.min_angle:.1f}° a {joint.config.max_angle:.1f}°] "
                "ou 'q' para sair: "
            )

            if cmd.strip().lower() == "q":
                break

            try:
                target_angle = float(cmd.strip())
            except ValueError:
                output_fn("Valor inválido. Digite um número decimal para o ângulo ou 'q' para sair.")
                continue

            if not (joint.config.min_angle <= target_angle <= joint.config.max_angle):
                output_fn(
                    f"Ângulo {target_angle:.2f}° fora dos limites permitidos "
                    f"[{joint.config.min_angle:.1f}°, {joint.config.max_angle:.1f}°]."
                )
                continue

            output_fn(f"Movendo '{joint.name}' para {target_angle:.2f}°...")
            status = joint.move(angle=target_angle, timeout=5.0)

            output_fn(
                f"-> Chegada confirmada! Posição={status.current_position} counts, "
                f"Ângulo={joint.position_to_angle(status.current_position):.2f}°, "
                f"Erro={status.position_error} counts (Tolerância={joint.config.tolerance_counts} counts)"
            )

    finally:
        disable_confirm = input_fn("\nDeseja desabilitar o torque antes de fechar? (s/n): ")
        if disable_confirm.strip().lower() in ("s", "sim", "y", "yes"):
            joint.disable_torque()
        else:
            output_fn("Atenção: torque mantido habilitado por opção do operador.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa testes de movimento individual e controlado em uma junta calibrada."
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument(
        "--joint",
        default="gripper",
        help="Nome ou ID da junta configurada em robot_config.py (padrão: 'gripper')",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = find_joint_config(args.joint)

    port = PortHandler(args.port)
    servo = sms_sts(port)

    try:
        if not port.openPort():
            raise RuntimeError(f"Erro abrindo a porta {args.port}")

        if not port.setBaudRate(args.baudrate):
            raise RuntimeError(f"Erro configurando baudrate {args.baudrate}")

        joint = Joint(servo=servo, config=config)
        run_motion_test(joint)

    except KeyboardInterrupt:
        print("\nOperação interrompida pelo operador.")
    finally:
        port.closePort()


if __name__ == "__main__":
    main()
