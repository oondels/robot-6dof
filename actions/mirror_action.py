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
    """[Modo 1 - Original do Usuário] Reproduz a trajetória gravada em tempo real com pausas humanas."""
    output_fn("\n\nIniciando a ação de espelhamento (Modo 1 - Original)...\n\n")
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

    if not arm.is_torque_enabled():
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
    arm.disable_torque()
    output_fn("PlayBack da ação de espelhamento concluído.")


# ==============================================================================
# [MODO 2 ADICIONAL] Pipeline de Suavização e Reamostragem com Velocidade Constante
# ==============================================================================


def generate_smooth_trajectory(
    trajectory: list[dict[str, Any]],
    target_speed_deg_s: float = 35.0,
    sample_interval: float = 0.04,
) -> list[dict[str, Any]]:
    """Gera uma nova trajetória reamostrada com velocidade angular constante e interpolação linear densa.

    Matemática aplicada:
    1. Filtro de Ruído: Remove pontos consecutivos com variação angular desprezível (< 0.2°).
    2. Reamostragem por Arco: O tempo de cada trecho é recalculado como (Δθ_max / target_speed),
       eliminando pausas e hesitações manuais gravadas acidentalmente.
    3. Interpolação a 25 Hz (40ms): Cria waypoints intermediários a cada sample_interval para garantir
       que o envio via SyncWrite seja contínuo e sem degraus/trancos.

    Args:
        trajectory: Lista de poses brutas gravadas [{"time": float, "angles": dict[str, float]}].
        target_speed_deg_s: Velocidade angular da junta líder em graus/s (padrão: 35°/s).
        sample_interval: Período de amostragem em segundos (padrão: 0.04s = 25Hz).

    Returns:
        Nova lista de waypoints suavizados e interpolados.
    """
    if not trajectory:
        return []

    if len(trajectory) == 1:
        return [{"time": 0.0, "angles": trajectory[0]["angles"].copy()}]

    # 1. Filtra waypoints redundantes (ruído estático de encoder < 0.2°)
    clean_waypoints = [trajectory[0]]
    for wp in trajectory[1:]:
        last_angles = clean_waypoints[-1]["angles"]
        curr_angles = wp["angles"]
        max_delta = max(
            abs(curr_angles[name] - last_angles[name]) for name in curr_angles
        )
        if max_delta >= 0.2:
            clean_waypoints.append(wp)

    if len(clean_waypoints) == 1:
        return [{"time": 0.0, "angles": clean_waypoints[0]["angles"].copy()}]

    # 2. Recalcula os tempos de cada trecho para velocidade angular constante
    cumulative_times: list[float] = [0.0]
    total_time = 0.0

    for i in range(1, len(clean_waypoints)):
        prev_angles = clean_waypoints[i - 1]["angles"]
        curr_angles = clean_waypoints[i]["angles"]
        # Junta líder: a que percorre a maior amplitude angular no trecho
        max_delta = max(
            abs(curr_angles[name] - prev_angles[name]) for name in curr_angles
        )
        # Duração necessária para percorrer max_delta a target_speed_deg_s
        duration = max(sample_interval, max_delta / target_speed_deg_s)
        total_time += duration
        cumulative_times.append(total_time)

    # 3. Interpolação de alta densidade a 25 Hz (sample_interval = 0.04s)
    smooth_trajectory: list[dict[str, Any]] = []
    current_time = 0.0
    joint_names = list(clean_waypoints[0]["angles"].keys())
    num_segments = len(clean_waypoints) - 1
    seg_idx = 0

    while current_time <= total_time + 1e-6:
        # Avança para o segmento correspondente ao tempo atual
        while (
            seg_idx < num_segments - 1 and current_time > cumulative_times[seg_idx + 1]
        ):
            seg_idx += 1

        t_start = cumulative_times[seg_idx]
        t_end = cumulative_times[seg_idx + 1]
        seg_duration = t_end - t_start

        if seg_duration > 0:
            alpha = (current_time - t_start) / seg_duration
            alpha = max(0.0, min(1.0, alpha))
        else:
            alpha = 1.0

        p_start = clean_waypoints[seg_idx]["angles"]
        p_end = clean_waypoints[seg_idx + 1]["angles"]

        # Interpolação linear (LERP) para cada uma das 6 juntas
        interpolated_angles = {
            name: p_start[name] + alpha * (p_end[name] - p_start[name])
            for name in joint_names
        }

        smooth_trajectory.append(
            {
                "time": round(current_time, 4),
                "angles": interpolated_angles,
            }
        )

        current_time += sample_interval

    # Garante que a última pose exata esteja presente
    last_expected_pose = clean_waypoints[-1]["angles"]
    if smooth_trajectory and smooth_trajectory[-1]["angles"] != last_expected_pose:
        smooth_trajectory.append(
            {
                "time": round(total_time, 4),
                "angles": last_expected_pose.copy(),
            }
        )

    return smooth_trajectory


def replay_smooth_trajectory(
    arm: RobotArm,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    target_speed_deg_s: float = 35.0,
    sample_interval: float = 0.04,
) -> None:
    """[Modo 2] Reproduz a trajetória gravada de forma suavizada, contínua e a velocidade constante."""
    output_fn(
        "\n\n=== Iniciando PlayBack Modo 2 (Velocidade Constante Suavizada) ===\n"
    )
    raw_trajectory = load_mirror_result()
    if not raw_trajectory:
        output_fn("Nenhum resultado de espelhamento encontrado para teste.")
        return

    # Gera a trajetória reamostrada e interpolada
    smooth_traj = generate_smooth_trajectory(
        raw_trajectory,
        target_speed_deg_s=target_speed_deg_s,
        sample_interval=sample_interval,
    )
    total_duration = smooth_traj[-1]["time"] if smooth_traj else 0.0
    output_fn(
        f"Trajetória suavizada gerada com sucesso ({len(smooth_traj)} waypoints, "
        f"duração total estimada: {total_duration:.2f}s a {target_speed_deg_s}°/s)."
    )

    reset_position = input_fn(
        "\nDeseja mover o robô para a posição inicial (Home) antes de reproduzir? (s/n): "
    )
    if not reset_position.strip().lower() in ("s", "sim", "y", "yes"):
        output_fn("PlayBack cancelado pelo operador.")
        return

    time.sleep(1)  # Tempo de segurança
    set_robot_home_pose(arm, output_fn=output_fn)

    if not arm.is_torque_enabled():
        arm.enable_torque()

    # Move suavemente da Home para a primeira pose gravada antes de iniciar o streaming
    first_pose = smooth_traj[0]["angles"]
    output_fn("\nAlinhando braço com a primeira pose gravada...")
    arm.move_pose(first_pose, timeout=6.0)

    question = input_fn(
        "\nBraço pronto no ponto inicial. Deseja iniciar o PlayBack suavizado? (s/n): "
    )
    if not question.strip().lower() in ("s", "sim", "y", "yes"):
        output_fn("PlayBack cancelado pelo operador.")
        return

    output_fn("-> Executando trajetória suavizada em velocidade constante...")
    start_playback_time = time.monotonic()

    for i in range(len(smooth_traj)):
        target_angles = smooth_traj[i]["angles"]
        target_time = smooth_traj[i]["time"]

        # Envia o pacote SyncWrite broadcast para todas as 6 juntas
        arm.command_pose(target_angles)

        # Aguarda até o timestamp relativo do waypoint com relógio monotônico
        elapsed = time.monotonic() - start_playback_time
        time_to_wait = target_time - elapsed
        if time_to_wait > 0:
            time.sleep(time_to_wait)

    output_fn("PlayBack suavizado da ação de espelhamento concluído com sucesso!")


def select_and_run_replay(
    arm: RobotArm,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Apresenta o menu para o operador escolher entre o Modo 1 (Original) e o Modo 2 (Suavizado)."""
    output_fn("\n==================================================")
    output_fn("Escolha o Modo de Reprodução (Replay):")
    output_fn("  1: Replay Original (tempo real fiel como gravado, com pausas)")
    output_fn("  2: Replay Suavizado (velocidade constante contínua sem pausas)")
    output_fn("==================================================")

    choice = input_fn("Selecione a opção desejada (1 ou 2): ").strip()
    if choice == "2":
        replay_smooth_trajectory(arm, input_fn=input_fn, output_fn=output_fn)
    elif choice == "1":
        replay_trajectory(arm, input_fn=input_fn, output_fn=output_fn)
    else:
        output_fn(f"Opção '{choice}' não reconhecida. Executando Modo 1 padrão.")
        replay_trajectory(arm, input_fn=input_fn, output_fn=output_fn)


def main_mirror(
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

            # Salva Resultados em JSON
            save_result(mirror_positions)
            break

        time.sleep(RECORD_TIME_GAP)

    select_and_run_replay(arm, input_fn=input_fn, output_fn=output_fn)
    disable_torque = input_fn("\n\nDesabilitar torque? (s/n): ")

    if disable_torque:
        arm.disable_torque()
        output_fn("Torque desabilitado. Ação de espelhamento concluída.")
