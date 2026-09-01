"""Bootstrap para controle do braço robótico via controle PS5/DualSense."""

from src.actions.home_pose import move_arm_to_home
from src.application.robot_arm import RobotArm
from src.application.teleoperation import TeleOperation
from src.infrastructure.input.ps5_controller import (
    Ps5ControllerInput,
    find_ps5_controller_device,
)
from src.utils.adaptive_trigger import apply_load_to_adaptive_trigger


def controller_control(arm: RobotArm) -> None:
    """Inicializa os recursos de hardware e executa a teleoperação PS5."""
    device_path = find_ps5_controller_device()
    controller = Ps5ControllerInput(device_path)
    apply_load_to_adaptive_trigger(0, 0.0, 0.0, initialize=True)
    controller.open()

    teleop = TeleOperation(
        input_control_device=controller,
        robot_arm=arm,
        jog_speed=60.0,
    )

    try:
        teleop.run()
    except KeyboardInterrupt:
        print("\n[AUDIT] Encerrando monitor...")
    finally:
        apply_load_to_adaptive_trigger(0, 0.0, 0.0, shutdown=True)
        move_arm_to_home(arm, output_fn=print)
        controller.close()

