import unittest

from models.Joint import Joint
from models.joint_config import JointConfig
from models.RobotArm import RobotArm
from tests.fake_servo import FakeServo


class RobotArmTestCase(unittest.TestCase):
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
            name="shoulder_pitch",
            servo_id=2,
            zero_position=2048,
            direction=1,
            min_angle=-45.0,
            max_angle=90.0,
            speed=400,
            acc=30,
            tolerance_deg=1.0,
        )
        self.config3 = JointConfig(
            name="gripper",
            servo_id=3,
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
        self.joint3 = Joint(servo=self.servo, config=self.config3)

        self.arm = RobotArm([self.joint1, self.joint2, self.joint3])

    def test_creates_robot_arm_successfully(self) -> None:
        self.assertEqual(len(self.arm), 3)
        self.assertEqual(
            self.arm.joint_names,
            ("base_yaw", "shoulder_pitch", "gripper"),
        )
        self.assertEqual(
            self.arm.joints,
            (self.joint1, self.joint2, self.joint3),
        )

    def test_rejects_empty_joints_sequence(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "ao menos uma junta",
        ):
            RobotArm([])

    def test_rejects_non_joint_elements(self) -> None:
        with self.assertRaisesRegex(
            TypeError,
            "instâncias de Joint",
        ):
            RobotArm([self.joint1, "não é uma junta"])  # type: ignore

    def test_rejects_duplicate_joint_names(self) -> None:
        duplicate_config = JointConfig(
            name="BASE_YAW",  # Mesmo nome em maiúsculas
            servo_id=99,
            zero_position=2048,
            direction=1,
            min_angle=-90.0,
            max_angle=90.0,
        )
        duplicate_joint = Joint(servo=self.servo, config=duplicate_config)

        with self.assertRaisesRegex(
            ValueError,
            "Nome de junta duplicado",
        ):
            RobotArm([self.joint1, duplicate_joint])

    def test_rejects_duplicate_servo_ids(self) -> None:
        duplicate_id_config = JointConfig(
            name="outra_junta",
            servo_id=1,  # Mesmo ID 1 da joint1
            zero_position=2048,
            direction=1,
            min_angle=-90.0,
            max_angle=90.0,
        )
        duplicate_id_joint = Joint(servo=self.servo, config=duplicate_id_config)

        with self.assertRaisesRegex(
            ValueError,
            "ID de servo duplicado",
        ):
            RobotArm([self.joint1, duplicate_id_joint])

    def test_joint_lookup_by_name_and_item_access(self) -> None:
        self.assertIs(self.arm.joint("base_yaw"), self.joint1)
        self.assertIs(self.arm["BASE_YAW"], self.joint1)
        self.assertIs(self.arm["gripper"], self.joint3)

        with self.assertRaises(KeyError):
            self.arm.joint("inexistente")

        with self.assertRaises(TypeError):
            self.arm.joint(123)  # type: ignore

    def test_collective_torque_management(self) -> None:
        self.assertFalse(self.arm.is_torque_enabled())

        self.arm.enable_torque()
        self.assertTrue(self.arm.is_torque_enabled())

        self.arm.disable_torque()
        self.assertFalse(self.arm.is_torque_enabled())

    def test_current_angles_and_positions(self) -> None:
        angles = self.arm.current_angles()
        positions = self.arm.current_positions()

        self.assertEqual(
            angles,
            {
                "base_yaw": 0.0,
                "shoulder_pitch": 0.0,
                "gripper": 0.0,
            },
        )
        self.assertEqual(
            positions,
            {
                "base_yaw": 2048,
                "shoulder_pitch": 2048,
                "gripper": 2048,
            },
        )

    def test_validate_pose_success(self) -> None:
        valid_pose = {
            "base_yaw": 45.0,
            "shoulder_pitch": 30.0,
            "gripper": 50.0,
        }
        # Não deve lançar exceção
        self.arm.validate_pose(valid_pose)

    def test_validate_pose_rejects_non_dict(self) -> None:
        with self.assertRaises(TypeError):
            self.arm.validate_pose([45.0, 30.0, 50.0])  # type: ignore

    def test_validate_pose_rejects_missing_joints(self) -> None:
        incomplete_pose = {
            "base_yaw": 45.0,
            "shoulder_pitch": 30.0,
            # 'gripper' faltando
        }
        with self.assertRaisesRegex(
            ValueError,
            "Pose incompleta. Juntas ausentes: \\['gripper'\\]",
        ):
            self.arm.validate_pose(incomplete_pose)

    def test_validate_pose_rejects_unknown_joints(self) -> None:
        extra_pose = {
            "base_yaw": 45.0,
            "shoulder_pitch": 30.0,
            "gripper": 50.0,
            "camera_tilt": 10.0,  # Não existe
        }
        with self.assertRaisesRegex(
            ValueError,
            "Pose contém juntas desconhecidas: \\['camera_tilt'\\]",
        ):
            self.arm.validate_pose(extra_pose)

    def test_validate_pose_rejects_out_of_bounds_angles(self) -> None:
        invalid_angle_pose = {
            "base_yaw": 45.0,
            "shoulder_pitch": 30.0,
            "gripper": 150.0,  # Máximo é 100.0
        }
        with self.assertRaisesRegex(
            ValueError,
            "gripper: ângulo 150.0° fora do limite",
        ):
            self.arm.validate_pose(invalid_angle_pose)


if __name__ == "__main__":
    unittest.main()
