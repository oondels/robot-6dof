import unittest
from dataclasses import FrozenInstanceError

from models.joint_config import JointConfig


class JointConfigTestCase(unittest.TestCase):
    def create_config(self, **changes) -> JointConfig:
        configuration = {
            "name": "Joint 1",
            "servo_id": 6,
            "zero_position": 2048,
            "direction": 1,
            "min_angle": -90,
            "max_angle": 90,
            "speed": 1000,
            "acc": 100,
            "tolerance_deg": 1.0,
        }

        configuration.update(changes)

        return JointConfig(**configuration)

    def test_accepts_valid_configuration(self) -> None:
        config = self.create_config()

        self.assertEqual(config.zero_position, 2048)
        self.assertEqual(config.direction, 1)
        self.assertEqual(config.min_angle, -90.0)
        self.assertEqual(config.max_angle, 90.0)

    def test_normalizes_name(self) -> None:
        config = self.create_config(name="  Shoulder  ")

        self.assertEqual(config.name, "Shoulder")

    def test_is_immutable(self) -> None:
        config = self.create_config()

        with self.assertRaises(FrozenInstanceError):
            config.zero_position = 1000

    def test_accepts_inverted_direction(self) -> None:
        config = self.create_config(direction=-1)

        self.assertEqual(config.direction, -1)

    def test_rejects_invalid_direction(self) -> None:
        with self.assertRaises(ValueError):
            self.create_config(direction=0)

    def test_rejects_broadcast_id(self) -> None:
        with self.assertRaises(ValueError):
            self.create_config(servo_id=254)

    def test_rejects_zero_outside_encoder(self) -> None:
        with self.assertRaises(ValueError):
            self.create_config(zero_position=4096)

    def test_rejects_limits_without_zero_angle(self) -> None:
        with self.assertRaises(ValueError):
            self.create_config(
                min_angle=10,
                max_angle=90,
            )

    def test_rejects_non_finite_angle(self) -> None:
        with self.assertRaises(ValueError):
            self.create_config(max_angle=float("nan"))

    def test_rejects_non_positive_tolerance(self) -> None:
        with self.assertRaises(ValueError):
            self.create_config(tolerance_deg=0)

    def test_rejects_limit_outside_encoder(self) -> None:
        with self.assertRaises(ValueError):
            self.create_config(
                zero_position=100,
                min_angle=-90,
                max_angle=90,
            )


    def test_converts_angle_to_position(self) -> None:
        config = self.create_config()

        self.assertEqual(
            config.angle_to_position(-90),
            1024,
        )
        self.assertEqual(
            config.angle_to_position(0),
            2048,
        )
        self.assertEqual(
            config.angle_to_position(90),
            3072,
        )


    def test_converts_angle_with_inverted_direction(self) -> None:
        config = self.create_config(direction=-1)

        self.assertEqual(
            config.angle_to_position(-90),
            3072,
        )
        self.assertEqual(
            config.angle_to_position(90),
            1024,
        )


    def test_converts_position_to_angle(self) -> None:
        config = self.create_config()

        self.assertEqual(
            config.position_to_angle(1024),
            -90.0,
        )
        self.assertEqual(
            config.position_to_angle(2048),
            0.0,
        )
        self.assertEqual(
            config.position_to_angle(3072),
            90.0,
        )


    def test_angle_round_trip_respects_encoder_resolution(
        self,
    ) -> None:
        config = self.create_config()
        requested_angle = 35.5

        position = config.angle_to_position(requested_angle)
        measured_angle = config.position_to_angle(position)

        half_count_in_degrees = 360.0 / 4096 / 2

        self.assertAlmostEqual(
            measured_angle,
            requested_angle,
            delta=half_count_in_degrees,
        )


    def test_rejects_angle_outside_joint_limits(self) -> None:
        config = self.create_config()

        with self.assertRaises(ValueError):
            config.angle_to_position(91)


    def test_rejects_position_outside_calibration(self) -> None:
        config = self.create_config()

        with self.assertRaises(ValueError):
            config.position_to_angle(1000)
            
    def test_rejects_invalid_speed(self) -> None:
        with self.assertRaises(ValueError):
            self.create_config(speed=3401)

    def test_rejects_invalid_acceleration(self) -> None:
        with self.assertRaises(ValueError):
            self.create_config(acc=255)

    def test_rejects_boolean_speed(self) -> None:
        with self.assertRaises(TypeError):
            self.create_config(speed=True)

    def test_validates_command_speed(self) -> None:
        JointConfig.validate_speed(1500)

        with self.assertRaises(ValueError):
            JointConfig.validate_speed(5000)

    def test_validates_command_acceleration(self) -> None:
        JointConfig.validate_acceleration(100)

        with self.assertRaises(ValueError):
            JointConfig.validate_acceleration(300)


if __name__ == "__main__":
    unittest.main()
