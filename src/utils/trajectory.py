from collections.abc import Sequence
from typing import Any


# Realiza Suavizacao de Trajetoria com Interpolacao Linear (LERP) e Reamostragem Temporal

def calculate_joint_distance(pose_a: dict[str, float], pose_b: dict[str, float]) -> float:
    """Calcula a maior variação angular (junta líder) entre duas poses."""
    return max(abs(pose_b[name] - pose_a[name]) for name in pose_b if name in pose_a)


def filter_noise_waypoints(
    trajectory: Sequence[dict[str, Any]],
    min_delta_deg: float = 0.2,
) -> list[dict[str, Any]]:
    """Remove waypoints consecutivos com variação angular insignificante (< min_delta_deg)."""
    if not trajectory:
        return []

    clean_waypoints = [trajectory[0]]
    for wp in trajectory[1:]:
        last_angles = clean_waypoints[-1]["angles"]
        curr_angles = wp["angles"]
        max_delta = calculate_joint_distance(last_angles, curr_angles)
        if max_delta >= min_delta_deg:
            clean_waypoints.append(wp)

    return clean_waypoints


def generate_smooth_trajectory(
    trajectory: Sequence[dict[str, Any]],
    target_speed_deg_s: float = 35.0,
    sample_interval: float = 0.04,
) -> list[dict[str, Any]]:
    """Gera uma trajetória reamostrada com velocidade angular constante e interpolação linear densa (LERP).

    Matemática aplicada:
    1. Filtro de Ruído: Descarta variações de encoder imperceptíveis (< 0.2°).
    2. Reamostragem Temporal: O tempo de cada segmento é calculado como (Δθ_max / target_speed),
       eliminando hesitações manuais e pausas gravadas acidentalmente.
    3. Interpolação a 25 Hz (40ms): Gera waypoints contínuos e suaves para transmissão via SyncWrite.

    Args:
        trajectory: Lista de waypoints [{"time": float, "angles": dict[str, float]}].
        target_speed_deg_s: Velocidade angular da junta líder em graus/s (padrão: 35°/s).
        sample_interval: Período de amostragem em segundos (padrão: 0.04s = 25Hz).

    Returns:
        Nova lista de waypoints suavizados e interpolados.
    """
    if not trajectory:
        return []

    if len(trajectory) == 1:
        return [{"time": 0.0, "angles": trajectory[0]["angles"].copy()}]

    # 1. Filtra waypoints redundantes
    clean_waypoints = filter_noise_waypoints(trajectory, min_delta_deg=0.2)

    if len(clean_waypoints) == 1:
        return [{"time": 0.0, "angles": clean_waypoints[0]["angles"].copy()}]

    # 2. Recalcula os tempos de cada trecho para velocidade angular constante
    cumulative_times: list[float] = [0.0]
    total_time = 0.0

    for i in range(1, len(clean_waypoints)):
        prev_angles = clean_waypoints[i - 1]["angles"]
        curr_angles = clean_waypoints[i]["angles"]
        max_delta = calculate_joint_distance(prev_angles, curr_angles)
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
        while seg_idx < num_segments - 1 and current_time > cumulative_times[seg_idx + 1]:
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

        interpolated_angles = {
            name: p_start[name] + alpha * (p_end[name] - p_start[name])
            for name in joint_names
        }

        smooth_trajectory.append({
            "time": round(current_time, 4),
            "angles": interpolated_angles,
        })

        current_time += sample_interval

    # Garante que a última pose exata esteja presente
    last_expected_pose = clean_waypoints[-1]["angles"]
    if smooth_trajectory and smooth_trajectory[-1]["angles"] != last_expected_pose:
        smooth_trajectory.append({
            "time": round(total_time, 4),
            "angles": last_expected_pose.copy(),
        })

    return smooth_trajectory


def calculate_trajectory_duration(trajectory: Sequence[dict[str, Any]]) -> float:
    """Retorna a duração total de uma trajetória em segundos."""
    if not trajectory:
        return 0.0
    return float(trajectory[-1].get("time", 0.0))
