import unittest

from models.Joint import (
    ADDR_TORQUE_ENABLE,
    Joint,
)
from models.joint_config import JointConfig
from tests.fake_servo import FakeServo


class JointTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.servo = FakeServo(position=2048)

        self.config = JointConfig(
            name="Joint 1",
            servo_id=6,
            zero_position=2048,
            direction=1,
            min_angle=-90,
            max_angle=90,
            speed=1000,
            acc=100,
            tolerance_deg=1.0,
        )

        self.joint = Joint(
            servo=self.servo,
            config=self.config,
        )

    def test_rejects_none_servo(self) -> None:
        with self.assertRaises(ValueError):
            Joint(
                servo=None,
                config=self.config,
            )

    def test_rejects_invalid_config(self) -> None:
        with self.assertRaises(TypeError):
            Joint(
                servo=self.servo,
                config=object(),
            )

    def test_exposes_configuration_properties(self) -> None:
        self.assertIs(
            self.joint.config,
            self.config,
        )
        self.assertEqual(self.joint.name, "Joint 1")
        self.assertEqual(self.joint.servo_id, 6)
        self.assertEqual(self.joint.speed, 1000)
        self.assertEqual(self.joint.acc, 100)

    def test_reads_current_position(self) -> None:
        position = self.joint.current_position()

        self.assertEqual(position, 2048)

    def test_reads_current_angle(self) -> None:
        angle = self.joint.current_angle()

        self.assertEqual(angle, 0.0)

    def test_delegates_angle_conversion(self) -> None:
        self.assertEqual(
            self.joint.angle_to_position(90),
            3072,
        )

        self.assertEqual(
            self.joint.position_to_angle(1024),
            -90.0,
        )

    def test_supports_inverted_joint(self) -> None:
        inverted_config = JointConfig(
            name="Inverted Joint",
            servo_id=7,
            zero_position=2048,
            direction=-1,
            min_angle=-90,
            max_angle=90,
        )

        joint = Joint(
            servo=self.servo,
            config=inverted_config,
        )

        self.assertEqual(
            joint.angle_to_position(90),
            1024,
        )

    def test_enables_torque_without_initial_jump(
        self,
    ) -> None:
        self.joint.enable_torque()

        self.assertTrue(self.joint.is_torque_enabled())

        self.assertEqual(
            self.servo.registers[ADDR_TORQUE_ENABLE],
            1,
        )

        self.assertEqual(
            self.servo.position_commands,
            [(6, 2048, 1000, 100)],
        )

    def test_disables_torque(self) -> None:
        self.joint.enable_torque()
        self.joint.disable_torque()

        self.assertFalse(self.joint.is_torque_enabled())

        self.assertEqual(
            self.servo.registers[ADDR_TORQUE_ENABLE],
            0,
        )

    def test_move_uses_configuration_defaults(
        self,
    ) -> None:
        self.joint.move(45)

        self.assertEqual(
            self.servo.position_commands,
            [(6, 2560, 1000, 100)],
        )

    def test_move_rejects_invalid_override(
        self,
    ) -> None:
        with self.assertRaises(ValueError):
            self.joint.move(
                45,
                speed=5000,
            )

        self.assertEqual(
            self.servo.position_commands,
            [],
        )

    def test_move_skips_target_inside_tolerance(
        self,
    ) -> None:
        self.joint.move(0.5)

        self.assertEqual(
            self.servo.position_commands,
            [],
        )

    def test_reads_moving_state(self) -> None:
        self.servo.moving = 1

        self.assertTrue(
            self.joint.is_moving()
        )

        self.servo.moving = 0

        self.assertFalse(
            self.joint.is_moving()
        )


if __name__ == "__main__":
    unittest.main()
