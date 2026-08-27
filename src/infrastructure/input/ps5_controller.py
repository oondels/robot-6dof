from collections.abc import Callable
import math
from time import monotonic
from typing import Protocol

from evdev import InputDevice, ecodes, list_devices
from src.application.ports.control_input import ControlInput, ControlState


class InputEvent(Protocol):
    """Evento mínimo recebido de um dispositivo evdev."""

    type: int
    code: int
    value: int


class ControllerDevice(Protocol):
    """Operações do evdev necessárias pelo adapter."""

    def read_one(self) -> InputEvent | None: ...

    def close(self) -> None: ...


DeviceFactory = Callable[[str], ControllerDevice]
DeviceLister = Callable[[], list[str]]
Clock = Callable[[], float]


def find_ps5_controller_device(
    device_lister: DeviceLister = list_devices,
    device_factory: DeviceFactory = InputDevice,
) -> str:
    """Encontra o único DualSense disponível nos dispositivos evdev.

    Os caminhos ``/dev/input/eventN`` são atribuídos dinamicamente pelo Linux;
    portanto, eles não devem ser tratados como uma configuração estável.
    """
    candidates: list[tuple[str, str]] = []
    inspected_devices: list[tuple[str, str]] = []
    inaccessible_paths: list[str] = []
    unavailable_paths: list[str] = []

    for path in device_lister():
        device: ControllerDevice | None = None
        try:
            device = device_factory(path)
            name = str(getattr(device, "name", "desconhecido"))
            inspected_devices.append((path, name))
            if _is_ps5_controller_name(name):
                candidates.append((path, name))
        except PermissionError:
            inaccessible_paths.append(path)
        except OSError:
            unavailable_paths.append(path)
        finally:
            if device is not None:
                try:
                    device.close()
                except OSError:
                    pass

    if len(candidates) == 1:
        return candidates[0][0]

    if len(candidates) > 1:
        formatted_candidates = _format_devices(candidates)
        raise ConnectionError(
            "Mais de um controle PS5/DualSense foi encontrado: "
            f"{formatted_candidates}. Desconecte os controles extras e tente novamente."
        )

    details = _format_discovery_details(
        inspected_devices,
        inaccessible_paths,
        unavailable_paths,
    )
    raise ConnectionError(
        "Nenhum controle PS5/DualSense foi encontrado automaticamente. "
        f"{details}"
    )


def _is_ps5_controller_name(name: str) -> bool:
    normalized_name = name.strip().casefold()
    auxiliary_interfaces = ("touchpad", "motion sensors")
    if any(interface in normalized_name for interface in auxiliary_interfaces):
        return False

    return "dualsense" in normalized_name or normalized_name == "wireless controller"


def _format_discovery_details(
    inspected_devices: list[tuple[str, str]],
    inaccessible_paths: list[str],
    unavailable_paths: list[str],
) -> str:
    details: list[str] = []
    if inspected_devices:
        details.append(f"Dispositivos lidos: {_format_devices(inspected_devices)}.")
    if inaccessible_paths:
        details.append(
            "Sem permissão para ler: "
            f"{', '.join(inaccessible_paths)}. Verifique o grupo 'input' ou as regras udev."
        )
    if unavailable_paths:
        details.append(f"Indisponíveis durante a leitura: {", ".join(unavailable_paths)}.")
    return " ".join(details) or "Nenhum dispositivo evdev foi listado pelo Linux."


def _format_devices(devices: list[tuple[str, str]]) -> str:
    return ", ".join(f"{path} ({name})" for path, name in devices)

BUTTON_NAMES = {
    ecodes.BTN_SOUTH: "cross",
    ecodes.BTN_EAST: "circle",
    ecodes.BTN_NORTH: "triangle",
    ecodes.BTN_WEST: "square",
    ecodes.BTN_TL: "l1",
    ecodes.BTN_TR: "r1",
    ecodes.BTN_TL2: "l2",
    ecodes.BTN_TR2: "r2",
    ecodes.BTN_SELECT: "share",
    ecodes.BTN_START: "options",
    ecodes.BTN_MODE: "ps",
    ecodes.BTN_THUMBL: "l3",
    ecodes.BTN_THUMBR: "r3",
}

AXIS_NAMES = {
    ecodes.ABS_X: "left_x",
    ecodes.ABS_Y: "left_y",
    ecodes.ABS_RX: "right_x",
    ecodes.ABS_RY: "right_y",
    ecodes.ABS_Z: "l2",
    ecodes.ABS_RZ: "r2",
    ecodes.ABS_HAT0X: "dpad_x",
    ecodes.ABS_HAT0Y: "dpad_y",
}

DEFAULT_AXES = frozenset(AXIS_NAMES.values())
STICK_AXIS_NAMES = frozenset({"left_x", "left_y", "right_x", "right_y"})
STICK_CENTER = 128
STICK_MAXIMUM = 255


class Ps5ControllerInput(ControlInput):
    """Adapter evdev para o controle PS5/DualSense em Linux.

    O adapter entrega estado de entrada normalizado. Ele não possui conhecimento
    de juntas, cinemática ou comandos de movimento do braço robótico.
    """

    def __init__(
        self,
        device_path: str,
        device_factory: DeviceFactory = InputDevice,
        clock: Clock = monotonic,
    ) -> None:
        if not device_path:
            raise ValueError("device_path não pode estar vazio")

        self._device_path = device_path
        self._device_factory = device_factory
        self._clock = clock
        self._controller: ControllerDevice | None = None

        self._deadzone = 0.03

        self._axes: dict[str, float] = self._new_axes()
        self._raw_stick_axes: dict[str, float] = self._new_stick_axes()
        self._buttons_pressed: set[str] = set()
        self._buttons_held: set[str] = set()
        self._buttons_released: set[str] = set()
        self._last_timestamp: float | None = None

        self._movement_enabled = False
        self._emergency_stop = False

    def open(self) -> None:
        """Abre o dispositivo configurado e inicia o controle desarmado."""
        if self._controller is not None:
            return

        try:
            self._controller = self._device_factory(self._device_path)
        except OSError as error:
            raise ConnectionError(
                f"Não foi possível abrir o controle PS5 em {self._device_path}"
            ) from error

        self._clear_transient_state()
        self._movement_enabled = False

    def read(self) -> ControlState:
        """Retorna o snapshot atual sem bloquear o ciclo de controle."""
        if self._controller is None:
            raise RuntimeError("O controle PS5 não está aberto")

        try:
            while (event := self._controller.read_one()) is not None:
                self._process_event(event)
        except OSError as error:
            self._handle_disconnection()
            raise ConnectionError("Conexão com o controle PS5 foi perdida") from error

        self._update_emergency_stop()
        timestamp = self._clock()
        delta_time = (
            0.0 if self._last_timestamp is None else timestamp - self._last_timestamp
        )
        self._last_timestamp = timestamp

        state = ControlState(
            axes=dict(self._axes),
            buttons_pressed=frozenset(self._buttons_pressed),
            buttons_held=frozenset(self._buttons_held),
            buttons_released=frozenset(self._buttons_released),
            timestamp=timestamp,
            delta_time=delta_time,
            movement_enabled=self._movement_enabled,
            emergency_stop=self._emergency_stop,
        )

        self._buttons_pressed.clear()
        self._buttons_released.clear()
        return state

    def is_available(self) -> bool:
        """Informa se há um dispositivo aberto e sem desconexão conhecida."""
        return self._controller is not None

    def reset(self) -> None:
        """Limpa entradas transitórias sem remover uma emergência latched."""
        self._clear_transient_state()
        self._movement_enabled = False

    def close(self) -> None:
        """Fecha o dispositivo e deixa o adapter em estado seguro."""
        controller = self._controller
        self._controller = None

        if controller is not None:
            try:
                controller.close()
            except OSError:
                pass

        self._clear_transient_state()
        self._movement_enabled = False

    def _process_event(self, event: InputEvent) -> None:
        if event.type == ecodes.EV_KEY:
            self._process_button_event(event.code, event.value)
        elif event.type == ecodes.EV_ABS:
            self._process_axis_event(event.code, event.value)

    def _process_button_event(self, code: int, value: int) -> None:
        name = BUTTON_NAMES.get(code)
        if name is None:
            return

        if value == 0:
            self._buttons_held.discard(name)
            self._buttons_released.add(name)
            return

        if name not in self._buttons_held:
            self._buttons_pressed.add(name)
        self._buttons_held.add(name)

        if name == "ps" and value == 1:
            self._toggle_movement()

    def _process_axis_event(self, code: int, value: int) -> None:
        name = AXIS_NAMES.get(code)
        if name is None:
            return

        # Aplica normalização e deadzone
        if name in STICK_AXIS_NAMES:
            normalized_value = self._normalize_stick(value)
            self._raw_stick_axes[name] = (
                normalized_value if name.endswith("_x") else -normalized_value
            )
            self._update_stick_axes(name.split("_", maxsplit=1)[0])
        elif name in {"l2", "r2"}:
            self._axes[name] = self._normalize_trigger(value)
        elif name == "dpad_y":
            self._axes[name] = float(-value)
        else:
            self._axes[name] = float(value)

    def _radial_stick_deadzone(self, x_value: float, y_value: float) -> dict[str, float]:
        magnitude = math.sqrt(x_value**2 + y_value**2)

        if magnitude > 1.0:
            x_value /= magnitude
            y_value /= magnitude
            magnitude = 1.0

        if magnitude <= self._deadzone:
            return {"x": 0.0, "y": 0.0}

        scale = (magnitude - self._deadzone) / (magnitude * (1.0 - self._deadzone))
        return {"x": scale * x_value, "y": scale * y_value}

    def _update_stick_axes(self, stick_name: str) -> None:
        filtered_axes = self._radial_stick_deadzone(
            self._raw_stick_axes[f"{stick_name}_x"],
            self._raw_stick_axes[f"{stick_name}_y"],
        )
        self._axes[f"{stick_name}_x"] = filtered_axes["x"]
        self._axes[f"{stick_name}_y"] = filtered_axes["y"]

    def _toggle_movement(self) -> None:
        if self._emergency_stop:
            self._emergency_stop = False
            self._movement_enabled = True
            return

        self._movement_enabled = not self._movement_enabled

    def _update_emergency_stop(self) -> None:
        l2_active = self._axes["l2"] > 0.0 or "l2" in self._buttons_held
        r2_active = self._axes["r2"] > 0.0 or "r2" in self._buttons_held

        if l2_active and r2_active:
            self._emergency_stop = True
            self._movement_enabled = False

    def _handle_disconnection(self) -> None:
        self._controller = None
        self._clear_transient_state()
        self._movement_enabled = False
        self._emergency_stop = True

    def _clear_transient_state(self) -> None:
        self._axes = self._new_axes()
        self._raw_stick_axes = self._new_stick_axes()
        self._buttons_pressed.clear()
        self._buttons_held.clear()
        self._buttons_released.clear()
        self._last_timestamp = None

    @staticmethod
    def _new_axes() -> dict[str, float]:
        return {name: 0.0 for name in DEFAULT_AXES}

    @staticmethod
    def _new_stick_axes() -> dict[str, float]:
        return {name: 0.0 for name in STICK_AXIS_NAMES}

    @staticmethod
    def _normalize_stick(value: int) -> float:
        normalized = (value - STICK_CENTER) / (STICK_MAXIMUM - STICK_CENTER)
        return max(-1.0, min(1.0, normalized))

    @staticmethod
    def _normalize_trigger(value: int) -> float:
        normalized = value / STICK_MAXIMUM
        return max(0.0, min(1.0, normalized))
