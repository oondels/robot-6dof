import unittest
from unittest.mock import Mock, patch

from calibration import test_joint_motion as motion_module
from calibration.test_joint_motion import find_joint_config, run_motion_test
from models.Joint import Joint
from models.joint_config import JointConfig
from tests.fake_servo import FakeServo


class TestJointMotionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.config = JointConfig(
            name="test_joint",
            servo_id=6,
            zero_position=2041,
            direction=1,
            min_angle=-1.0,
            max_angle=110.0,
            speed=400,
            acc=30,
            tolerance_deg=1.0,
        )

    def test_find_joint_config_by_name_and_id(self) -> None:
        with patch.object(motion_module, "JOINT_CONFIGS", (self.config,)):
            self.assertEqual(find_joint_config("test_joint"), self.config)
            self.assertEqual(find_joint_config("TEST_JOINT"), self.config)
            self.assertEqual(find_joint_config(6), self.config)
            self.assertEqual(find_joint_config("6"), self.config)

            with self.assertRaises(ValueError):
                find_joint_config("inexistente")

    def test_run_motion_test_cancels_if_operator_declines(self) -> None:
        servo = FakeServo(position=2041)
        joint = Joint(servo=servo, config=self.config)
        messages: list[str] = []

        run_motion_test(
            joint=joint,
            input_fn=lambda _: "n",
            output_fn=messages.append,
        )

        self.assertIn("Teste cancelado pelo operador antes de habilitar o torque.", messages)
        self.assertFalse(joint.is_torque_enabled())

    def test_run_motion_test_executes_moves_and_disables_torque(self) -> None:
        servo = FakeServo(position=2041)
        joint = Joint(servo=servo, config=self.config)

        # Simula resposta do servo para o movimento de 20.0 graus (2041 + 228 = 2269 counts)
        servo.queue_motion(
            positions=[2041, 2269],
            moving_states=[1, 0],
        )

        inputs = iter(["s", "20.0", "q", "s"])
        messages: list[str] = []

        run_motion_test(
            joint=joint,
            input_fn=lambda _: next(inputs),
            output_fn=messages.append,
        )

        self.assertTrue(any("Chegada confirmada!" in msg for msg in messages))
        self.assertFalse(joint.is_torque_enabled())


if __name__ == "__main__":
    unittest.main()
