from scservo_sdk import *
import time
from utils.validation import validate_result

PORT = "/dev/ttyUSB0"
BAUDRATE = 1_000_000
SERVO_ID = 6

ADDR_TORQUE_ENABLE = 40

MIN_POSITION = 0
MAX_POSITION = 4095
STEPS_PER_REVOLUTION = 4096

POSITION_TOLERANCE = 10

DEFAULT_SPEED = 1000
DEFAULT_ACC = 100

port = PortHandler(PORT)
servo = sms_sts(port)


def connect():
    if not port.openPort():
        raise RuntimeError("Erro abrindo porta")

    if not port.setBaudRate(BAUDRATE):
        raise RuntimeError("Erro configurando baudrate")


def current_position() -> int:
    position, speed, result, error = servo.ReadPosSpeed(
        SERVO_ID
    )

    validate_result(servo, result, error, "Leitura de posição")

    return position


def enable_torque():
    position = current_position()

    # Define posição atual como alvo antes de habilitar torque
    result, error = servo.WritePosEx(
        SERVO_ID,
        position,
        DEFAULT_SPEED,
        DEFAULT_ACC,
    )

    validate_result(
        servo,
        result,
        error,
        "Preparação da posição"
    )

    result, error = servo.write1ByteTxRx(
        SERVO_ID,
        ADDR_TORQUE_ENABLE,
        1,
    )

    validate_result(
        servo,
        result,
        error,
        "Habilitação do torque"
    )

    torque, result, error = servo.read1ByteTxRx(
        SERVO_ID,
        ADDR_TORQUE_ENABLE,
    )

    validate_result(
        servo,
        result,
        error,
        "Leitura do torque"
    )

    if torque != 1:
        raise RuntimeError(
            f"Torque não foi habilitado. Valor={torque}"
        )

    print("Torque habilitado")


def position_to_angle(position: int) -> float:
    if not MIN_POSITION <= position <= MAX_POSITION:
        raise ValueError(
            f"Posição deve estar entre "
            f"{MIN_POSITION} e {MAX_POSITION}"
        )

    return position * 360.0 / STEPS_PER_REVOLUTION


def angle_to_position(angle: float) -> int:
    if not 0 <= angle <= 360:
        raise ValueError(
            "Ângulo deve estar entre 0° e 360°"
        )

    # 360° corresponde ao último count disponível
    if angle == 360:
        return MAX_POSITION

    position = round(
        angle * STEPS_PER_REVOLUTION / 360.0
    )

    return min(position, MAX_POSITION)


def move_pos(
    target: int,
    speed: int = DEFAULT_SPEED,
    acc: int = DEFAULT_ACC,
) -> int:

    if not MIN_POSITION <= target <= MAX_POSITION:
        raise ValueError(
            f"Target deve estar entre "
            f"{MIN_POSITION} e {MAX_POSITION}"
        )

    position = current_position()

    error_position = abs(target - position)

    if error_position <= POSITION_TOLERANCE:
        print(
            f"Posição já atingida: "
            f"{position} "
            f"(erro={error_position})"
        )

        return position

    print(
        f"Movendo {position} -> {target}"
    )

    result, error = servo.WritePosEx(
        SERVO_ID,
        target,
        speed,
        acc,
    )

    validate_result(
        servo,
        result,
        error,
        "Comando de movimento"
    )

    while True:
        position, motor_speed, result, error = (
            servo.ReadPosSpeed(SERVO_ID)
        )

        validate_result(
            servo,
            result,
            error,
            "Leitura durante movimento"
        )

        moving, result, error = servo.ReadMoving(
            SERVO_ID
        )

        validate_result(
            servo,
            result,
            error,
            "Leitura de movimento"
        )

        error_position = abs(
            target - position
        )

        print(
            f"position={position} "
            f"angle={position_to_angle(position):.2f}° "
            f"speed={motor_speed} "
            f"moving={moving} "
            f"error={error_position}"
        )

        if (
            moving == 0
            and error_position <= POSITION_TOLERANCE
        ):
            break

        if moving == 0:
            # Servo considerou movimento concluído,
            # mesmo estando fora da tolerância.
            break

        time.sleep(0.05)

    final_position = current_position()

    final_error = abs(
        target - final_position
    )

    print(
        f"\nFinal: {final_position} "
        f"({position_to_angle(final_position):.2f}°)"
    )

    print(
        f"Target: {target} "
        f"({position_to_angle(target):.2f}°)"
    )

    print(
        f"Erro: {final_error} counts "
        f"({final_error * 360 / 4096:.3f}°)"
    )

    return final_position


def move_angle(
    angle: float,
    speed: int = DEFAULT_SPEED,
    acc: int = DEFAULT_ACC,
):
    target = angle_to_position(angle)

    print(
        f"{angle:.2f}° -> posição {target}"
    )

    return move_pos(
        target,
        speed,
        acc,
    )


def menu():
    print()
    print("1. Mover por posição")
    print("2. Mover por ângulo")

    choice = input(
        "Escolha uma opção: "
    ).strip()

    if choice == "1":
        position = int(
            input("Posição (0 ~ 4095): ")
        )

        move_pos(position)

    elif choice == "2":
        angle = float(
            input("Ângulo (0° ~ 360°): ")
        )

        move_angle(angle)

    else:
        print("Opção inválida")


try:
    connect()

    position = current_position()

    print(
        f"Posição atual: {position}"
    )

    print(
        f"Ângulo atual: "
        f"{position_to_angle(position):.2f}°"
    )

    enable_torque()

    menu()

finally:
    port.closePort()