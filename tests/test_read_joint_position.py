import unittest
from argparse import Namespace
from unittest.mock import Mock, patch

from calibration import read_joint_position as reader_module
from calibration.read_joint_position import (
    read_position,
    run_reader,
    validate_servo_id,
)
from tests.fake_servo import FakeServo


class ReadJointPositionTestCase(unittest.TestCase):
    def test_reads_raw_position_without_writes(self) -> None:
        servo = FakeServo(position=2310)

        position = read_position(servo, servo_id=6)

        self.assertEqual(position, 2310)
        self.assertEqual(servo.position_commands, [])
        self.assertEqual(servo.registers, {})

    def test_rejects_invalid_servo_id_before_reading(self) -> None:
        servo = FakeServo(position=2310)

        for servo_id, expected_error in (
            (True, TypeError),
            (-1, ValueError),
            (254, ValueError),
        ):
            with self.subTest(servo_id=servo_id):
                with self.assertRaises(expected_error):
                    read_position(servo, servo_id)

        self.assertEqual(servo.position_sequence, [])

    def test_propagates_communication_error(self) -> None:
        servo = FakeServo(position=2310)
        servo.communication_result = -1

        with self.assertRaisesRegex(
            RuntimeError,
            "leitura para calibração",
        ):
            read_position(servo, servo_id=6)

    def test_interactive_reader_only_reads_on_enter(self) -> None:
        servo = FakeServo()
        servo.queue_motion(
            positions=[2200, 2300],
            moving_states=[],
        )
        commands = iter(["inválido", "", "", "q"])
        messages: list[str] = []

        run_reader(
            servo=servo,
            servo_id=6,
            input_fn=lambda _: next(commands),
            output_fn=messages.append,
        )

        self.assertIn("Comando inválido. Use apenas Enter ou q.", messages)
        self.assertIn("servo 6: posição=2200 counts", messages)
        self.assertIn("servo 6: posição=2300 counts", messages)
        self.assertEqual(servo.position_commands, [])
        self.assertEqual(servo.registers, {})

    def test_validate_servo_id_accepts_individual_id(self) -> None:
        validate_servo_id(6)

    @patch.object(reader_module, "run_reader")
    @patch.object(reader_module, "sms_sts")
    @patch.object(reader_module, "PortHandler")
    @patch.object(reader_module, "parse_args")
    def test_main_closes_port_after_reader_failure(
        self,
        mocked_parse_args,
        mocked_port_handler,
        mocked_sms_sts,
        mocked_run_reader,
    ) -> None:
        mocked_parse_args.return_value = Namespace(
            port="/dev/test",
            baudrate=1_000_000,
            servo_id=6,
        )

        port = Mock()
        port.openPort.return_value = True
        port.setBaudRate.return_value = True
        mocked_port_handler.return_value = port

        servo = object()
        mocked_sms_sts.return_value = servo
        mocked_run_reader.side_effect = RuntimeError("falha simulada")

        with self.assertRaisesRegex(RuntimeError, "falha simulada"):
            reader_module.main()

        mocked_run_reader.assert_called_once_with(servo, 6)
        port.closePort.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
