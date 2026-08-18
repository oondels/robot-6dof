import unittest

from tests.fake_servo import FakeServo


class FakeServoTestCase(unittest.TestCase):
    def test_replays_motion_sequence(self) -> None:
        servo = FakeServo(
            position=1000,
            moving=0,
        )

        servo.queue_motion(
            positions=[1100, 1200, 1300],
            moving_states=[1, 1, 0],
        )

        first_position, _, _, _ = servo.ReadPosSpeed(6)
        first_moving, _, _ = servo.ReadMoving(6)

        second_position, _, _, _ = servo.ReadPosSpeed(6)
        second_moving, _, _ = servo.ReadMoving(6)

        final_position, _, _, _ = servo.ReadPosSpeed(6)
        final_moving, _, _ = servo.ReadMoving(6)

        self.assertEqual(first_position, 1100)
        self.assertEqual(first_moving, 1)

        self.assertEqual(second_position, 1200)
        self.assertEqual(second_moving, 1)

        self.assertEqual(final_position, 1300)
        self.assertEqual(final_moving, 0)

    def test_keeps_last_state_after_sequence(
        self,
    ) -> None:
        servo = FakeServo()

        servo.queue_motion(
            positions=[2048],
            moving_states=[0],
        )

        servo.ReadPosSpeed(6)
        servo.ReadMoving(6)

        position, _, _, _ = servo.ReadPosSpeed(6)
        moving, _, _ = servo.ReadMoving(6)

        self.assertEqual(position, 2048)
        self.assertEqual(moving, 0)


if __name__ == "__main__":
    unittest.main()
