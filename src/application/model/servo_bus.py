from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from src.infrastructure.scservo_bus import ScServoBus


@dataclass(frozen=True, slots=True)
class ServoPositionCommand:
    """Dados necessários para comandar a posição de um servo."""

    servo_id: int
    position: int
    speed: int
    acceleration: int


class ServoBus(Protocol):
    """Porta de comunicação exigida pelo núcleo de controle do robô."""

    def read_position(self, servo_id: int) -> int:
        """Retorna a posição atual do servo em counts."""
        ...

    def is_moving(self, servo_id: int) -> bool:
        """Informa se o servo está executando um movimento."""
        ...

    def command_position(
        self,
        servo_id: int,
        position: int,
        speed: int,
        acceleration: int,
    ) -> None:
        """Envia um comando de posição sem aguardar sua conclusão."""
        ...

    def is_torque_enabled(self, servo_id: int) -> bool:
        """Informa se o torque do servo está habilitado."""
        ...

    def enable_torque(self, servo_id: int) -> None:
        """Habilita o torque do servo."""
        ...

    def disable_torque(self, servo_id: int) -> None:
        """Desabilita o torque do servo."""
        ...

    def command_positions_sync(
        self,
        commands: Sequence[ServoPositionCommand],
    ) -> None:
        """Transmite um conjunto de comandos de posição sincronizados."""
        ...
