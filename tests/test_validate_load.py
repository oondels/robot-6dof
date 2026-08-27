import unittest

from src.utils.validate_load import validate_load


class ValidateLoadTestCase(unittest.TestCase):
    def test_does_not_report_contact_during_fast_free_movement(self) -> None:
        contact_detected = validate_load(
            raw_load=248,
            measured_velocity_deg_s=-49.3,
            angle_error_deg=12.14,
            current_a=0.026,
        )

        self.assertFalse(contact_detected)

    def test_reports_contact_when_servo_is_blocked_and_applying_effort(self) -> None:
        contact_detected = validate_load(
            raw_load=472,
            measured_velocity_deg_s=-0.2,
            angle_error_deg=10.1,
            current_a=0.53,
        )

        self.assertTrue(contact_detected)

    def test_ignores_the_load_direction_bit(self) -> None:
        raw_load_with_negative_direction = (1 << 10) | 472

        contact_detected = validate_load(
            raw_load=raw_load_with_negative_direction,
            measured_velocity_deg_s=0.0,
            angle_error_deg=10.0,
            current_a=0.50,
        )

        self.assertTrue(contact_detected)

    def test_does_not_report_contact_without_position_error(self) -> None:
        contact_detected = validate_load(
            raw_load=472,
            measured_velocity_deg_s=0.0,
            angle_error_deg=1.0,
            current_a=0.50,
        )

        self.assertFalse(contact_detected)

    def test_does_not_report_contact_without_electrical_effort(self) -> None:
        contact_detected = validate_load(
            raw_load=472,
            measured_velocity_deg_s=0.0,
            angle_error_deg=10.0,
            current_a=0.02,
        )

        self.assertFalse(contact_detected)


if __name__ == "__main__":
    unittest.main()
