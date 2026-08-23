import unittest
from unittest.mock import Mock, patch

from src.calibration import test_arm_poses as pose_module
from src.calibration.test_arm_poses import run_pose_tester
from src.models.Joint import Joint
from src.models.joint_config import JointConfig
from src.models.RobotArm import RobotArm
from tests.fake_servo import FakeServo


class TestArmPosesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.servo = FakeServo(position=2048)
        self.config1 = JointConfig(
            name="base_yaw",
            servo_id=1,
            zero_position=2048,
            direction=1,
            min_angle=-90.0,
            max_angle=90.0,
            speed=400,
            acc=30,
            tolerance_deg=1.0,
        )
        self.config2 = JointConfig(
            name="gripper",
            servo_id=2,
            zero_position=2048,
            direction=1,
            min_angle=0.0,
            max_angle=100.0,
            speed=400,
            acc=30,
            tolerance_deg=1.0,
        )
        self.joint1 = Joint(servo=self.servo, config=self.config1)
        self.joint2 = Joint(servo=self.servo, config=self.config2)
        self.arm = RobotArm([self.joint1, self.joint2])

    def test_run_pose_tester_cancels_if_declined(self) -> None:
        messages: list[str] = []
        run_pose_tester(
            arm=self.arm,
            input_fn=lambda _: "n",
            output_fn=messages.append,
        )
        self.assertIn("Teste cancelado pelo operador antes de habilitar torque.", messages)
        self.assertFalse(self.arm.is_torque_enabled())

    def test_run_pose_tester_runs_and_exits(self) -> None:
        inputs = iter(["s", "q", "s"])
        messages: list[str] = []
        run_pose_tester(
            arm=self.arm,
            input_fn=lambda _: next(inputs),
            output_fn=messages.append,
        )
        self.assertFalse(self.arm.is_torque_enabled())


if __name__ == "__main__":
    unittest.main()
