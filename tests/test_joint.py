import unittest
from unittest.mock import patch

from models.Joint import ADDR_TORQUE_ENABLE, Joint, MovementStatus
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

    def test_command_uses_configuration_defaults(
        self,
    ) -> None:
        target_position = self.joint.command(45)

        self.assertEqual(target_position, 2560)

        self.assertEqual(
            self.servo.position_commands,
            [(6, 2560, 1000, 100)],
        )

    def test_command_accepts_overrides(self) -> None:
        self.joint.command(
            45,
            speed=500,
            acc=50,
        )

        self.assertEqual(
            self.servo.position_commands,
            [(6, 2560, 500, 50)],
        )

    def test_command_rejects_invalid_override(
        self,
    ) -> None:
        with self.assertRaises(ValueError):
            self.joint.command(
                45,
                speed=5000,
            )

        self.assertEqual(
            self.servo.position_commands,
            [],
        )

    def test_command_always_sends_valid_target(
        self,
    ) -> None:
        self.joint.command(0.5)

        self.assertEqual(
            self.servo.position_commands,
            [(6, 2054, 1000, 100)],
        )

    def test_reads_moving_state(self) -> None:
        self.servo.moving = 1

        self.assertTrue(self.joint.is_moving())

        self.servo.moving = 0

        self.assertFalse(self.joint.is_moving())

    def test_calculates_absolute_position_error(
        self,
    ) -> None:
        self.assertEqual(
            self.joint.position_error(
                target_position=2560,
                current_position=2550,
            ),
            10,
        )

        self.assertEqual(
            self.joint.position_error(
                target_position=2550,
                current_position=2560,
            ),
            10,
        )

    def test_accepts_position_at_tolerance_limit(
        self,
    ) -> None:
        self.assertTrue(
            self.joint.is_within_tolerance(
                target_position=2560,
                current_position=2549,
            )
        )

    def test_rejects_position_outside_tolerance(
        self,
    ) -> None:
        self.assertFalse(
            self.joint.is_within_tolerance(
                target_position=2560,
                current_position=2548,
            )
        )

    def test_position_error_rejects_non_integer(
        self,
    ) -> None:
        with self.assertRaises(TypeError):
            self.joint.position_error(
                target_position=2560.0,
                current_position=2550,
            )

    def test_reads_movement_status(self) -> None:
        self.servo.position = 2550
        self.servo.moving = 1

        status = self.joint.movement_status(target_position=2560)

        self.assertEqual(
            status,
            MovementStatus(
                target_position=2560,
                current_position=2550,
                position_error=10,
                moving=True,
                within_tolerance=True,
            ),
        )

    def test_movement_status_detects_stopped_outside_tolerance(
        self,
    ) -> None:
        self.servo.position = 2548
        self.servo.moving = 0

        status = self.joint.movement_status(target_position=2560)

        self.assertFalse(status.moving)
        self.assertFalse(status.within_tolerance)
        self.assertEqual(status.position_error, 12)

    @patch("models.Joint.sleep")
    def test_move_waits_until_target_is_reached(
        self,
        mocked_sleep,
    ) -> None:
        self.servo.queue_motion(
            positions=[2400, 2550],
            moving_states=[1, 0],
        )

        status = self.joint.move(
            angle=45,
            timeout=1.0,
            poll_interval=0.01,
        )

        self.assertTrue(status.within_tolerance)
        self.assertEqual(status.target_position, 2560)
        self.assertEqual(status.current_position, 2550)
        self.assertEqual(status.position_error, 10)

        self.assertEqual(
            self.servo.position_commands,
            [(6, 2560, 1000, 100)],
        )

        mocked_sleep.assert_called_once()

    def test_move_detects_servo_stopped_outside_target(
        self,
    ) -> None:
        self.servo.position = 2500
        self.servo.moving = 0

        with self.assertRaisesRegex(
            RuntimeError,
            "servo parou fora do alvo",
        ):
            self.joint.move(
                angle=45,
                timeout=1.0,
                poll_interval=0.01,
            )

    @patch("models.Joint.sleep")
    @patch(
        "models.Joint.monotonic",
        side_effect=[10.0, 11.0],
    )
    def test_move_raises_timeout(
        self,
        mocked_monotonic,
        mocked_sleep,
    ) -> None:
        self.servo.position = 2500
        self.servo.moving = 1

        with self.assertRaisesRegex(
            TimeoutError,
            "timeout",
        ):
            self.joint.move(
                angle=45,
                timeout=0.5,
                poll_interval=0.01,
            )

        mocked_sleep.assert_not_called()

    def test_move_keeps_torque_enabled_after_failure(
        self,
    ) -> None:
        self.joint.enable_torque()

        self.servo.position = 2500
        self.servo.moving = 0

        with self.assertRaises(RuntimeError):
            self.joint.move(
                angle=45,
                timeout=1.0,
                poll_interval=0.01,
            )

        self.assertTrue(self.joint.is_torque_enabled())

    def test_move_validates_wait_parameters_before_command(
        self,
    ) -> None:
        invalid_cases = [
            (
                {"timeout": 0},
                ValueError,
            ),
            (
                {"timeout": float("inf")},
                ValueError,
            ),
            (
                {"timeout": True},
                TypeError,
            ),
            (
                {"poll_interval": 0},
                ValueError,
            ),
            (
                {"poll_interval": float("nan")},
                ValueError,
            ),
            (
                {"poll_interval": False},
                TypeError,
            ),
        ]

        for arguments, expected_error in invalid_cases:
            with self.subTest(arguments=arguments):
                with self.assertRaises(expected_error):
                    self.joint.move(
                        angle=45,
                        **arguments,
                    )

        self.assertEqual(
            self.servo.position_commands,
            [],
        )

    def test_move_propagates_communication_error(
        self,
    ) -> None:
        self.servo.communication_result = -1

        with self.assertRaisesRegex(
            RuntimeError,
            "comando de movimento",
        ):
            self.joint.move(
                angle=45,
                timeout=1.0,
                poll_interval=0.01,
            )


if __name__ == "__main__":
    unittest.main()
