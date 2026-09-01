import unittest

from src.utils.dualsense_color import (
    CONTROLLER_IDLE_COLOR,
    MOVEMENT_DISABLED_COLOR,
    MOVEMENT_ENABLED_COLOR,
    DualSenseColorConfig,
    color_for_controller_state,
)


class DualSenseColorConfigTestCase(unittest.TestCase):
    def test_accepts_valid_rgb_color(self) -> None:
        color = DualSenseColorConfig(red=10, green=20, blue=30)

        self.assertEqual((color.red, color.green, color.blue), (10, 20, 30))

    def test_rejects_non_integer_channel(self) -> None:
        with self.assertRaises(TypeError):
            DualSenseColorConfig(red=10.5, green=20, blue=30)

    def test_rejects_channel_outside_rgb_range(self) -> None:
        with self.assertRaises(ValueError):
            DualSenseColorConfig(red=256, green=20, blue=30)

    def test_selects_color_from_controller_state(self) -> None:
        self.assertEqual(
            color_for_controller_state(False, False),
            MOVEMENT_DISABLED_COLOR,
        )
        self.assertEqual(
            color_for_controller_state(True, False),
            MOVEMENT_ENABLED_COLOR,
        )
        self.assertEqual(
            color_for_controller_state(True, True),
            CONTROLLER_IDLE_COLOR,
        )


if __name__ == "__main__":
    unittest.main()
