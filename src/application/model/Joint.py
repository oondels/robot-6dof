from .ServoBus import ServoBus
from .JointConfig import JointConfig
from .MovementStatus import MovementStatus
from typing import Any


class Joint:
    def __init__(self, config: JointConfig, servo_bus: ServoBus) -> None:
        """Inicializa a junta com a configuração e o barramento de servo fornecidos."""
        if servo_bus is None:
            raise ValueError("servo não pode ser None")

        if not isinstance(config, JointConfig):
            raise TypeError("config deve ser uma instância de JointConfig")

        self._config = config
        self._servo = servo_bus


    @property
    def name(self) -> str:
        return self._config.name

    @property
    def servo_id(self) -> int:
        return self._config.servo_id

    @property
    def speed(self) -> int:
        return self._config.speed

    @property
    def acc(self) -> int:
        return self._config.acc

    def current_position(self) -> int:
        """Lê a posição atual da junta em counts."""
        return self._servo.read_position(self._config.servo_id)

    def current_angle(self) -> float:
        """Converte a posição atual da junta em ângulo."""
        position = self.current_position()
        return self._config.position_to_angle(position)

    def is_torque_enabled(self) -> bool:
        """Verifica se o torque do servo da junta está habilitado."""
        return self._servo.is_torque_enabled(self._config.servo_id)

    def enable_torque(self) -> None:
        current_position = self.current_position()
        
        """Habilita o torque do servo da junta."""
        self._servo.enable_torque(self._config.servo_id)

    def disable_torque(self) -> None:
        """Desabilita o torque do servo da junta."""
        self._servo.disable_torque(self._config.servo_id)

    def angle_to_position(self, angle: float) -> int:
        """Converte um ângulo em posição (counts) para a junta."""
        return self._config.angle_to_position(angle)

    def position_to_angle(self, position: int) -> float:
        """Converte uma posição (counts) em ângulo para a junta."""
        return self._config.position_to_angle(position)

    def is_moving(self) -> bool:
        """Verifica se a junta está em movimento."""
        return self._servo.is_moving(self._config.servo_id)
        
    @staticmethod
    def position_error(
        target_position: int,
        current_position: int,
    ) -> int:
        """Calcula a diferença absoluta entre a posição alvo e a posição atual."""
        # Verificacao para acoes de movimento da Joitn
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

        return error <= self._config.tolerance_counts

    def movement_status(
        self,
        target_position: int,
    ) -> Any:
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

        return MovementStatus (
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
        """Valida se o parâmetro de espera é um número finito."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{parameter_name} deve ser um número finito")

        if not (value >= 0):
            raise ValueError(f"{parameter_name} deve ser maior ou igual a zero")

    def command(
        self,
        angle: float,
        speed: int | None = None,
        acc: int | None = None,
    ) -> int:
        """Comanda a junta para mover-se para o ângulo especificado [Não espera servo chegar, apenas envia o comando]."""
        if speed is None:
            speed = self._config.speed
        else:
            self._config.validate_speed(speed)

        if acc is None:
            acc = self._config.acc
        else:
            self._config.validate_acceleration(acc)

        position = self.angle_to_position(angle)
        self._servo.command_position(
            self._config.servo_id,
            position,
            speed,
            acc,
        )
        return position
    
    def move(
        self,
        angle: float,
        speed: int | None = None,
        acc: int | None = None,
        timeout: float | None = None,
        poll_interval: float = 0.1, # Tempo em segundos entre cada verificação do status do movimento
    ) -> MovementStatus:
        """Comanda a junta para mover-se para o ângulo especificado e aguarda até que o movimento seja concluído ou o tempo limite seja atingido."""
        target_position = self.command(angle, speed, acc)

        if timeout is not None:
            self._validate_wait_parameter("timeout", timeout)
        self._validate_wait_parameter("poll_interval", poll_interval)

        import time
        start_time = time.time()

        while True:
            current_position = self.current_position()
            moving = self.is_moving()

            if not moving:
                break

            if timeout is not None and (time.time() - start_time) > timeout:
                break

            time.sleep(poll_interval)

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