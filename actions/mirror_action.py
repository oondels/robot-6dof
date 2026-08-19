import time
from collections.abc import Callable
from typing import Any

from pathlib import Path
import json

from scservo_sdk import PortHandler, sms_sts

from models.Joint import Joint
from models.RobotArm import RobotArm
from robot_config import JOINT_CONFIGS

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 1_000_000

# Poses pré-programadas seguras de teste
HOME_POSE: dict[str, dict[str, float]] = {
    "home": {
        "base_yaw": 0.0,
        "shoulder_pitch": 0.0,
        "elbow_pitch": 0.0,
        "wrist_pitch": 0.0,
        "wrist_roll": 0.0,
        "gripper": 0.0,
    }
}

SAVE_FILE_NAME = "mirror_positions.json"
SAVE_PATH = Path(__file__).parent / "data" / "mirror_results" / SAVE_FILE_NAME


def set_robot_home_pose(
    arm: RobotArm,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Move o braço robótico para a pose 'home' (todos os ângulos em 0.0°)."""
    home_angles = HOME_POSE["home"]

    try:
        arm.enable_torque()
        joint_status = arm.move_pose(home_angles, timeout=8.0)
        for name, st in joint_status.items():
            joint = arm[name]
            ang = joint.position_to_angle(st.current_position)
            output_fn(
                f"   * {name}: {ang:.2f}° (alvo={st.target_position}, "
                f"pos={st.current_position}, erro={st.position_error} counts)"
            )

        output_fn("Braço robótico movido para a pose 'home'.")
    except Exception as e:
        output_fn(f"ERRO durante a execução da pose: {e}")


def save_result(mirror_positions):
    """Salva os resultados de espelhamento em JSON."""
    try:
        SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(mirror_positions, f, indent=4)

        print(f"Resultados salvos em: {SAVE_PATH}")

    except Exception as e:
        print(f"Falha ao salvar resultados: {e}")
        raise


def load_mirror_result():
    """Carrega os resultados de espelhamento salvos em JSON."""
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            mirror_positions = json.load(f)

        print(f"Resultados carregados de: {SAVE_PATH}")
        return mirror_positions

    except FileNotFoundError:
        print(f"Nenhum arquivo de resultados encontrado em: {SAVE_PATH}")
        return None
    except Exception as e:
        print(f"Falha ao carregar resultados: {e}")
        raise


def replay_trajectory(
    arm: RobotArm,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Testa a ação de espelhamento."""
    output_fn("\n\nIniciando a ação de espelhamento...\n\n")
    trajectory = load_mirror_result()
    if trajectory is None:
        output_fn("Nenhum resultado de espelhamento encontrado para teste.")
        return

    output_fn(
        "Resultados de espelhamento carregados com sucesso. Colocando Braco na posição Home..."
    )

    reset_position = input_fn(
        "\n\nPosicao espelhamento salvo, deseja voltar a posicao inicial para replicar o teste? (s/n): "
    )
    if not reset_position.strip().lower() in ("s", "sim", "y", "yes"):
        output_fn("PlayBack cancelado pelo operador.")
        return
    
    time.sleep(1)  # Tempo de segurança antes de mover o braço
    set_robot_home_pose(arm, output_fn=output_fn)

    if not arm.is_torque_enabled:
        arm.enable_torque()

    question = input_fn(
        "\nTorque Habilitado e Braço na Posição Home. Deseja iniciar o PlayBack da acao gravada? (s/n): "
    )
    if not question.strip().lower() in ("s", "sim", "y", "yes"):
        output_fn("PlayBack cancelado pelo operador.")
        return

    start_playback_time = time.monotonic()
    for i in range(1, len(trajectory)):
        target_angles = trajectory[i]["angles"]
        target_time = trajectory[i]["time"]  # tempo relativo original

        # Envia a pose sincronizada para todas as juntas
        arm.command_pose(target_angles)

        # Calcula quanto tempo real deve esperar até o próximo waypoint
        # usando time.monotonic() para evitar drift acumulado
        elapsed = time.monotonic() - start_playback_time
        time_to_wait = target_time - elapsed

        if time_to_wait > 0:
            time.sleep(time_to_wait)


def run_mirror_action(
    arm: RobotArm,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    test_mov = False

    """Ação placeholder para espelhamento ou gravação/reprodução de movimentos."""
    output_fn("==================================================")
    output_fn("Função de Espelhamento — Braço Robótico (6-DOF)")
    output_fn("Juntas monitoradas: " + ", ".join(arm.joint_names))
    output_fn("==================================================")

    if not test_mov:
        current_angles = arm.current_angles()
        output_fn("\nEstado angular atual do braço:")
        for name, ang in current_angles.items():
            output_fn(f"  - {name}: {ang:.2f}°")

        warn = input_fn(
            "\nAviso: O robo irá se mover para a posição Default (home), certifique-se de que não há obstáculos. Deseja continuar? (s/n): "
        )
        if warn.strip().lower() not in ("s", "sim", "y", "yes"):
            output_fn("Ação de espelhamento cancelada pelo operador.")
            return

        set_robot_home_pose(arm, output_fn=output_fn)

        confirm = input_fn(
            "\nTorque será desabilitado para grava posição, concorda? (s/n): "
        )
        if confirm.strip().lower() not in ("s", "sim", "y", "yes"):
            output_fn(
                "Ação de espelhamento cancelada pelo operador antes de desabilitar torque."
            )
            return

    ANGLE_BASE_TOLERANCE = 2.5
    STOP_RECORD_TIME_TOLERANCE = 10
    RECORD_TIME_GAP = 0.3
    arm.disable_torque()

    mirror_positions: list[dict[str, Any]] = []

    recording = True
    start_time = None
    last_motion_time = None
    last_angles = arm.current_angles()

    while recording:
        now = time.monotonic()
        current_angles = arm.current_angles()

        moved = any(
            abs(current_angles[name] - last_angles[name]) > ANGLE_BASE_TOLERANCE
            for name in arm.joint_names
        )

        if moved:
            if start_time is None:
                start_time = now

            last_motion_time = now

            mirror_positions.append(
                {
                    "time": now - start_time,
                    "angles": current_angles.copy(),
                }
            )

            last_angles = current_angles.copy()

            output_fn(f"Movimento detectado -> registrando pose")

        if (
            start_time is not None
            and last_motion_time is not None
            and now - last_motion_time >= STOP_RECORD_TIME_TOLERANCE
        ):
            output_fn("Braço parado. Finalizando gravação.")
            arm.disable_torque()
            recording = False

            save_result(mirror_positions)
            break

        time.sleep(RECORD_TIME_GAP)

    replay_trajectory(arm)
