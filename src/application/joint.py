from dataclasses import dataclass, field
from math import isfinite
from time import monotonic, sleep

from .joint_config import JointConfig
from .movement_status import MovementStatus
from .ports.servo_bus import ServoBus


# TODO: Implementar consulta periodica da junta para coleta de informaceos, geracao de metricas, graficos, controle, etc
@dataclass(frozen=True, slots=True)
class JointStatus:
    """Dados essenciais sobre o estado da junta."""

    position: int
    speed: int
    acceleration: int
    voltage: float
    current: float
    temperature: float
    load: int
    timestamp: float = field(default_factory=monotonic)


class Joint:
    def __init__(self, config: JointConfig, servo_bus: ServoBus) -> None:
        """Inicializa a junta com a configuração e o barramento de servo fornecidos."""
        if servo_bus is None:
            raise ValueError("servo não pode ser None")

        if not isinstance(config, JointConfig):
            raise TypeError("config deve ser uma instância de JointConfig")

        self._config = config
        self._servo_bus = servo_bus
        self._status: JointStatus | None = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def config(self) -> JointConfig:
        """Retorna a configuração imutável da junta."""
        return self._config

    @property
    def servo_id(self) -> int:
        return self._config.servo_id

    # Verificar se a alteracao de velocidade e aceleracao durante uso reflete na classe ou fica presa a arquivo
    @property
    def speed(self) -> int:
        return self._config.speed

    @property
    def acc(self) -> int:
        return self._config.acc

    @property
    def tolerance_counts(self) -> int:
        return self._config.tolerance_counts

    def get_status(self) -> JointStatus:
        """Coleta, armazena e retorna o status atual da junta."""
        self._status = JointStatus(
            position=self.current_position(),
            load=self.current_load(),
            speed=self.speed,
            acceleration=self.acc,
            voltage=self.current_voltage(),
            current=self.current_current(),
            temperature=self.current_temperature(),
            timestamp=monotonic(),
        )

        return self._status

    @property
    def status(self) -> JointStatus | None:
        """Retorna o último status coletado sem consultar o hardware."""
        return self._status
    
    def current_position(self) -> int:
        """Lê a posição atual da junta em counts."""
        return self._servo_bus.read_position(self.servo_id)

    def current_load(self) -> int:
        """Lê a carga atual da junta em counts."""
        return self._servo_bus.read_load(self.servo_id)

    def current_voltage(self) -> float:
        """Lê a tensão atual da junta em volts."""
        return self._servo_bus.read_voltage(self.servo_id)

    def current_temperature(self) -> float:
        """Lê a temperatura atual da junta em graus Celsius."""
        return self._servo_bus.read_temperature(self.servo_id)

    def current_current(self) -> float:
        """Lê a corrente atual da junta em amperes."""
        return self._servo_bus.read_current(self.servo_id)

    def current_angle(self) -> float:
        """Converte a posição atual da junta em ângulo."""
        position = self.current_position()
        return self._config.position_to_angle(position)

    def is_torque_enabled(self) -> bool:
        """Verifica se o torque do servo da junta está habilitado."""
        return self._servo_bus.is_torque_enabled(self.servo_id)

    def enable_torque(self) -> None:
        """Habilita o torque sem buscar um alvo antigo do servo."""
        current_position = self.current_position()
        self._servo_bus.command_position(
            self.servo_id,
            current_position,
            self.speed,
            self.acc,
        )
        self._servo_bus.enable_torque(self.servo_id)

        if not self.is_torque_enabled():
            raise RuntimeError(f"{self.name}: torque não foi habilitado")

    def disable_torque(self) -> None:
        """Desabilita o torque do servo da junta."""
        self._servo_bus.disable_torque(self.servo_id)

        if self.is_torque_enabled():
            raise RuntimeError(f"{self.name}: torque não foi desabilitado")

    def angle_to_position(self, angle: float) -> int:
        """Converte um ângulo em posição (counts) para a junta."""
        return self._config.angle_to_position(angle)

    def position_to_angle(self, position: int) -> float:
        """Converte uma posição (counts) em ângulo para a junta."""
        return self._config.position_to_angle(position)

    def is_moving(self) -> bool:
        """Verifica se a junta está em movimento."""
        return self._servo_bus.is_moving(self.servo_id)

    @staticmethod
    def position_error(
        target_position: int,
        current_position: int,
    ) -> int:
        """Calcula a diferença absoluta entre a posição alvo e a posição atual."""
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
        """Verifica se a posição atual está dentro da tolerância da posição alvo."""
        error = self.position_error(
            target_position,
            current_position,
        )

        return error <= self.tolerance_counts

    def movement_status(
        self,
        target_position: int,
    ) -> MovementStatus:
        """Retorna o status do movimento da junta em relação à posição alvo."""
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
        """Valida um intervalo de espera usado no controle de movimento."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
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
        """Envia um comando de posição sem aguardar sua conclusão."""
        command_speed = self.speed if speed is None else speed
        command_acc = self.acc if acc is None else acc

        JointConfig.validate_speed(command_speed)
        JointConfig.validate_acceleration(command_acc)

        position = self.angle_to_position(angle)
        self._servo_bus.command_position(
            self.servo_id,
            position,
            command_speed,
            command_acc,
        )
        return position

    def move(
        self,
        angle: float,
        speed: int | None = None,
        acc: int | None = None,
        timeout: float = 5.0,
        poll_interval: float = 0.05,
    ) -> MovementStatus:
        """Envia o movimento e aguarda o alvo ou uma condição de falha."""
        self._validate_wait_parameter("timeout", timeout)
        self._validate_wait_parameter("poll_interval", poll_interval)

        target_position = self.command(angle, speed, acc)
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
                    f"tolerância={self.tolerance_counts} counts)"
                )

            remaining_time = deadline - monotonic()
            if remaining_time <= 0:
                raise TimeoutError(
                    f"{self.name}: timeout após {timeout:.3f}s "
                    f"(alvo={status.target_position}, "
                    f"posição={status.current_position}, "
                    f"erro={status.position_error} counts)"
                )

            sleep(min(poll_interval, remaining_time))
