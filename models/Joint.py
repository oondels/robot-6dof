from typing import Any

from models.joint_config import (
    STEPS_PER_REVOLUTION,
    JointConfig,
)
from utils.validation import validate_result

ADDR_TORQUE_ENABLE = 40
TORQUE_DISABLED = 0
TORQUE_ENABLED = 1


class Joint:
    def __init__(
        self,
        servo: Any,
        config: JointConfig,
    ) -> None:
        if servo is None:
            raise ValueError("servo não pode ser None")

        if not isinstance(config, JointConfig):
            raise TypeError("config deve ser uma instância de JointConfig")

        self.servo = servo
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def servo_id(self) -> int:
        return self.config.servo_id

    @property
    def speed(self) -> int:
        return self.config.speed

    @property
    def acc(self) -> int:
        return self.config.acc

    def current_position(self) -> int:
        position, _, result, error = self.servo.ReadPosSpeed(self.servo_id)

        validate_result(
            self.servo,
            result,
            error,
            f"{self.name}: leitura de posição",
        )

        return position

    def current_angle(self) -> float:
        return self.position_to_angle(self.current_position())

    def enable_torque(self) -> None:
        current_position = self.current_position()

        # Evita buscar um alvo antigo ao habilitar o torque.
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
        return self.config.angle_to_position(angle)

    def position_to_angle(self, position: int) -> float:
        return self.config.position_to_angle(position)

    def move(
        self,
        angle: float,
        speed: int | None = None,
        acc: int | None = None,
    ) -> int:
        command_speed = self.speed if speed is None else speed

        command_acc = self.acc if acc is None else acc

        JointConfig.validate_speed(command_speed)
        JointConfig.validate_acceleration(command_acc)

        target_position = self.angle_to_position(angle)
        current_position = self.current_position()

        tolerance_counts = max(
            1,
            round(self.config.tolerance_deg * STEPS_PER_REVOLUTION / 360.0),
        )

        position_error = abs(target_position - current_position)

        if position_error <= tolerance_counts:
            print(
                f"{self.name}: posição já atingida: "
                f"{current_position} "
                f"(erro={position_error} counts)"
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

        # A espera pela conclusão será implementada na etapa 3.
        return self.current_position()
