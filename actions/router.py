from collections.abc import Callable

from calibration.test_arm_poses import run_pose_tester
from actions.mirror_action import run_mirror_action
from models.RobotArm import RobotArm


def execute_action(
    action: str,
    arm: RobotArm,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Roteia e executa a ação solicitada para o braço robótico."""
    if not isinstance(action, str):
        raise TypeError("action deve ser uma string")

    normalized = action.strip().lower()

    if normalized == "test":
        run_pose_tester(arm, input_fn=input_fn, output_fn=output_fn)
    elif normalized == "mirror":
        run_mirror_action(arm, input_fn=input_fn, output_fn=output_fn)
    else:
        raise ValueError(f"Ação desconhecida: '{action}'")
