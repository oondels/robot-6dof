from src.application.ports.control_input import ControlState
from src.infrastructure.input.ps5_controller import (
    Ps5ControllerInput,
    find_ps5_controller_device,
)


def observable_state(state: ControlState) -> dict[str, object]:
    """Campos relevantes para diagnosticar a entrada do operador."""
    return {
        "axes": dict(state.axes),
        "buttons_pressed": state.buttons_pressed,
        "buttons_held": state.buttons_held,
        "buttons_released": state.buttons_released,
        "movement_enabled": state.movement_enabled,
        "emergency_stop": state.emergency_stop,
    }


def changed_fields(
    previous: dict[str, object], current: dict[str, object]
) -> dict[str, object]:
    return {name: value for name, value in current.items() if value != previous[name]}

controller = Ps5ControllerInput(device_path=find_ps5_controller_device())
controller.open()

previous_state = observable_state(controller.read())
while True:
    current_state = observable_state(controller.read())
    changes = changed_fields(previous_state, current_state)
    if changes:
        print(changes)
    previous_state = current_state
