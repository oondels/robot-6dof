from collections.abc import Callable, Sequence
from datetime import datetime
import json
from pathlib import Path
import re
import time
from typing import Any

from src.models.RobotArm import RobotArm
from src.utils.trajectory import (
    calculate_trajectory_duration,
    generate_smooth_trajectory,
)

# Diretório padrão para armazenamento das ações gravadas na raiz do projeto
DEFAULT_RECORDED_ACTIONS_DIR = Path(__file__).resolve().parent.parent / "recorded_actions"


def sanitize_action_name(name: str) -> str:
    """Normaliza o nome da ação para um identificador seguro de arquivo (letras, números, hífen, underscore)."""
    if not isinstance(name, str):
        raise TypeError("O nome da ação deve ser uma string.")

    cleaned = name.strip().lower().replace(" ", "_")
    cleaned = re.sub(r"[^a-z0-9_-]", "", cleaned)
    if not cleaned:
        raise ValueError(f"Nome de ação inválido: '{name}'. Use letras e números.")
    return cleaned


def get_actions_directory(base_dir: Path | None = None) -> Path:
    """Retorna o diretório de ações gravadas, criando-o se não existir."""
    actions_dir = base_dir if base_dir is not None else DEFAULT_RECORDED_ACTIONS_DIR
    actions_dir.mkdir(parents=True, exist_ok=True)
    return actions_dir


def save_named_action(
    name: str,
    trajectory: Sequence[dict[str, Any]],
    description: str = "",
    target_speed_deg_s: float = 35.0,
    sample_interval: float = 0.04,
    base_dir: Path | None = None,
) -> Path:
    """Salva uma trajetória como ação nomeada em recorded_actions/, sempre no formato suavizado (smooth).

    Args:
        name: Identificador da ação (ex.: 'pegar_copo', 'danca', 'tchau').
        trajectory: Trajetória bruta ou pré-gravada.
        description: Descrição opcional da ação.
        target_speed_deg_s: Velocidade angular da junta líder em graus/s.
        sample_interval: Taxa de amostragem em segundos (padrão: 0.04s = 25Hz).
        base_dir: Diretório customizado para persistência (usado em testes).

    Returns:
        Path absoluto do arquivo .json salvo.
    """
    clean_name = sanitize_action_name(name)
    actions_dir = get_actions_directory(base_dir)
    file_path = actions_dir / f"{clean_name}.json"

    # Sempre converte para a versão suavizada a velocidade constante
    smooth_traj = generate_smooth_trajectory(
        trajectory=trajectory,
        target_speed_deg_s=target_speed_deg_s,
        sample_interval=sample_interval,
    )

    if not smooth_traj:
        raise ValueError("Não é possível salvar uma ação com trajetória vazia.")

    joint_names = sorted(list(smooth_traj[0]["angles"].keys()))
    duration = calculate_trajectory_duration(smooth_traj)

    payload = {
        "name": clean_name,
        "description": description.strip(),
        "created_at": datetime.now().isoformat(),
        "format_version": "1.0",
        "is_smooth": True,
        "target_speed_deg_s": target_speed_deg_s,
        "sample_interval": sample_interval,
        "duration_seconds": round(duration, 3),
        "waypoints_count": len(smooth_traj),
        "joint_names": joint_names,
        "trajectory": smooth_traj,
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return file_path


def load_named_action(name: str, base_dir: Path | None = None) -> dict[str, Any]:
    """Carrega uma ação gravada a partir do nome ou caminho."""
    clean_name = sanitize_action_name(name)
    actions_dir = get_actions_directory(base_dir)
    file_path = actions_dir / f"{clean_name}.json"

    if not file_path.exists():
        raise FileNotFoundError(f"Ação gravada '{clean_name}' não encontrada em: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def list_named_actions(base_dir: Path | None = None) -> list[dict[str, Any]]:
    """Varre e retorna a lista de todas as ações gravadas disponíveis."""
    actions_dir = get_actions_directory(base_dir)
    actions_list: list[dict[str, Any]] = []

    for file_path in sorted(actions_dir.glob("*.json")):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                actions_list.append({
                    "name": data.get("name", file_path.stem),
                    "description": data.get("description", ""),
                    "duration_seconds": data.get("duration_seconds", 0.0),
                    "waypoints_count": data.get("waypoints_count", len(data.get("trajectory", []))),
                    "created_at": data.get("created_at", ""),
                    "file_path": str(file_path),
                })
        except Exception:
            continue

    return actions_list


def print_named_actions(
    output_fn: Callable[[str], None] = print,
    base_dir: Path | None = None,
) -> None:
    """Imprime uma tabela formatada de todas as ações gravadas disponíveis."""
    actions = list_named_actions(base_dir)
    output_fn("==================================================")
    output_fn("Ações Gravadas Disponíveis (`recorded_actions/`)")
    output_fn("==================================================")

    if not actions:
        output_fn("Nenhuma ação gravada encontrada.")
        output_fn("Use `python main.py --action mirror` para gravar uma nova ação.")
        return

    output_fn(f"{'Nome da Ação':<20} | {'Duração':<10} | {'Waypoints':<10} | {'Descrição'}")
    output_fn("-" * 65)
    for act in actions:
        name = act["name"]
        dur = f"{act['duration_seconds']:.2f}s"
        pts = f"{act['waypoints_count']}"
        desc = act["description"] if act["description"] else "(sem descrição)"
        output_fn(f"{name:<20} | {dur:<10} | {pts:<10} | {desc}")
    output_fn("-" * 65)
    output_fn("Para executar: `python main.py --action <nome_da_acao>`")


def play_named_action(
    arm: RobotArm,
    action_name: str,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    base_dir: Path | None = None,
) -> None:
    """Executa uma ação gravada, garantindo SEMPRE o posicionamento prévio na pose Default (Home)."""
    action_data = load_named_action(action_name, base_dir=base_dir)
    name = action_data["name"]
    duration = action_data.get("duration_seconds", 0.0)
    trajectory = action_data.get("trajectory", [])

    if not trajectory:
        output_fn(f"Ação '{name}' possui trajetória vazia.")
        return

    output_fn("\n==================================================")
    output_fn(f"Executando Ação Gravada: '{name}'")
    if action_data.get("description"):
        output_fn(f"Descrição: {action_data['description']}")
    output_fn(f"Duração estimada: {duration:.2f}s | Waypoints: {len(trajectory)}")
    output_fn("==================================================")

    # 1. SEMPRE posiciona o robô na posição default (Home: 0.0° para todas as juntas cadastradas)
    output_fn("\n[1/3] Movendo braço para a posição Default (Home)...")
    if not arm.is_torque_enabled():
        arm.enable_torque()

    home_pose = {joint_name: 0.0 for joint_name in arm.joint_names}
    arm.move_pose(home_pose, timeout=8.0)
    output_fn("-> Braço posicionado em Home com sucesso.")

    # 2. Move suavemente da Home para a primeira pose gravada (P0)
    first_pose = trajectory[0]["angles"]
    output_fn("\n[2/3] Alinhando braço com o ponto inicial da ação...")
    arm.move_pose(first_pose, timeout=6.0)
    output_fn("-> Alinhamento concluído.")

    # 3. Executa o streaming suavizado via SyncWrite
    output_fn(f"\n[3/3] Executando trajetória da ação '{name}'...")
    start_time = time.monotonic()

    try:
        for i in range(len(trajectory)):
            target_angles = trajectory[i]["angles"]
            target_time = trajectory[i]["time"]

            # Envia pacote broadcast SyncWrite
            arm.command_pose(target_angles, speed=1000)

            speed_factor = 2.0
            # Sincroniza com relógio monotônico
            elapsed = time.monotonic() - start_time
            time_to_wait = (target_time / speed_factor) - elapsed
            if time_to_wait > 0:
                time.sleep(time_to_wait)

        output_fn(f"\n-> Ação '{name}' concluída com sucesso!")
    finally:
        time.sleep(0.5) 
        # Devolve o robo para a posição Home antes de desabilitar torque
        output_fn("\nMovendo braço de volta para a posição Default (Home)...")
        arm.move_pose(home_pose, timeout=8.0)
        
        time.sleep(0.5)  # Tempo de segurança antes de desabilitar torque
        arm.disable_torque()
        output_fn("Torque desabilitado.")
