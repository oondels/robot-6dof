import tempfile
import unittest
from pathlib import Path

from src.actions.recorded_actions import (
    list_named_actions,
    load_named_action,
    play_named_action,
    print_named_actions,
    sanitize_action_name,
    save_named_action,
)
from src.models.Joint import Joint
from src.models.joint_config import JointConfig
from src.models.RobotArm import RobotArm
from tests.fake_servo import FakeServo


class RecordedActionsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

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

        self.sample_raw_trajectory = [
            {
                "time": 0.0,
                "angles": {"base_yaw": 0.0, "gripper": 0.0},
            },
            {
                "time": 1.2,
                "angles": {"base_yaw": 15.0, "gripper": 10.0},
            },
        ]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_sanitize_action_name(self) -> None:
        self.assertEqual(sanitize_action_name("Pegar Copo!"), "pegar_copo")
        self.assertEqual(sanitize_action_name("acao-123_teste"), "acao-123_teste")
        with self.assertRaises(TypeError):
            sanitize_action_name(123)  # type: ignore
        with self.assertRaises(ValueError):
            sanitize_action_name("   !@#$   ")

    def test_save_and_load_named_action(self) -> None:
        saved_path = save_named_action(
            name="danca_robo",
            trajectory=self.sample_raw_trajectory,
            description="Coreografia de teste",
            base_dir=self.base_dir,
        )
        self.assertTrue(saved_path.exists())

        loaded = load_named_action("danca_robo", base_dir=self.base_dir)
        self.assertEqual(loaded["name"], "danca_robo")
        self.assertEqual(loaded["description"], "Coreografia de teste")
        self.assertTrue(loaded["is_smooth"])
        self.assertIn("trajectory", loaded)
        self.assertGreater(len(loaded["trajectory"]), len(self.sample_raw_trajectory))

    def test_list_and_print_named_actions(self) -> None:
        save_named_action("acao_a", self.sample_raw_trajectory, description="A", base_dir=self.base_dir)
        save_named_action("acao_b", self.sample_raw_trajectory, description="B", base_dir=self.base_dir)

        actions = list_named_actions(base_dir=self.base_dir)
        self.assertEqual(len(actions), 2)
        names = [a["name"] for a in actions]
        self.assertIn("acao_a", names)
        self.assertIn("acao_b", names)

        outputs: list[str] = []
        print_named_actions(output_fn=outputs.append, base_dir=self.base_dir)
        self.assertTrue(any("acao_a" in out for out in outputs))

    def test_play_named_action_executes_smoothly(self) -> None:
        save_named_action("pegar_objeto", self.sample_raw_trajectory, base_dir=self.base_dir)

        outputs: list[str] = []
        play_named_action(
            self.arm,
            "pegar_objeto",
            output_fn=outputs.append,
            base_dir=self.base_dir,
        )

        # Verifica que o robô passou pela posição Default (Home) primeiro
        self.assertTrue(any("Default (Home)" in out for out in outputs))
        self.assertTrue(any("concluída com sucesso" in out for out in outputs))


if __name__ == "__main__":
    unittest.main()
