import argparse
from collections.abc import Callable
from typing import Any

from scservo_sdk import PortHandler, sms_sts

from models.Joint import Joint
from models.RobotArm import RobotArm
from robot_config import JOINT_CONFIGS

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 1_000_000

# Poses pré-programadas seguras de teste
PRESET_POSES: dict[str, dict[str, float]] = {
    "home": {
        "base_yaw": 0.0,
        "shoulder_pitch": 0.0,
        "elbow_pitch": 0.0,
        "wrist_pitch": 0.0,
        "wrist_roll": 0.0,
        "gripper": 0.0,
    },
    "wave_small": {
        "base_yaw": 15.0,
        "shoulder_pitch": 20.0,
        "elbow_pitch": 20.0,
        "wrist_pitch": 10.0,
        "wrist_roll": 20.0,
        "gripper": 30.0,
    },
}


def run_pose_tester(
    arm: RobotArm,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    output_fn("==================================================")
    output_fn("Teste de Poses Sincronizadas — Braço Robótico (6-DOF)")
    output_fn("Juntas monitoradas: " + ", ".join(arm.joint_names))
    output_fn("==================================================")

    current_angles = arm.current_angles()
    output_fn("\nEstado angular atual do braço:")
    for name, ang in current_angles.items():
        output_fn(f"  - {name}: {ang:.2f}°")

    confirm = input_fn("\nDeseja habilitar o torque de todo o braço para iniciar o teste? (s/n): ")
    if confirm.strip().lower() not in ("s", "sim", "y", "yes"):
        output_fn("Teste cancelado pelo operador antes de habilitar torque.")
        return

    arm.enable_torque()

    try:
        while True:
            output_fn("\nOpções de pose:")
            output_fn("  1: Pose 'home' (todos os ângulos em 0.0°)")
            output_fn("  2: Pose 'wave_small' (pequeno movimento suave de demonstração)")
            output_fn("  c: Customizada (digitar o ângulo de cada junta)")
            output_fn("  q: Sair")

            choice = input_fn("\nEscolha uma opção: ").strip().lower()

            if choice == "q":
                break

            target_pose: dict[str, float] = {}

            if choice == "1":
                target_pose = PRESET_POSES["home"]
            elif choice == "2":
                target_pose = PRESET_POSES["wave_small"]
            elif choice == "c":
                output_fn("\nDigite os ângulos para cada junta:")
                cancelled = False
                for joint in arm.joints:
                    prompt = (
                        f"  {joint.name} [{joint.config.min_angle:.1f}° a "
                        f"{joint.config.max_angle:.1f}°]: "
                    )
                    raw_val = input_fn(prompt)
                    try:
                        ang = float(raw_val.strip())
                        target_pose[joint.name] = ang
                    except ValueError:
                        output_fn(f"Valor inválido digitado para {joint.name}. Pose cancelada.")
                        cancelled = True
                        break
                if cancelled:
                    continue
            else:
                output_fn("Opção inválida.")
                continue

            try:
                output_fn("\nValidando e enviando pose sincronizada via SyncWrite...")
                statuses = arm.move_pose(target_pose, timeout=8.0)
                output_fn("-> Pose alcançada com sucesso por todas as juntas!")
                for name, st in statuses.items():
                    joint = arm[name]
                    ang = joint.position_to_angle(st.current_position)
                    output_fn(
                        f"   * {name}: {ang:.2f}° (alvo={st.target_position}, "
                        f"pos={st.current_position}, erro={st.position_error} counts)"
                    )
            except Exception as e:
                output_fn(f"ERRO durante a execução da pose: {e}")

    finally:
        disable_confirm = input_fn("\nDeseja desabilitar o torque de todas as juntas? (s/n): ")
        if disable_confirm.strip().lower() in ("s", "sim", "y", "yes"):
            arm.disable_torque()
        else:
            output_fn("Atenção: torque mantido habilitado.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Testador interativo de poses sincronizadas com SyncWrite para o braço 6-DOF."
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not JOINT_CONFIGS:
        raise RuntimeError("Nenhuma junta configurada em robot_config.py.")

    port = PortHandler(args.port)
    servo = sms_sts(port)

    try:
        if not port.openPort():
            raise RuntimeError(f"Erro abrindo a porta {args.port}")

        if not port.setBaudRate(args.baudrate):
            raise RuntimeError(f"Erro configurando baudrate {args.baudrate}")

        joints = [Joint(servo=servo, config=cfg) for cfg in JOINT_CONFIGS]
        arm = RobotArm(joints)

        run_pose_tester(arm)

    except KeyboardInterrupt:
        print("\nOperação interrompida pelo operador.")
    finally:
        port.closePort()


if __name__ == "__main__":
    main()
