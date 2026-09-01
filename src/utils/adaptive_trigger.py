import atexit
import math
import time
from typing import Protocol

from src.utils.dualsense_color import (
    DEFAULT_DUALSENSE_COLOR,
    DualSenseColorConfig,
)
from src.utils.validate_load import (
    BASE_LOAD_AT_REST,
    LOAD_MAGNITUDE_MASK,
    LOAD_PER_DEGREE_SECOND,
)

DEFAULT_TRIGGER_NAME = "l2"
TRIGGER_START_POSITION = 0
MAXIMUM_TRIGGER_FORCE = 200
OBJECT_HELD_TRIGGER_FORCE = 120
LOAD_EXCESS_START = 40.0
LOAD_EXCESS_FULL_FORCE = 400.0
LOAD_FILTER_ALPHA = 0.25
TRIGGER_FORCE_STEP = 8
MINIMUM_UPDATE_INTERVAL_S = 0.05


class TriggerEffect(Protocol):
    def continuous_resistance(
        self,
        start_position: int,
        force: int,
    ) -> None: ...

    def off(self) -> None: ...


class Trigger(Protocol):
    effect: TriggerEffect


class Lightbar(Protocol):
    def set_color(self, red: int, green: int, blue: int) -> None: ...


class DualSenseDevice(Protocol):
    left_trigger: Trigger
    right_trigger: Trigger
    lightbar: Lightbar

    def activate(self) -> None: ...

    def deactivate(self) -> None: ...


_controller: DualSenseDevice | None = None
_controller_initialization_failed = False
_filtered_load_excess = 0.0
_last_applied_force = 0
_last_update_time = 0.0
_active_trigger_name = DEFAULT_TRIGGER_NAME
_previous_trigger_value = 0.0


def _create_controller() -> DualSenseDevice:
    from dualsense_controller import DualSenseController

    return DualSenseController()


def _validate_inputs(
    raw_load: int,
    measured_velocity_deg_s: float,
    trigger_value: float,
    trigger_name: str,
) -> None:
    if isinstance(raw_load, bool) or not isinstance(raw_load, int):
        raise TypeError("raw_load deve ser inteiro")

    if isinstance(measured_velocity_deg_s, bool) or not isinstance(
        measured_velocity_deg_s,
        (int, float),
    ):
        raise TypeError("measured_velocity_deg_s deve ser numérica")

    if not math.isfinite(measured_velocity_deg_s):
        raise ValueError("measured_velocity_deg_s deve ser finita")

    if isinstance(trigger_value, bool) or not isinstance(
        trigger_value,
        (int, float),
    ):
        raise TypeError("trigger_value deve ser numérico")

    if not math.isfinite(trigger_value):
        raise ValueError("trigger_value deve ser finito")

    if not 0.0 <= trigger_value <= 1.0:
        raise ValueError("trigger_value deve estar entre 0 e 1")

    if trigger_name not in {"l2", "r2"}:
        raise ValueError("trigger_name deve ser 'l2' ou 'r2'")


def _trigger_effect(
    controller: DualSenseDevice,
    trigger_name: str,
) -> TriggerEffect:
    trigger = (
        controller.left_trigger
        if trigger_name == "l2"
        else controller.right_trigger
    )
    return trigger.effect


def _load_excess(raw_load: int, measured_velocity_deg_s: float) -> float:
    load_magnitude = raw_load & LOAD_MAGNITUDE_MASK
    expected_movement_load = (
        BASE_LOAD_AT_REST
        + LOAD_PER_DEGREE_SECOND * abs(measured_velocity_deg_s)
    )
    return max(0.0, load_magnitude - expected_movement_load)


def _force_from_load_excess(load_excess: float) -> int:
    if load_excess <= LOAD_EXCESS_START:
        return 0

    usable_range = LOAD_EXCESS_FULL_FORCE - LOAD_EXCESS_START
    normalized_load = min(
        1.0,
        (load_excess - LOAD_EXCESS_START) / usable_range,
    )
    unquantized_force = normalized_load * MAXIMUM_TRIGGER_FORCE
    quantized_force = (
        round(unquantized_force / TRIGGER_FORCE_STEP)
        * TRIGGER_FORCE_STEP
    )
    return min(MAXIMUM_TRIGGER_FORCE, quantized_force)


def _initialize_controller() -> DualSenseDevice | None:
    global _controller
    global _controller_initialization_failed

    if _controller is not None:
        return _controller

    if _controller_initialization_failed:
        return None

    controller: DualSenseDevice | None = None
    try:
        controller = _create_controller()
        controller.activate()
        controller.lightbar.set_color(
            DEFAULT_DUALSENSE_COLOR.red,
            DEFAULT_DUALSENSE_COLOR.green,
            DEFAULT_DUALSENSE_COLOR.blue,
        )
    except Exception as error:
        if controller is not None:
            try:
                controller.deactivate()
            except Exception:
                pass
        _controller_initialization_failed = True
        print(f"[GATILHO PS5] Feedback adaptativo indisponível: {error}")
        return None

    _controller = controller
    return _controller


def set_dualsense_color(color: DualSenseColorConfig) -> bool:
    """Aplica uma cor RGB usando a conexão HID já existente do DualSense."""
    if not isinstance(color, DualSenseColorConfig):
        raise TypeError("color deve ser uma instância de DualSenseColorConfig")

    controller = _initialize_controller()
    if controller is None:
        return False

    try:
        controller.lightbar.set_color(color.red, color.green, color.blue)
    except Exception as error:
        print(f"[CONTROLE PS5] Falha ao alterar cor: {error}")
        return False

    return True


def _turn_off_effect(reset_filter: bool) -> None:
    global _filtered_load_excess
    global _last_applied_force
    global _last_update_time
    global _previous_trigger_value

    if _controller is not None and _last_applied_force != 0:
        try:
            _trigger_effect(_controller, _active_trigger_name).off()
        except Exception as error:
            print(f"[GATILHO PS5] Falha ao remover resistência: {error}")

    _last_applied_force = 0
    _last_update_time = 0.0
    if reset_filter:
        _filtered_load_excess = 0.0
        _previous_trigger_value = 0.0


def _shutdown_controller() -> None:
    global _controller
    global _controller_initialization_failed
    global _active_trigger_name
    global _previous_trigger_value

    controller = _controller
    _turn_off_effect(reset_filter=True)

    if controller is not None:
        try:
            controller.left_trigger.effect.off()
            controller.right_trigger.effect.off()
        except Exception as error:
            print(f"[GATILHO PS5] Falha ao remover efeitos: {error}")

        try:
            controller.deactivate()
        except Exception as error:
            print(f"[GATILHO PS5] Falha ao encerrar feedback: {error}")

    _controller = None
    _controller_initialization_failed = False
    _active_trigger_name = DEFAULT_TRIGGER_NAME
    _previous_trigger_value = 0.0


def apply_load_to_adaptive_trigger(
    raw_load: int,
    measured_velocity_deg_s: float,
    trigger_value: float,
    trigger_name: str = DEFAULT_TRIGGER_NAME,
    shutdown: bool = False,
    initialize: bool = False,
    hold_force: bool = False,
) -> int:
    """Aplica no gatilho uma resistência proporcional ao load excedente.

    Esta é a única função pública necessária para operar o feedback. O
    controlador HID é aberto somente quando uma força precisa ser aplicada.
    Informe ``hold_force=True`` enquanto o robô estiver segurando um objeto,
    ``initialize=True`` na inicialização da feature e ``shutdown=True``
    durante emergência ou encerramento do programa.
    """
    global _active_trigger_name
    global _filtered_load_excess
    global _last_applied_force
    global _last_update_time
    global _previous_trigger_value

    if shutdown:
        _shutdown_controller()
        return 0

    if initialize:
        _initialize_controller()
        return 0

    _validate_inputs(
        raw_load,
        measured_velocity_deg_s,
        trigger_value,
        trigger_name,
    )

    trigger_pressed_again = (
        _previous_trigger_value == 0.0
        and trigger_value > 0.0
    )
    _previous_trigger_value = trigger_value

    if trigger_value == 0.0 and not hold_force:
        _turn_off_effect(reset_filter=True)
        return 0

    if hold_force:
        desired_force = max(
            _last_applied_force,
            OBJECT_HELD_TRIGGER_FORCE,
        )
    else:
        current_load_excess = _load_excess(
            raw_load,
            measured_velocity_deg_s,
        )
        _filtered_load_excess = (
            LOAD_FILTER_ALPHA * current_load_excess
            + (1.0 - LOAD_FILTER_ALPHA) * _filtered_load_excess
        )
        desired_force = _force_from_load_excess(_filtered_load_excess)

    if desired_force == 0:
        _turn_off_effect(reset_filter=False)
        return 0

    current_time = time.monotonic()
    update_interval = current_time - _last_update_time
    if not trigger_pressed_again and (
        desired_force == _last_applied_force
        or update_interval < MINIMUM_UPDATE_INTERVAL_S
    ):
        return _last_applied_force

    controller = _initialize_controller()
    if controller is None:
        return 0

    if _active_trigger_name != trigger_name and _last_applied_force != 0:
        _trigger_effect(controller, _active_trigger_name).off()

    try:
        _trigger_effect(controller, trigger_name).continuous_resistance(
            start_position=TRIGGER_START_POSITION,
            force=desired_force,
        )
    except Exception as error:
        print(f"[GATILHO PS5] Falha ao aplicar resistência: {error}")
        _turn_off_effect(reset_filter=True)
        return 0

    _active_trigger_name = trigger_name
    _last_applied_force = desired_force
    _last_update_time = current_time
    return _last_applied_force


atexit.register(_shutdown_controller)
