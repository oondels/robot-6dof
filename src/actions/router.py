from collections.abc import Callable

from src.actions.mirror_action import run_mirror_action
from src.actions.recorded_actions import (
    DEFAULT_RECORDED_ACTIONS_DIR,
    play_named_action,
    print_named_actions,
    sanitize_action_name,
)
from src.calibration.test_arm_poses import run_pose_tester
from src.application import RobotArm
from src.calibration.calibration import run_calibration
from src.actions.tele_control.keyboard_control import keyboard_control
from src.actions.tele_control.ps5_controller import controller_control


def execute_action(
    action: str,
    arm: RobotArm | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Roteia e executa a ação solicitada para o braço robótico.

    Suporta:
    - 'test': Testador interativo de poses sincronizadas (SyncWrite).
    - 'mirror': Modo de espelhamento e gravação manual (Teach & Repeat).
    - 'list': Lista todas as ações gravadas disponíveis em recorded_actions/.
    - '<nome_acao>': Executa uma ação previamente gravada e salva em recorded_actions/.
    """
    if not isinstance(action, str):
        raise TypeError("action deve ser uma string")

    normalized = action.strip().lower()

    # 1. Ação de listagem (não requer obrigatoriamente instância de hardware)
    if normalized == "list":
        print_named_actions(output_fn=output_fn)
        return

    if arm is None:
        raise ValueError(
            f"Para executar a ação '{action}', uma instância de RobotArm é necessária."
        )

    if normalized == "calibrate":
        run_calibration(input_fn=input_fn, output_fn=output_fn)
        return

    # 2. Ações nativas do sistema
    if normalized == "test":
        run_pose_tester(arm, input_fn=input_fn, output_fn=output_fn)
    elif normalized == "mirror":
        run_mirror_action(arm, input_fn=input_fn, output_fn=output_fn)
    elif normalized == "keyboard":
        keyboard_control()
    elif normalized == "ps5" or normalized == "controller":
        controller_control(arm)
    else:
        # 3. Verifica se corresponde a uma ação gravada em recorded_actions/
        try:
            clean_name = sanitize_action_name(normalized)
            action_file = DEFAULT_RECORDED_ACTIONS_DIR / f"{clean_name}.json"
            if action_file.exists():
                play_named_action(
                    arm, clean_name, input_fn=input_fn, output_fn=output_fn
                )
                return
        except Exception:
            pass

        raise ValueError(
            f"Ação desconhecida: '{action}'. "
            "Use `python main.py --action list` para ver as ações gravadas disponíveis."
        )
