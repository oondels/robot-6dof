import argparse
from collections.abc import Callable
from typing import Any

import time

from scservo_sdk import PortHandler, sms_sts

from models.joint_config import MAX_SERVO_ID, MIN_SERVO_ID
from utils.validation import validate_result

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 1_000_000
DEFAULT_SERVO_ID = 6


def validate_servo_id(servo_id: int) -> None:
    if type(servo_id) is not int:
        raise TypeError("servo_id deve ser um número inteiro")

    if not MIN_SERVO_ID <= servo_id <= MAX_SERVO_ID:
        raise ValueError(f"servo_id deve estar entre {MIN_SERVO_ID} e {MAX_SERVO_ID}")


def read_position(servo: Any, servo_id: int) -> int:
    validate_servo_id(servo_id)

    position, _, result, error = servo.ReadPosSpeed(servo_id)

    validate_result(
        servo,
        result,
        error,
        f"servo {servo_id}: leitura para calibração",
    )

    return position


def run_reader(
    servo: Any,
    servo_id: int,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    validate_servo_id(servo_id)

    output_fn(
        "Leitura de calibração iniciada. "
        "Esta rotina não habilita torque e não envia movimento."
    )

    command = input_fn(
        "Pressione Enter para começar a leitura dos counts ou digite 'q' para sair: "
    )
    
    last_signal = None
    last_position = None
    while command.strip().lower() != "q":
        position = read_position(servo, servo_id)
        current_time = time.monotonic_ns()
        
        if last_position is not None and position != last_position and (last_signal is None or current_time - last_signal > 500_000_000):  # 500 ms
            output_fn(f"servo {servo_id}: posição={position} counts (mudou de {last_position})")
            last_signal = current_time
        
        last_position = position

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lê counts brutos de um servo sem enviar movimento."
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--servo-id", type=int, default=DEFAULT_SERVO_ID)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_servo_id(args.servo_id)

    port = PortHandler(args.port)
    servo = sms_sts(port)

    try:
        if not port.openPort():
            raise RuntimeError(f"Erro abrindo a porta {args.port}")

        if not port.setBaudRate(args.baudrate):
            raise RuntimeError(f"Erro configurando baudrate {args.baudrate}")

        run_reader(servo, args.servo_id)
    except KeyboardInterrupt:
        print("\nLeitura encerrada pelo operador.")
    finally:
        port.closePort()


if __name__ == "__main__":
    main()
