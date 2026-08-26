from src.application.ports.control_input import ControlInput
from src.application.robot_arm import RobotArm


class TeleOperation:
    def __init__(
        self,
        input_control_device: ControlInput,
        robot_arm: RobotArm,
        jog_speed: float = 30.0,
        button_mappings: dict[str, tuple[str, float]] | None = None,
        axis_mappings: dict[str, tuple[str, float]] | None = None,
    ) -> None:
        self._input_device = input_control_device
        self._arm = robot_arm
        self._jog_speed = jog_speed
        self._button_mappings = button_mappings or {}
        self._axis_mappings = axis_mappings or {}
        self._is_running = False

    @property
    def input_control_device(self) -> ControlInput:
        return self._input_device
    
    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def robot_arm(self) -> RobotArm:
        return self._arm
    
    def start(self) -> None:
        pass
    
    def stop(self) -> None:
        pass

    def step(self, dt: float) -> bool:
        """Executa um único tick / ciclo de controle discreto no tempo. """
        state = self._input_device.read()
        
        if (state.emergency_stop):
            self.stop()
            return False
        
        return True

    def run (self, frequency: float = 50.0) -> None:
        """Loop contínuo de tempo real para uso em produção."""
        pass

