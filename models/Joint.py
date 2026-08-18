from scservo_sdk import *
from typing import Any
from utils.validation import validate_result

DEFAULT_SPEED = 1000
DEFAULT_ACC = 100

MIN_SPEED = 0
MAX_SPEED = 3400

MIN_ACC = 0
MAX_ACC = 254

MIN_SERVO_POSITION = 0
MAX_SERVO_POSITION = 4095

POSITION_TOLERANCE = 10
STEPS_PER_REVOLUTION = 4096

ADDR_TORQUE_ENABLE = 40
TORQUE_DISABLED = 0
TORQUE_ENABLED = 1


class Joint:
    def __init__(
        self,
        servo_id: int,
        servo: Any,
        name: str,
        min_pos: int,
        max_pos: int,
        speed: int = DEFAULT_SPEED,
        acc: int = DEFAULT_ACC,
    ) -> None:
        self._validate_configuration(
            servo_id=servo_id,
            servo=servo,
            name=name,
            min_pos=min_pos,
            max_pos=max_pos,
            speed=speed,
            acc=acc,
        )

        self.servo_id = servo_id
        self.servo = servo
        self.name = name
        self.min_pos = min_pos
        self.max_pos = max_pos
        self.speed = speed
        self.acc = acc

    @staticmethod
    def _validate_configuration(
        servo_id: int,
        servo: Any,
        name: str,
        min_pos: int,
        max_pos: int,
        speed: int,
        acc: int,
    ) -> None:
        if not isinstance(servo_id, int):
            raise TypeError("servo_id deve ser um número inteiro")

        if servo_id < 0:
            raise ValueError("servo_id não pode ser negativo")

        if servo is None:
            raise ValueError("Servo não pode ser None")

        if not isinstance(name, str):
            raise TypeError("Name deve ser uma string")

        if not name.strip():
            raise ValueError("Name não pode estar vazio")

        if not isinstance(min_pos, int) or not isinstance(max_pos, int):
            raise TypeError("min_pos e max_pos devem ser números inteiros")

        if not MIN_SERVO_POSITION <= min_pos <= MAX_SERVO_POSITION:
            raise ValueError(
                f"min_pos deve estar entre "
                f"{MIN_SERVO_POSITION} e {MAX_SERVO_POSITION}"
            )

        if not MIN_SERVO_POSITION <= max_pos <= MAX_SERVO_POSITION:
            raise ValueError(
                f"max_pos deve estar entre "
                f"{MIN_SERVO_POSITION} e {MAX_SERVO_POSITION}"
            )

        if min_pos >= max_pos:
            raise ValueError("min_pos deve ser menor que max_pos")

    @staticmethod
    def _validate_speed(speed: int) -> None:
        if not isinstance(speed, int):
            raise TypeError("speed deve ser um número inteiro")

        if not MIN_SPEED <= speed <= MAX_SPEED:
            raise ValueError(f"speed deve estar entre {MIN_SPEED} e {MAX_SPEED}")

    @staticmethod
    def _validate_acceleration(acc: int) -> None:
        if not isinstance(acc, int):
            raise TypeError("acc deve ser um número inteiro")

        if not MIN_ACC <= acc <= MAX_ACC:
            raise ValueError(f"acc deve estar entre {MIN_ACC} e {MAX_ACC}")

    def current_position(self) -> int:
        position, _, result, error = self.servo.ReadPosSpeed(self.servo_id)

        validate_result(self.servo, result, error, f"{self.name}: leitura de posição")

        return position

    def enable_torque(self):
        current_position = self.current_position()

        # Evita que o servo tente buscar um alvo antigo ao habilitar o torque.
        result, error = self.servo.WritePosEx(
            self.servo_id,
            current_position,
            self.speed,
            self.acc,
        )

        validate_result(
            self.servo,
            result,
            error,
            f"{self.name}: preparação da posição",
        )

        self._write_torque(TORQUE_ENABLED)

        if not self.is_torque_enabled():
            raise RuntimeError(f"{self.name}: torque não foi habilitado")

        print(f"{self.name}: torque habilitado")

    def disable_torque(self) -> None:
        self._write_torque(TORQUE_DISABLED)

        if self.is_torque_enabled():
            raise RuntimeError(f"{self.name}: torque não foi desabilitado")

        print(f"{self.name}: torque desabilitado")

    def is_torque_enabled(self) -> bool:
        torque_value, result, error = self.servo.read1ByteTxRx(
            self.servo_id,
            ADDR_TORQUE_ENABLE,
        )

        validate_result(
            self.servo,
            result,
            error,
            f"{self.name}: leitura do torque",
        )

        return torque_value == TORQUE_ENABLED

    def _write_torque(self, value: int) -> None:
        result, error = self.servo.write1ByteTxRx(
            self.servo_id,
            ADDR_TORQUE_ENABLE,
            value,
        )

        validate_result(
            self.servo,
            result,
            error,
            f"{self.name}: alteração do torque",
        )

    def angle_to_position(self, angle: float) -> int:
        if not isinstance(angle, (int, float)):
            raise TypeError("Angle deve ser um número")

        if not 0 <= angle <= 360:
            raise ValueError("Angle deve estar entre 0° e 360°")

        if angle == 360:
            position = MAX_SERVO_POSITION
        else:
            position = round(angle * STEPS_PER_REVOLUTION / 360.0)

        if not self.min_pos <= position <= self.max_pos:
            raise ValueError(
                f"{self.name}: ângulo de {angle}° gera a posição "
                f"{position}, fora do limite "
                f"[{self.min_pos}, {self.max_pos}]"
            )

        return position

    def position_to_angle(self, position: int) -> float:
        if not isinstance(position, int):
            raise TypeError("Position deve ser um número inteiro")

        if not self.min_pos <= position <= self.max_pos:
            raise ValueError(
                f"{self.name}: posição {position} fora do limite "
                f"[{self.min_pos}, {self.max_pos}]"
            )

        return position * 360.0 / STEPS_PER_REVOLUTION

    # Move a junta com target -> angle
    def move(
        self,
        angle: float,
        speed: int | None = None,
        acc: int | None = None,
    ) -> int:
        command_speed = self.speed if speed is None else speed
        command_acc = self.acc if acc is None else acc

        self._validate_speed(command_speed)
        self._validate_acceleration(command_acc)

        target_position = self.angle_to_position(angle)
        current_position = self.current_position()

        position_error = abs(target_position - current_position)

        if position_error <= POSITION_TOLERANCE:
            print(
                f"{self.name}: posição já atingida: "
                f"{current_position} (erro={position_error})"
            )
            return current_position

        print(
            f"{self.name}: enviando movimento "
            f"{current_position} -> {target_position}"
        )

        result, error = self.servo.WritePosEx(
            self.servo_id,
            target_position,
            command_speed,
            command_acc,
        )

        validate_result(
            self.servo,
            result,
            error,
            f"{self.name}: comando de movimento",
        )

        # O comando foi recebido, mas o movimento ainda pode estar acontecendo.
        return self.current_position()
