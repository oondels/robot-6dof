from collections import deque
from dataclasses import dataclass
from math import sqrt
import unittest

from evdev import ecodes

from src.infrastructure.input.ps5_controller import Ps5ControllerInput


@dataclass(frozen=True)
class FakeEvent:
    type: int
    code: int
    value: int


class FakeController:
    def __init__(self, events: list[FakeEvent] | None = None) -> None:
        self.events = deque(events or [])
        self.closed = False
        self.disconnect_on_read = False

    def read_one(self) -> FakeEvent | None:
        if self.disconnect_on_read:
            raise OSError("disconnected")
        return self.events.popleft() if self.events else None

    def close(self) -> None:
        self.closed = True


class Ps5ControllerInputTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = FakeController()
        self.opened_paths: list[str] = []
        self.times = iter((10.0, 10.02, 10.04, 10.06, 10.08, 10.10))
        self.input = Ps5ControllerInput(
            "/dev/input/event-test",
            device_factory=self._create_controller,
            clock=lambda: next(self.times),
        )

    def _create_controller(self, path: str) -> FakeController:
        self.opened_paths.append(path)
        return self.controller

    def read_events(self, *events: FakeEvent):
        self.controller.events.extend(events)
        return self.input.read()

    def test_open_and_close_manage_configured_device(self) -> None:
        self.assertFalse(self.input.is_available())
        self.input.open()
        self.assertTrue(self.input.is_available())
        self.assertEqual(self.opened_paths, ["/dev/input/event-test"])
        self.input.close()
        self.assertTrue(self.controller.closed)
        self.assertFalse(self.input.is_available())

    def test_read_requires_open_device(self) -> None:
        with self.assertRaises(RuntimeError):
            self.input.read()

    def test_normalizes_sticks_triggers_and_dpad(self) -> None:
        self.input.open()
        state = self.read_events(
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_X, 255),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_Y, 0),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_RX, 0),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_RY, 255),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_Z, 128),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_RZ, 255),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_HAT0X, -1),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_HAT0Y, -1),
        )
        self.assertAlmostEqual(state.axes["left_x"], 1 / sqrt(2))
        self.assertAlmostEqual(state.axes["left_y"], 1 / sqrt(2))
        self.assertAlmostEqual(state.axes["right_x"], -1 / sqrt(2))
        self.assertAlmostEqual(state.axes["right_y"], -1 / sqrt(2))
        self.assertEqual(state.axes["l2"], 128 / 255)
        self.assertEqual(state.axes["r2"], 1.0)
        self.assertEqual(state.axes["dpad_x"], -1.0)
        self.assertEqual(state.axes["dpad_y"], 1.0)

    def test_ignores_stick_variation_inside_radial_deadzone(self) -> None:
        self.input.open()

        state = self.read_events(
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_X, 130),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_Y, 127),
        )

        self.assertEqual(state.axes["left_x"], 0.0)
        self.assertEqual(state.axes["left_y"], 0.0)

    def test_applies_radial_deadzone_to_both_axes_of_a_stick(self) -> None:
        self.input.open()

        state = self.read_events(
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_X, 160),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_Y, 96),
        )

        self.assertGreater(state.axes["left_x"], 0.0)
        self.assertGreater(state.axes["left_y"], 0.0)
        self.assertLess(state.axes["left_x"], self.input._normalize_stick(160))
        self.assertLess(state.axes["left_y"], -self.input._normalize_stick(96))

    def test_button_edges_are_consumed_after_read(self) -> None:
        self.input.open()
        pressed = self.read_events(FakeEvent(ecodes.EV_KEY, ecodes.BTN_SOUTH, 1))
        held = self.input.read()
        released = self.read_events(FakeEvent(ecodes.EV_KEY, ecodes.BTN_SOUTH, 0))
        self.assertEqual(pressed.buttons_pressed, frozenset({"cross"}))
        self.assertEqual(pressed.buttons_held, frozenset({"cross"}))
        self.assertFalse(held.buttons_pressed)
        self.assertEqual(held.buttons_held, frozenset({"cross"}))
        self.assertEqual(released.buttons_released, frozenset({"cross"}))
        self.assertFalse(released.buttons_held)

    def test_ps_toggles_movement_enabled(self) -> None:
        self.input.open()
        armed = self.read_events(FakeEvent(ecodes.EV_KEY, ecodes.BTN_MODE, 1))
        self.read_events(FakeEvent(ecodes.EV_KEY, ecodes.BTN_MODE, 0))
        disarmed = self.read_events(FakeEvent(ecodes.EV_KEY, ecodes.BTN_MODE, 1))
        self.assertTrue(armed.movement_enabled)
        self.assertFalse(disarmed.movement_enabled)

    def test_trigger_pressures_are_preserved_and_trigger_emergency(self) -> None:
        self.input.open()
        state = self.read_events(
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_Z, 64),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_RZ, 192),
        )
        self.assertEqual(state.axes["l2"], 64 / 255)
        self.assertEqual(state.axes["r2"], 192 / 255)
        self.assertTrue(state.emergency_stop)
        self.assertFalse(state.movement_enabled)

    def test_ps_rearms_after_emergency_only_when_triggers_are_released(self) -> None:
        self.input.open()
        self.read_events(
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_Z, 255),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_RZ, 255),
        )
        self.read_events(
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_Z, 0),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_RZ, 0),
        )
        rearmed = self.read_events(FakeEvent(ecodes.EV_KEY, ecodes.BTN_MODE, 1))
        self.assertFalse(rearmed.emergency_stop)
        self.assertTrue(rearmed.movement_enabled)

    def test_reset_preserves_latched_emergency(self) -> None:
        self.input.open()
        self.read_events(
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_Z, 255),
            FakeEvent(ecodes.EV_ABS, ecodes.ABS_RZ, 255),
        )
        self.input.reset()
        state = self.input.read()
        self.assertTrue(state.emergency_stop)
        self.assertFalse(state.movement_enabled)
        self.assertEqual(state.axes["l2"], 0.0)
        self.assertEqual(state.axes["r2"], 0.0)

    def test_read_reports_monotonic_timestamp_and_delta_time(self) -> None:
        self.input.open()

        first = self.input.read()
        second = self.input.read()

        self.assertEqual(first.timestamp, 10.0)
        self.assertEqual(first.delta_time, 0.0)
        self.assertEqual(second.timestamp, 10.02)
        self.assertAlmostEqual(second.delta_time, 0.02)

    def test_disconnect_marks_adapter_unavailable_and_latches_emergency(self) -> None:
        self.input.open()
        self.controller.disconnect_on_read = True
        with self.assertRaises(ConnectionError):
            self.input.read()
        self.assertFalse(self.input.is_available())


if __name__ == "__main__":
    unittest.main()
