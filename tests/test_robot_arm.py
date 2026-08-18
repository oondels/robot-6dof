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
            name="BASE_YAW",
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
            servo_id=1,
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
        self.arm.validate_pose(valid_pose)

    def test_validate_pose_rejects_non_dict(self) -> None:
        with self.assertRaises(TypeError):
            self.arm.validate_pose([45.0, 30.0, 50.0])  # type: ignore

    def test_validate_pose_rejects_missing_joints(self) -> None:
        incomplete_pose = {
            "base_yaw": 45.0,
            "shoulder_pitch": 30.0,
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
            "camera_tilt": 10.0,
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
            "gripper": 150.0,
        }
        with self.assertRaisesRegex(
            ValueError,
            "gripper: ângulo 150.0° fora do limite",
        ):
            self.arm.validate_pose(invalid_angle_pose)

    def test_command_pose_transmits_sync_packet_and_clears_buffer(self) -> None:
        pose = {
            "base_yaw": 45.0,
            "shoulder_pitch": 30.0,
            "gripper": 50.0,
        }

        targets = self.arm.command_pose(pose)

        self.assertEqual(
            targets,
            {
                "base_yaw": 2560,
                "shoulder_pitch": 2389,
                "gripper": 2617,
            },
        )
        self.assertEqual(len(self.servo.groupSyncWrite.tx_history), 1)
        self.assertEqual(len(self.servo.groupSyncWrite.data_dict), 0)
        self.assertEqual(
            set(self.servo.groupSyncWrite.tx_history[0].keys()),
            {1, 2, 3},
        )

    def test_command_pose_propagates_communication_error(self) -> None:
        self.servo.communication_result = -1
        pose = {
            "base_yaw": 0.0,
            "shoulder_pitch": 0.0,
            "gripper": 0.0,
        }

        with self.assertRaisesRegex(
            RuntimeError,
            "envio de pose sincronizada",
        ):
            self.arm.command_pose(pose)

        self.assertEqual(len(self.servo.groupSyncWrite.data_dict), 0)

    def test_move_pose_validates_wait_parameters(self) -> None:
        pose = {"base_yaw": 0.0, "shoulder_pitch": 0.0, "gripper": 0.0}

        for timeout in (-1.0, 0, float("inf"), float("nan"), "invalid"):
            with self.subTest(timeout=timeout):
                with self.assertRaises((ValueError, TypeError)):
                    self.arm.move_pose(pose, timeout=timeout)  # type: ignore

        for poll in (-1.0, 0, float("inf"), float("nan"), "invalid"):
            with self.subTest(poll_interval=poll):
                with self.assertRaises((ValueError, TypeError)):
                    self.arm.move_pose(pose, poll_interval=poll)  # type: ignore

    def test_move_pose_success(self) -> None:
        # Simula chegada síncrona ao alvo para todas as 3 juntas
        self.servo.queue_motion([2560], [0], servo_id=1)
        self.servo.queue_motion([2389], [0], servo_id=2)
        self.servo.queue_motion([2617], [0], servo_id=3)

        pose = {
            "base_yaw": 45.0,
            "shoulder_pitch": 30.0,
            "gripper": 50.0,
        }

        statuses = self.arm.move_pose(pose, timeout=1.0)

        self.assertEqual(len(statuses), 3)
        self.assertTrue(all(st.within_tolerance for st in statuses.values()))
        self.assertEqual(statuses["base_yaw"].current_position, 2560)
        self.assertEqual(statuses["shoulder_pitch"].current_position, 2389)
        self.assertEqual(statuses["gripper"].current_position, 2617)

    def test_move_pose_detects_joint_stopped_outside_tolerance(self) -> None:
        # Junta 1 e 3 chegam, mas junta 2 para no meio do caminho com moving=0
        self.servo.queue_motion([2560], [0], servo_id=1)
        self.servo.queue_motion([2100], [0], servo_id=2)  # Alvo era 2389
        self.servo.queue_motion([2617], [0], servo_id=3)

        pose = {
            "base_yaw": 45.0,
            "shoulder_pitch": 30.0,
            "gripper": 50.0,
        }

        with self.assertRaisesRegex(
            RuntimeError,
            "Pose falhou: junta 'shoulder_pitch' parou fora do alvo",
        ):
            self.arm.move_pose(pose, timeout=1.0)

    def test_move_pose_raises_timeout_with_diagnostics(self) -> None:
        # Junta 1 e 3 chegam, junta 2 continua moving=1 até estourar o prazo
        self.servo.queue_motion([2560], [0], servo_id=1)
        self.servo.queue_motion([2100, 2100, 2100], [1, 1, 1], servo_id=2)
        self.servo.queue_motion([2617], [0], servo_id=3)

        pose = {
            "base_yaw": 45.0,
            "shoulder_pitch": 30.0,
            "gripper": 50.0,
        }

        with self.assertRaisesRegex(
            TimeoutError,
            "Timeout após 0.050s aguardando pose.*shoulder_pitch",
        ):
            self.arm.move_pose(pose, timeout=0.05, poll_interval=0.01)


if __name__ == "__main__":
    unittest.main()
