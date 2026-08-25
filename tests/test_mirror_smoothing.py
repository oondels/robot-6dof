import unittest
from unittest.mock import patch

from src.actions.mirror_action import (
    generate_smooth_trajectory,
    replay_smooth_trajectory,
    select_and_run_replay,
)
from src.application import Joint, JointConfig, RobotArm
from src.infrastructure.scservo_bus import ScServoBus
from tests.fake_servo import FakeServo


class MirrorSmoothingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.servo = FakeServo(position=2048)
        self.servo_bus = ScServoBus(self.servo)
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
            Joint(config=self.config1, servo_bus=self.servo_bus),
            Joint(config=self.config2, servo_bus=self.servo_bus),
        ]
        self.arm = RobotArm(self.servo_bus, self.joints)

        self.sample_raw_trajectory = [
            {
                "time": 0.0,
                "angles": {"base_yaw": 0.0, "gripper": 0.0},
            },
            {
                "time": 0.31,
                "angles": {"base_yaw": 10.0, "gripper": 5.0},
            },
            {
                "time": 2.50,  # Pausa humana longa de 2.19s para mover apenas mais 10 graus
                "angles": {"base_yaw": 20.0, "gripper": 10.0},
            },
        ]

    def test_generate_smooth_trajectory_empty(self) -> None:
        result = generate_smooth_trajectory([])
        self.assertEqual(result, [])

    def test_generate_smooth_trajectory_single_point(self) -> None:
        single = [{"time": 0.0, "angles": {"base_yaw": 10.0, "gripper": 5.0}}]
        result = generate_smooth_trajectory(single)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["angles"]["base_yaw"], 10.0)

    def test_generate_smooth_trajectory_resamples_and_interpolates(self) -> None:
        # Velocidade alvo: 20°/s. Deslocamento total = 20°.
        # Tempo total esperado = 20 / 20 = 1.0s (em vez dos 2.50s com a pausa humana).
        smooth = generate_smooth_trajectory(
            self.sample_raw_trajectory,
            target_speed_deg_s=20.0,
            sample_interval=0.05,
        )

        self.assertTrue(len(smooth) > len(self.sample_raw_trajectory))

        # Verifica monotonicidade estrita do tempo
        times = [p["time"] for p in smooth]
        for i in range(1, len(times)):
            self.assertGreaterEqual(times[i], times[i - 1])

        # Verifica que os pontos inicial e final coincidem com a trajetória original
        self.assertAlmostEqual(smooth[0]["angles"]["base_yaw"], 0.0, places=2)
        self.assertAlmostEqual(smooth[-1]["angles"]["base_yaw"], 20.0, places=2)

        # O tempo total deve ser próximo de 1.0s (eliminando a pausa de 2.5s)
        total_time = smooth[-1]["time"]
        self.assertAlmostEqual(total_time, 1.0, delta=0.15)

    def test_select_and_run_replay_mode_selection(self) -> None:
        outputs: list[str] = []
        inputs = ["2", "n"]  # Escolhe Modo 2, e recusa home para sair

        with patch(
            "src.actions.mirror_action.load_mirror_result",
            return_value=self.sample_raw_trajectory,
        ):
            select_and_run_replay(
                self.arm,
                input_fn=lambda _: inputs.pop(0),
                output_fn=outputs.append,
            )

        self.assertTrue(any("Modo 2" in out for out in outputs))


if __name__ == "__main__":
    unittest.main()
