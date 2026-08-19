import unittest

from actions.router import execute_action
import main
from models.joint_config import JointConfig
from models.Joint import Joint
from models.RobotArm import RobotArm
from tests.fake_servo import FakeServo


class ActionsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.servo = FakeServo(position=2048)
        self.config1 = JointConfig(
            name="base_yaw",
            servo_id=1,
            zero_position=2048,
            direction=1,
            min_angle=-90.0,
            max_angle=90.0,
        )
        self.config2 = JointConfig(
            name="gripper",
            servo_id=6,
            zero_position=2048,
            direction=1,
            min_angle=-45.0,
            max_angle=45.0,
        )
        self.joints = [
            Joint(servo=self.servo, config=self.config1),
            Joint(servo=self.servo, config=self.config2),
        ]
        self.arm = RobotArm(self.joints)

    def test_execute_action_rejects_non_string(self) -> None:
        with self.assertRaises(TypeError):
            execute_action(123, self.arm)  # type: ignore

    def test_execute_action_rejects_unknown_action(self) -> None:
        with self.assertRaises(ValueError):
            execute_action("invalid_action", self.arm)

    def test_execute_action_test(self) -> None:
        # Testa chamada da action "test", que executa run_pose_tester
        inputs = ["n"]  # Recusa ligar torque para sair imediatamente
        outputs: list[str] = []

        execute_action(
            "test",
            self.arm,
            input_fn=lambda _: inputs.pop(0),
            output_fn=outputs.append,
        )

        self.assertTrue(any("Teste de Poses Sincronizadas" in out for out in outputs))

    def test_execute_action_mirror(self) -> None:
        outputs: list[str] = []
        execute_action(
            "mirror",
            self.arm,
            output_fn=outputs.append,
        )
        self.assertTrue(any("mirror" in out.lower() for out in outputs))

    def test_main_parse_args_defaults(self) -> None:
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["main.py"]
            args = main.parse_args()
            self.assertEqual(args.action, "status")
            self.assertEqual(args.port, main.DEFAULT_PORT)
            self.assertEqual(args.baudrate, main.DEFAULT_BAUDRATE)
        finally:
            sys.argv = old_argv

    def test_main_create_arm(self) -> None:
        arm = main.create_arm(self.servo)
        self.assertIsInstance(arm, RobotArm)
        self.assertEqual(len(arm), len(main.JOINT_CONFIGS))

    def test_main_print_arm_status(self) -> None:
        # Garante que print_arm_status roda sem exceção
        main.print_arm_status(self.arm)


if __name__ == "__main__":
    unittest.main()
