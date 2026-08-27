from typing import Callable

from src.application.robot_arm import RobotArm



def move_arm_to_home(arm: RobotArm, output_fn: Callable[[str], None] = print, service: str = "default") -> None:
    """Move o braço robótico para a pose Home (posição padrão)."""
    try:
        output_fn("\n==================================================")
        output_fn("Movendo braço para a posição Home...")
        output_fn("==================================================\n")
        if not arm.is_torque_enabled():
            arm.enable_torque()
    
        home_pose = {joint_name: 0.0 for joint_name in arm.joint_names}
        arm.move_pose(home_pose, timeout=8.0)
        output_fn("Braço retornado para a posição de descanço.")
    except Exception as e:
        output_fn(f"Erro ao mover o braço para a posição Home: {e}")
    finally:
        if arm.is_torque_enabled() and service == "default":
            print(f"[DEBUG] Desabilitando torque do braço após serviço '{service}'")
            arm.disable_torque()
