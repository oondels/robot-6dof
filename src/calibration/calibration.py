from collections.abc import Callable
from typing import Any

from scservo_sdk import PortHandler, sms_sts

from src.utils.validation import validate_result

from src.calibration.read_joint_position import run_reader

STEPS_PER_REVOLUTION = 4096
DEGREES = 360.0


def count_to_degrees(counts: float, direction: int, zero_position: float) -> float:
    """Converte contagens do encoder para graus."""
    return ((counts - zero_position) * DEGREES / STEPS_PER_REVOLUTION) * direction


def run_calibration(
    input_fn: Callable[[str], str] = input, output_fn: Callable[[str], None] = print
) -> None:
    # Essa funcao tem como objetivo calibrar juntas do robo
    # pode ser utilizado como auxiliar de calibracao, os dados de erro de load do servo (maximo por folta de 220)
    # A proposta é selecionar uma junta, mover e ir tirando medidas, o usuario define onde é o ponto de operacao maximo e minimo
    # o sistema calcula -> count minimo, count maximo, angulo minimo e angulo maximo, direcao de operacao, etc
    print("Iniciando calibração do braço robótico.")
