from collections.abc import Callable
from typing import Any

from scservo_sdk import PortHandler, sms_sts

from src.models.RobotArm import RobotArm
from src.models.joint_config import MAX_SERVO_ID, MIN_SERVO_ID
from src.utils.validation import validate_result

from src.calibration.read_joint_position import run_reader

STEPS_PER_REVOLUTION = 4096
DEGREES = 360.0

zero_position = 0 # Posição de referência (em contagens) para o ângulo zero
direction = 1 # Direção padrão (1 = normal, -1 = invertida)
def run_calibration(input_fn: Callable[[str], str] = input, output_fn: Callable[[str], None] = print) -> None:
    print("Iniciando calibração do braço robótico.")