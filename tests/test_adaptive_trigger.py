import unittest
from unittest.mock import patch

from src.utils import adaptive_trigger
from src.utils.adaptive_trigger import apply_load_to_adaptive_trigger


class FakeEffect:
    def __init__(self) -> None:
        self.resistances: list[tuple[int, int]] = []
        self.off_calls = 0

    def continuous_resistance(self, start_position: int, force: int) -> None:
        self.resistances.append((start_position, force))

    def off(self) -> None:
        self.off_calls += 1


class FakeTrigger:
    def __init__(self) -> None:
        self.effect = FakeEffect()


class FakeController:
    def __init__(self) -> None:
        self.left_trigger = FakeTrigger()
        self.right_trigger = FakeTrigger()
        self.activated = False
        self.deactivated = False

    def activate(self) -> None:
        self.activated = True

    def deactivate(self) -> None:
        self.deactivated = True


class AdaptiveTriggerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        adaptive_trigger._shutdown_controller()
        self.controller = FakeController()
        self.controller_factory = patch.object(
            adaptive_trigger,
            "_create_controller",
            return_value=self.controller,
        )
        self.controller_factory.start()
        self.clock = patch.object(
            adaptive_trigger.time,
            "monotonic",
            side_effect=(1.0, 1.1, 1.2, 1.3, 1.4, 1.5),
        )
        self.clock.start()

    def tearDown(self) -> None:
        adaptive_trigger._shutdown_controller()
        self.clock.stop()
        self.controller_factory.stop()

    def test_does_not_open_controller_for_normal_free_movement(self) -> None:
        force = apply_load_to_adaptive_trigger(
            raw_load=248,
            measured_velocity_deg_s=-49.3,
            trigger_value=1.0,
        )

        self.assertEqual(force, 0)
        self.assertFalse(self.controller.activated)

    def test_can_initialize_controller_before_applying_resistance(self) -> None:
        force = apply_load_to_adaptive_trigger(
            raw_load=0,
            measured_velocity_deg_s=0.0,
            trigger_value=0.0,
            initialize=True,
        )

        self.assertEqual(force, 0)
        self.assertTrue(self.controller.activated)
        self.assertEqual(self.controller.left_trigger.effect.resistances, [])
        self.assertEqual(self.controller.right_trigger.effect.resistances, [])

    def test_applies_progressive_resistance_for_sustained_excess_load(self) -> None:
        forces = [
            apply_load_to_adaptive_trigger(472, 0.0, 1.0)
            for _ in range(4)
        ]

        self.assertEqual(forces, sorted(forces))
        self.assertGreater(forces[-1], 0)
        self.assertLessEqual(forces[-1], 200)
        self.assertTrue(self.controller.activated)

    def test_ignores_load_direction_bit(self) -> None:
        positive_force = apply_load_to_adaptive_trigger(472, 0.0, 1.0)
        adaptive_trigger._shutdown_controller()
        negative_force = apply_load_to_adaptive_trigger(
            (1 << 10) | 472,
            0.0,
            1.0,
        )

        self.assertEqual(positive_force, negative_force)

    def test_can_apply_resistance_to_r2(self) -> None:
        force = apply_load_to_adaptive_trigger(
            raw_load=500,
            measured_velocity_deg_s=0.0,
            trigger_value=1.0,
            trigger_name="r2",
        )

        self.assertGreater(force, 0)
        self.assertEqual(self.controller.left_trigger.effect.resistances, [])
        self.assertNotEqual(self.controller.right_trigger.effect.resistances, [])

    def test_releasing_trigger_removes_resistance(self) -> None:
        apply_load_to_adaptive_trigger(500, 0.0, 1.0)

        force = apply_load_to_adaptive_trigger(0, 0.0, 0.0)

        self.assertEqual(force, 0)
        self.assertGreater(self.controller.left_trigger.effect.off_calls, 0)

    def test_shutdown_removes_effect_and_deactivates_controller(self) -> None:
        apply_load_to_adaptive_trigger(500, 0.0, 1.0)

        force = apply_load_to_adaptive_trigger(0, 0.0, 0.0, shutdown=True)

        self.assertEqual(force, 0)
        self.assertTrue(self.controller.deactivated)

    def test_rejects_invalid_trigger_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "l2.*r2"):
            apply_load_to_adaptive_trigger(100, 0.0, 1.0, trigger_name="x")


if __name__ == "__main__":
    unittest.main()
