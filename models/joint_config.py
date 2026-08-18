from dataclasses import dataclass
from math import isfinite

DEFAULT_SPEED = 1000
DEFAULT_ACC = 100
DEFAULT_TOLERANCE_DEG = 1.0

MIN_SPEED = 0
MAX_SPEED = 3400

MIN_ACC = 0
MAX_ACC = 254

MIN_SERVO_ID = 0
MAX_SERVO_ID = 253

MIN_SERVO_POSITION = 0
MAX_SERVO_POSITION = 4095

STEPS_PER_REVOLUTION = 4096


@dataclass(frozen=True, slots=True)
class JointConfig:
    name: str
    servo_id: int

    zero_position: int
    direction: int

    min_angle: float
    max_angle: float

    speed: int = DEFAULT_SPEED
    acc: int = DEFAULT_ACC
    tolerance_deg: float = DEFAULT_TOLERANCE_DEG

    def __post_init__(self) -> None:
        self._validate_name()
        self._validate_servo_id()
        self._validate_zero_position()
        self._validate_direction()
        self._validate_angles()
        self.validate_speed(self.speed)
        self.validate_acceleration(self.acc)
        self._validate_tolerance()
        self._validate_mapped_positions()

        object.__setattr__(
            self,
            "name",
            self.name.strip(),
        )

        object.__setattr__(
            self,
            "min_angle",
            float(self.min_angle),
        )

        object.__setattr__(
            self,
            "max_angle",
            float(self.max_angle),
        )

        object.__setattr__(
            self,
            "tolerance_deg",
            float(self.tolerance_deg),
        )

    def angle_to_position(self, angle: float) -> int:
        self._validate_finite_number("angle", angle)

        if not self.min_angle <= angle <= self.max_angle:
            raise ValueError(
                f"{self.name}: ângulo {angle}° fora do limite "
                f"[{self.min_angle}°, {self.max_angle}°]"
            )

        return self._position_without_validation(angle)

    def position_to_angle(self, position: int) -> float:
        if type(position) is not int:
            raise TypeError("position deve ser um número inteiro")

        first_limit = self._position_without_validation(self.min_angle)
        second_limit = self._position_without_validation(self.max_angle)

        min_position = min(first_limit, second_limit)
        max_position = max(first_limit, second_limit)

        if not min_position <= position <= max_position:
            raise ValueError(
                f"{self.name}: posição {position} fora do intervalo "
                f"calibrado [{min_position}, {max_position}]"
            )

        return (
            (position - self.zero_position)
            * 360.0
            / (self.direction * STEPS_PER_REVOLUTION)
        )

    def _validate_name(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError("name deve ser uma string")

        if not self.name.strip():
            raise ValueError("name não pode estar vazio")

    def _validate_servo_id(self) -> None:
        if type(self.servo_id) is not int:
            raise TypeError("servo_id deve ser um número inteiro")

        if not MIN_SERVO_ID <= self.servo_id <= MAX_SERVO_ID:
            raise ValueError(
                f"servo_id deve estar entre " f"{MIN_SERVO_ID} e {MAX_SERVO_ID}"
            )

    def _validate_zero_position(self) -> None:
        if type(self.zero_position) is not int:
            raise TypeError("zero_position deve ser um número inteiro")

        if not (MIN_SERVO_POSITION <= self.zero_position <= MAX_SERVO_POSITION):
            raise ValueError(
                f"zero_position deve estar entre "
                f"{MIN_SERVO_POSITION} e "
                f"{MAX_SERVO_POSITION}"
            )

    def _validate_direction(self) -> None:
        if type(self.direction) is not int:
            raise TypeError("direction deve ser um número inteiro")

        if self.direction not in (-1, 1):
            raise ValueError("direction deve ser -1 ou 1")

    def _validate_angles(self) -> None:
        self._validate_finite_number(
            "min_angle",
            self.min_angle,
        )

        self._validate_finite_number(
            "max_angle",
            self.max_angle,
        )

        if self.min_angle >= self.max_angle:
            raise ValueError("min_angle deve ser menor que max_angle")

        if not self.min_angle <= 0 <= self.max_angle:
            raise ValueError("O ângulo 0° deve estar dentro dos limites da junta")

    @staticmethod
    def validate_speed(speed: int) -> None:
        if type(speed) is not int:
            raise TypeError(
                "speed deve ser um número inteiro"
            )

        if not MIN_SPEED <= speed <= MAX_SPEED:
            raise ValueError(
                f"speed deve estar entre "
                f"{MIN_SPEED} e {MAX_SPEED}"
            )

    @staticmethod
    def validate_acceleration(acc: int) -> None:
        if type(acc) is not int:
            raise TypeError(
                "acc deve ser um número inteiro"
            )

        if not MIN_ACC <= acc <= MAX_ACC:
            raise ValueError(
                f"acc deve estar entre {MIN_ACC} e {MAX_ACC}"
            )

    def _validate_tolerance(self) -> None:
        self._validate_finite_number(
            "tolerance_deg",
            self.tolerance_deg,
        )

        if self.tolerance_deg <= 0:
            raise ValueError("tolerance_deg deve ser maior que zero")

    def _validate_mapped_positions(self) -> None:
        min_position = self._position_without_validation(self.min_angle)

        max_position = self._position_without_validation(self.max_angle)

        for position in (min_position, max_position):
            if not (MIN_SERVO_POSITION <= position <= MAX_SERVO_POSITION):
                raise ValueError(
                    "Os limites angulares geram uma posição "
                    f"fora de {MIN_SERVO_POSITION}.."
                    f"{MAX_SERVO_POSITION}: {position}"
                )

    def _position_without_validation(
        self,
        angle: float,
    ) -> int:
        return round(
            self.zero_position + self.direction * angle * STEPS_PER_REVOLUTION / 360.0
        )

    @staticmethod
    def _validate_finite_number(
        field_name: str,
        value: float,
    ) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field_name} deve ser um número")

        if not isfinite(value):
            raise ValueError(f"{field_name} deve ser um número finito")
