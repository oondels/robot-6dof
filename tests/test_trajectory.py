import unittest

from src.utils.trajectory import (
    calculate_joint_distance,
    calculate_trajectory_duration,
    filter_noise_waypoints,
    generate_smooth_trajectory,
)


class TrajectoryUtilsTestCase(unittest.TestCase):
    def test_calculate_joint_distance(self) -> None:
        pose_a = {"base_yaw": 10.0, "gripper": 5.0}
        pose_b = {"base_yaw": 25.0, "gripper": 10.0}
        # Delta max = max(15.0, 5.0) = 15.0
        self.assertEqual(calculate_joint_distance(pose_a, pose_b), 15.0)

    def test_filter_noise_waypoints(self) -> None:
        traj = [
            {"time": 0.0, "angles": {"base_yaw": 0.0}},
            {"time": 0.1, "angles": {"base_yaw": 0.05}},  # Ruído < 0.2°
            {"time": 0.2, "angles": {"base_yaw": 5.0}},
        ]
        filtered = filter_noise_waypoints(traj, min_delta_deg=0.2)
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["angles"]["base_yaw"], 0.0)
        self.assertEqual(filtered[1]["angles"]["base_yaw"], 5.0)

    def test_generate_smooth_trajectory_empty_and_single(self) -> None:
        self.assertEqual(generate_smooth_trajectory([]), [])
        single = [{"time": 0.0, "angles": {"base_yaw": 10.0}}]
        result = generate_smooth_trajectory(single)
        self.assertEqual(len(result), 1)

    def test_generate_smooth_trajectory_interpolation_density(self) -> None:
        raw = [
            {"time": 0.0, "angles": {"base_yaw": 0.0, "gripper": 0.0}},
            {"time": 3.0, "angles": {"base_yaw": 30.0, "gripper": 15.0}},
        ]
        # Velocidade: 30°/s -> 30° / 30°/s = 1.0s total.
        smooth = generate_smooth_trajectory(
            raw,
            target_speed_deg_s=30.0,
            sample_interval=0.04,
        )
        self.assertGreater(len(smooth), 10)
        self.assertAlmostEqual(smooth[0]["angles"]["base_yaw"], 0.0, places=2)
        self.assertAlmostEqual(smooth[-1]["angles"]["base_yaw"], 30.0, places=2)
        self.assertAlmostEqual(smooth[-1]["time"], 1.0, delta=0.08)

    def test_calculate_trajectory_duration(self) -> None:
        traj = [{"time": 0.0}, {"time": 1.5}, {"time": 3.42}]
        self.assertEqual(calculate_trajectory_duration(traj), 3.42)
        self.assertEqual(calculate_trajectory_duration([]), 0.0)


if __name__ == "__main__":
    unittest.main()
