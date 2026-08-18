import unittest

from models.Joint import (
    ADDR_TORQUE_ENABLE,
    Joint,
)
from tests.fake_servo import FakeServo


class JointTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.servo = FakeServo(position=1024)

        self.joint = Joint(
            servo_id=6,
            servo=self.servo,
            name="Joint 1",
            min_pos=0,
            max_pos=4095,
            speed=1000,
            acc=100,
        )

    def create_joint(self, **changes) -> Joint:
        configuration = {
            "servo_id": 6,
            "servo": self.servo,
            "name": "Joint 1",
            "min_pos": 0,
            "max_pos": 4095,
            "speed": 1000,
            "acc": 100,
        }

        configuration.update(changes)

        return Joint(**configuration)

    def test_normalizes_name(self) -> None:
        joint = self.create_joint(name="  Joint 1  ")

        self.assertEqual(joint.name, "Joint 1")

    def test_rejects_broadcast_id(self) -> None:
        with self.assertRaises(ValueError):
            self.create_joint(servo_id=254)

    def test_rejects_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            self.create_joint(name="   ")

    def test_rejects_none_servo(self) -> None:
        with self.assertRaises(ValueError):
            self.create_joint(servo=None)

    def test_rejects_inverted_position_limits(self) -> None:
        with self.assertRaises(ValueError):
            self.create_joint(
                min_pos=3000,
                max_pos=1000,
            )

    def test_rejects_invalid_default_speed(self) -> None:
        with self.assertRaises(ValueError):
            self.create_joint(speed=3401)

    def test_rejects_invalid_default_acceleration(self) -> None:
        with self.assertRaises(ValueError):
            self.create_joint(acc=255)

    def test_rejects_boolean_as_integer(self) -> None:
        with self.assertRaises(TypeError):
            self.create_joint(speed=True)

    def test_reads_current_position(self) -> None:
        position = self.joint.current_position()

        self.assertEqual(position, 1024)

    def test_enables_torque_without_initial_jump(self) -> None:
        self.joint.enable_torque()

        self.assertTrue(self.joint.is_torque_enabled())
        self.assertEqual(
            self.servo.registers[ADDR_TORQUE_ENABLE],
            1,
        )
        self.assertEqual(
            self.servo.position_commands,
            [(6, 1024, 1000, 100)],
        )

    def test_disables_torque(self) -> None:
        self.joint.enable_torque()
        self.joint.disable_torque()

        self.assertFalse(self.joint.is_torque_enabled())
        self.assertEqual(
            self.servo.registers[ADDR_TORQUE_ENABLE],
            0,
        )


if __name__ == "__main__":
    unittest.main()