import unittest
from unittest.mock import Mock

from src.application.joint import Joint
from src.application.joint_config import JointConfig
from src.application.robot_arm import RobotArm


class RobotStatusTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.servo_bus = Mock()
        self.servo_bus.read_position.side_effect = lambda servo_id: {
            1: 2048,
            6: 2200,
        }[servo_id]
        self.servo_bus.read_load.side_effect = lambda servo_id: {
            1: 40,
            6: 472,
        }[servo_id]
        self.servo_bus.read_voltage.return_value = 9.0
        self.servo_bus.read_current.return_value = 0.10
        self.servo_bus.read_temperature.return_value = 33.0

        base = Joint(
            JointConfig(
                name="base_yaw",
                servo_id=1,
                zero_position=2048,
                direction=1,
                min_angle=-90.0,
                max_angle=90.0,
            ),
            self.servo_bus,
        )
        gripper = Joint(
            JointConfig(
                name="gripper",
                servo_id=6,
                zero_position=2048,
                direction=1,
                min_angle=-30.0,
                max_angle=30.0,
            ),
            self.servo_bus,
        )
        self.arm = RobotArm(self.servo_bus, [base, gripper])

    def test_get_status_collects_all_joints_in_one_package(self) -> None:
        robot_status = self.arm.get_status()

        self.assertIs(robot_status, self.arm.status)
        self.assertEqual(set(robot_status.joints), {"base_yaw", "gripper"})
        self.assertEqual(robot_status.joints["base_yaw"].position, 2048)
        self.assertEqual(robot_status.joints["base_yaw"].load, 40)
        self.assertEqual(robot_status.joints["gripper"].position, 2200)
        self.assertEqual(robot_status.joints["gripper"].load, 472)
        self.assertEqual(
            robot_status.joints["gripper"].load_direction,
            "positiva",
        )

    def test_status_property_does_not_collect_again(self) -> None:
        self.arm.get_status()
        self.servo_bus.reset_mock()

        latest_status = self.arm.status

        self.assertIsNotNone(latest_status)
        self.servo_bus.read_position.assert_not_called()
        self.servo_bus.read_load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
