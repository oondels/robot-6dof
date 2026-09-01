import unittest
from unittest.mock import Mock

from src.application.joint import Joint
from src.application.joint_config import JointConfig


class JointStatusTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.servo_bus = Mock()
        self.servo_bus.read_position.return_value = 2048
        self.servo_bus.read_load.return_value = 472
        self.servo_bus.read_voltage.return_value = 9.0
        self.servo_bus.read_current.return_value = 0.53
        self.servo_bus.read_temperature.return_value = 33.0
        self.config = JointConfig(
            name="gripper",
            servo_id=6,
            zero_position=2048,
            direction=1,
            min_angle=-30.0,
            max_angle=30.0,
        )

    def test_constructor_does_not_read_hardware(self) -> None:
        joint = Joint(self.config, self.servo_bus)

        self.assertIsNone(joint.status)
        self.servo_bus.read_position.assert_not_called()

    def test_get_status_collects_and_stores_the_latest_status(self) -> None:
        joint = Joint(self.config, self.servo_bus)

        collected_status = joint.get_status()

        self.assertIs(collected_status, joint.status)
        self.assertEqual(collected_status.position, 2048)
        self.assertEqual(collected_status.load, 472)
        self.assertEqual(collected_status.load_direction, "positiva")
        self.assertEqual(collected_status.voltage, 9.0)
        self.assertEqual(collected_status.current, 0.53)
        self.assertEqual(collected_status.temperature, 33.0)

    def test_status_property_does_not_read_hardware_again(self) -> None:
        joint = Joint(self.config, self.servo_bus)
        joint.get_status()
        self.servo_bus.reset_mock()

        latest_status = joint.status

        self.assertIsNotNone(latest_status)
        self.servo_bus.read_position.assert_not_called()
        self.servo_bus.read_load.assert_not_called()

    def test_get_status_separates_load_magnitude_and_direction(self) -> None:
        self.servo_bus.read_load.return_value = (1 << 10) | 200
        joint = Joint(self.config, self.servo_bus)

        collected_status = joint.get_status()

        self.assertEqual(collected_status.load, 200)
        self.assertEqual(collected_status.load_direction, "negativa")

    def test_load_is_safe_when_no_limit_is_configured(self) -> None:
        joint = Joint(self.config, self.servo_bus)

        self.assertTrue(joint.is_load_safe)
        self.servo_bus.read_load.assert_not_called()

    def test_load_safety_uses_magnitude_and_configured_limit(self) -> None:
        config = JointConfig(
            name="base_yaw",
            servo_id=1,
            zero_position=2048,
            direction=1,
            min_angle=-30.0,
            max_angle=30.0,
            maximum_safe_load=300,
        )
        joint = Joint(config, self.servo_bus)

        self.servo_bus.read_load.return_value = (1 << 10) | 300
        self.assertTrue(joint.is_load_safe)

        self.servo_bus.read_load.return_value = (1 << 10) | 301
        self.assertFalse(joint.is_load_safe)


if __name__ == "__main__":
    unittest.main()
