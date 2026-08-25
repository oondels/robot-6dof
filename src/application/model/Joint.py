class Joint(config: JointConfig, servo_bus: ServoBus):
    """Representa uma junta do robô, que é controlada por um servo motor."""
    def __init__(self, config: JointConfig, servo_bus: ServoBus) -> None:
        """Inicializa a junta com a configuração e o barramento de servo fornecidos."""
        self._config = config
        self._servo_bus = servo_bus
    
    def read_position(self) -> int:
        """Lê a posição atual da junta em counts."""
        return self._servo_bus.read_position(self._config.servo_id)