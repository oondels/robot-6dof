from src.application.ports.control_input import ControlInput, ControlState
from pynput import keyboard
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KeyBinding:
    name: str
    key: keyboard.Key | keyboard.KeyCode


class KeyBoardInput(ControlInput):
    def __init__(self, bindings: tuple[KeyBinding, ...]) -> None:
        self._key_bindings = bindings

        self._pressed_keys = set()
        self._down_keys = set()
        self._released_keys = set()

        self._listener = None

    def open(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )

        self._listener.start()

    def _on_press(self, key) -> None:
        if key not in self._down_keys:
            self._pressed_keys.add(key)

        self._down_keys.add(key)

    def _on_release(self, key) -> None:
        self._down_keys.discard(key)
        self._released_keys.add(key)

    def is_pressed(self, binding: KeyBinding) -> bool:
        return binding.key in self._pressed_keys

    def is_held(self, binding: KeyBinding) -> bool:
        return binding.key in self._down_keys

    def is_released(self, binding: KeyBinding) -> bool:
        return binding.key in self._released_keys

    def read(self) -> ControlState:
        pressed = frozenset(
            binding.name for binding in self._key_bindings if self.is_pressed(binding)
        )

        held = frozenset(
            binding.name for binding in self._key_bindings if self.is_held(binding)
        )

        released = frozenset(
            binding.name for binding in self._key_bindings if self.is_released(binding)
        )

        state = ControlState(
            axes={},
            buttons_pressed=pressed,
            buttons_held=held,
            buttons_released=released,
            timestamp=0.0,
            delta_time=0.0,
            movement_enabled=True,
            emergency_stop=False,
        )

        # Eventos de borda são consumidos.
        self._pressed_keys.clear()
        self._released_keys.clear()

        return state

    def is_available(self) -> bool:
        return True

    def reset(self) -> None:
        self.close()
        self.open()

    def close(self) -> None:
        if self._listener:
            self._listener.stop()
        self._pressed_keys.clear()
        self._down_keys.clear()
        self._released_keys.clear()
