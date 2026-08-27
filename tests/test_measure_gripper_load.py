import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.application import JointConfig
from src.calibration import measure_gripper_load as meter_module
from src.calibration.measure_gripper_load import decode_load, run_meter


class FakeJoint:
    def __init__(self, angle: float = 0.0, loads: list[int] | None = None) -> None:
        self.config = JointConfig(
            name="gripper",
            servo_id=6,
            zero_position=2048,
            direction=1,
            min_angle=-1.0,
            max_angle=1.0,
        )
        self.angle = angle
        self.loads = iter(loads or [0])
        self.commands: list[tuple[float, int, int]] = []
        self.torque_enabled = False
        self.torque_disabled = False

    def enable_torque(self) -> None:
        self.torque_enabled = True

    def disable_torque(self) -> None:
        self.torque_disabled = True

    def current_angle(self) -> float:
        return self.angle

    def current_position(self) -> int:
        return self.config.angle_to_position(self.angle)

    def position_to_angle(self, position: int) -> float:
        return self.config.position_to_angle(position)

    def current_load(self) -> int:
        return next(self.loads)

    def command(self, angle: float, speed: int, acc: int) -> int:
        self.angle = angle
        self.commands.append((angle, speed, acc))
        return self.current_position()


class MeasureGripperLoadTestCase(unittest.TestCase):
    def test_decodes_positive_and_negative_load(self) -> None:
        self.assertEqual(decode_load(500), (500, "positiva", 50.0))
        self.assertEqual(decode_load((1 << 10) | 750), (750, "negativa", 75.0))
        self.assertEqual(decode_load(1000), (1000, "positiva", 100.0))

    def test_cancellation_does_not_enable_torque_or_create_csv(self) -> None:
        joint = FakeJoint()

        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "load.csv"
            run_meter(
                joint,
                csv_path=csv_path,
                label="cancelado",
                input_fn=lambda _: "não",
                output_fn=lambda _: None,
            )

            self.assertFalse(joint.torque_enabled)
            self.assertFalse(joint.torque_disabled)
            self.assertFalse(csv_path.exists())

    def test_steps_respect_limits_and_write_csv(self) -> None:
        joint = FakeJoint(loads=[100, (1 << 10) | 250, 300])
        commands = iter(("sim", "f", "f", "a", "a", "a", "q"))

        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "load.csv"
            run_meter(
                joint,
                csv_path=csv_path,
                label="objeto_macio",
                input_fn=lambda _: next(commands),
                output_fn=lambda _: None,
                clock=lambda: 10.0,
                sleep_fn=lambda _: None,
                sample_duration=0.05,
                sample_interval=0.05,
            )

            self.assertEqual(
                joint.commands,
                [
                    (-1.0, 200, 30),
                    (0.0, 200, 30),
                    (1.0, 200, 30),
                ],
            )
            self.assertTrue(joint.torque_enabled)
            self.assertTrue(joint.torque_disabled)

            with csv_path.open(newline="", encoding="utf-8") as csv_file:
                rows = list(csv.DictReader(csv_file))

            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["label"], "objeto_macio")
            self.assertEqual(rows[1]["load_magnitude"], "250")
            self.assertEqual(rows[1]["load_direction"], "negativa")

    def test_keyboard_interrupt_disables_torque(self) -> None:
        joint = FakeJoint()
        commands = iter(("sim",))

        def input_fn(_: str) -> str:
            try:
                return next(commands)
            except StopIteration as error:
                raise KeyboardInterrupt from error

        with tempfile.TemporaryDirectory() as directory:
            run_meter(
                joint,
                csv_path=Path(directory) / "load.csv",
                label="interrompido",
                input_fn=input_fn,
                output_fn=lambda _: None,
            )

        self.assertTrue(joint.torque_disabled)

    @patch.object(meter_module, "run_meter")
    @patch.object(meter_module, "Joint")
    @patch.object(meter_module, "ScServoBus")
    @patch.object(meter_module, "sms_sts")
    @patch.object(meter_module, "PortHandler")
    @patch.object(meter_module, "parse_args")
    def test_main_closes_serial_port(
        self,
        mocked_parse_args,
        mocked_port_handler,
        mocked_sms_sts,
        mocked_servo_bus,
        mocked_joint,
        mocked_run_meter,
    ) -> None:
        mocked_parse_args.return_value = Mock(
            port="/dev/test",
            baudrate=1_000_000,
            label="teste",
            csv=Path("/tmp/teste.csv"),
        )
        port = Mock()
        port.openPort.return_value = True
        port.setBaudRate.return_value = True
        port.ser = Mock()
        mocked_port_handler.return_value = port

        meter_module.main()

        mocked_run_meter.assert_called_once()
        self.assertTrue(port.ser.exclusive)
        port.closePort.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
