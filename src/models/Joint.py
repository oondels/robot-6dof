from dataclasses import dataclass
from math import isfinite
from time import monotonic, sleep
from typing import Any

from src.models.joint_config import JointConfig
from src.utils.validation import validate_result

ADDR_TORQUE_ENABLE = 40
TORQUE_DISABLED = 0
TORQUE_ENABLED = 1


@dataclass(frozen=True, slots=True)
class MovementStatus:
    target_position: int
    current_position: int
    position_error: int
    moving: bool
    within_tolerance: bool


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

    def is_moving(self) -> bool:
        moving, result, error = self.servo.ReadMoving(self.servo_id)

        validate_result(
            self.servo,
            result,
            error,
            f"{self.name}: leitura do estado de movimento",
        )

        return moving != 0

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

    @staticmethod
    def position_error(
        target_position: int,
        current_position: int,
    ) -> int:
        if type(target_position) is not int:
            raise TypeError("target_position deve ser inteiro")

        if type(current_position) is not int:
            raise TypeError("current_position deve ser inteiro")

        return abs(target_position - current_position)

    def is_within_tolerance(
        self,
        target_position: int,
        current_position: int,
    ) -> bool:
        error = self.position_error(
            target_position,
            current_position,
        )

        return error <= self.config.tolerance_counts

    def movement_status(
        self,
        target_position: int,
    ) -> MovementStatus:
        current_position = self.current_position()
        moving = self.is_moving()

        position_error = self.position_error(
            target_position,
            current_position,
        )

        within_tolerance = self.is_within_tolerance(
            target_position,
            current_position,
        )

        return MovementStatus(
            target_position=target_position,
            current_position=current_position,
            position_error=position_error,
            moving=moving,
            within_tolerance=within_tolerance,
        )

    @staticmethod
    def _validate_wait_parameter(
        parameter_name: str,
        value: float,
    ) -> None:
        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise TypeError(f"{parameter_name} deve ser um número")

        if not isfinite(value):
            raise ValueError(f"{parameter_name} deve ser finito")

        if value <= 0:
            raise ValueError(f"{parameter_name} deve ser maior que zero")

    def command(
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

        print(
            f"{self.name}: comando enviado para "
            f"{angle:.2f}° "
            f"({target_position} counts)"
        )

        return target_position

    def move(
        self,
        angle: float,
        speed: int | None = None,
        acc: int | None = None,
        timeout: float = 5.0,
        poll_interval: float = 0.05,
    ) -> MovementStatus:
        self._validate_wait_parameter(
            "timeout",
            timeout,
        )

        self._validate_wait_parameter(
            "poll_interval",
            poll_interval,
        )

        target_position = self.command(
            angle=angle,
            speed=speed,
            acc=acc,
        )

        deadline = monotonic() + timeout

        while True:
            status = self.movement_status(target_position)

            if status.within_tolerance:
                return status

            if not status.moving:
                raise RuntimeError(
                    f"{self.name}: servo parou fora do alvo "
                    f"(alvo={status.target_position}, "
                    f"posição={status.current_position}, "
                    f"erro={status.position_error} counts, "
                    f"tolerância="
                    f"{self.config.tolerance_counts} counts)"
                )

            remaining_time = deadline - monotonic()

            if remaining_time <= 0:
                raise TimeoutError(
                    f"{self.name}: timeout após "
                    f"{timeout:.3f}s "
                    f"(alvo={status.target_position}, "
                    f"posição={status.current_position}, "
                    f"erro={status.position_error} counts)"
                )

            sleep(
                min(
                    poll_interval,
                    remaining_time,
                )
            )
