import unittest
from collections.abc import Sequence

from src.application.model.Joint import Joint
from src.application.model.JointConfig import JointConfig
from src.application.model.RobotArm import RobotArm
from src.application.model.ServoBus import ServoPositionCommand
from src.infrastructure.scservo_bus import ADDR_TORQUE_ENABLE, ScServoBus
from tests.fake_servo import FakeServo


class FakeServoBus:
    """Test double que implementa apenas a porta exigida pelo núcleo."""

    def __init__(self) -> None:
        self.positions: dict[int, int] = {}
        self.moving: dict[int, bool] = {}
        self.torque_enabled: set[int] = set()
        self.position_commands: list[tuple[int, int, int, int]] = []
        self.sync_commands: list[tuple[ServoPositionCommand, ...]] = []
        self.events: list[tuple[str, int]] = []

    def read_position(self, servo_id: int) -> int:
        self.events.append(("read_position", servo_id))
        return self.positions.get(servo_id, 0)

    def is_moving(self, servo_id: int) -> bool:
        return self.moving.get(servo_id, False)

    def command_position(
        self,
        servo_id: int,
        position: int,
        speed: int,
        acceleration: int,
    ) -> None:
        self.events.append(("command_position", servo_id))
        self.position_commands.append(
            (servo_id, position, speed, acceleration)
        )

    def is_torque_enabled(self, servo_id: int) -> bool:
        self.events.append(("is_torque_enabled", servo_id))
        return servo_id in self.torque_enabled

    def enable_torque(self, servo_id: int) -> None:
        self.events.append(("enable_torque", servo_id))
        self.torque_enabled.add(servo_id)

    def disable_torque(self, servo_id: int) -> None:
        self.events.append(("disable_torque", servo_id))
        self.torque_enabled.discard(servo_id)

    def command_positions_sync(
        self,
        commands: Sequence[ServoPositionCommand],
    ) -> None:
        self.sync_commands.append(tuple(commands))


class ApplicationArchitectureTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = FakeServoBus()
        self.bus.positions[6] = 2048
        self.config = JointConfig(
            name="Joint 1",
            servo_id=6,
            zero_position=2048,
            direction=1,
            min_angle=-90,
            max_angle=90,
            speed=1000,
            acc=100,
            tolerance_deg=1.0,
        )
        self.joint = Joint(self.config, self.bus)

    def test_joint_uses_port_to_read_and_command_position(self) -> None:
        self.assertEqual(self.joint.current_position(), 2048)

        target = self.joint.command(45)

        self.assertEqual(target, 2560)
        self.assertEqual(
            self.bus.position_commands,
            [(6, 2560, 1000, 100)],
        )

    def test_enable_torque_prepares_current_position_first(self) -> None:
        self.joint.enable_torque()

        self.assertEqual(
            self.bus.events,
            [
                ("read_position", 6),
                ("command_position", 6),
                ("enable_torque", 6),
                ("is_torque_enabled", 6),
            ],
        )
        self.assertEqual(
            self.bus.position_commands,
            [(6, 2048, 1000, 100)],
        )

    def test_move_validates_wait_parameters_before_commanding(self) -> None:
        invalid_values = (0, -1, float("inf"), float("nan"), True)

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    self.joint.move(45, timeout=value)  # type: ignore[arg-type]

        self.assertEqual(self.bus.position_commands, [])

    def test_move_rejects_servo_stopped_outside_target(self) -> None:
        self.bus.positions[6] = 2400
        self.bus.moving[6] = False

        with self.assertRaisesRegex(RuntimeError, "parou fora do alvo"):
            self.joint.move(45, timeout=0.1, poll_interval=0.01)

    def test_move_raises_timeout_while_servo_is_moving(self) -> None:
        self.bus.positions[6] = 2400
        self.bus.moving[6] = True

        with self.assertRaisesRegex(TimeoutError, "timeout"):
            self.joint.move(45, timeout=0.001, poll_interval=0.0001)

    def test_robot_arm_sends_pose_through_sync_port(self) -> None:
        second_config = JointConfig(
            name="Gripper",
            servo_id=7,
            zero_position=2048,
            direction=-1,
            min_angle=-45,
            max_angle=45,
        )
        second_joint = Joint(second_config, self.bus)
        arm = RobotArm(self.bus, [self.joint, second_joint])

        targets = arm.command_pose(
            {
                " joint 1 ": 45,
                "GRIPPER": 10,
            }
        )

        self.assertEqual(
            targets,
            {
                "Joint 1": 2560,
                "Gripper": 1934,
            },
        )
        self.assertEqual(len(self.bus.sync_commands), 1)
        self.assertEqual(
            self.bus.sync_commands[0],
            (
                ServoPositionCommand(6, 2560, 1000, 100),
                ServoPositionCommand(7, 1934, 1000, 100),
            ),
        )


class ScServoBusAdapterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.sdk_servo = FakeServo(position=2048)
        self.bus = ScServoBus(self.sdk_servo)

    def test_translates_position_operations_to_sdk(self) -> None:
        self.assertEqual(self.bus.read_position(6), 2048)

        self.bus.command_position(6, 2560, 1000, 100)

        self.assertEqual(
            self.sdk_servo.position_commands,
            [(6, 2560, 1000, 100)],
        )

    def test_translates_torque_operations_to_register(self) -> None:
        self.bus.enable_torque(6)
        self.assertTrue(self.bus.is_torque_enabled(6))
        self.assertEqual(self.sdk_servo.registers[ADDR_TORQUE_ENABLE], 1)

        self.bus.disable_torque(6)
        self.assertFalse(self.bus.is_torque_enabled(6))
        self.assertEqual(self.sdk_servo.registers[ADDR_TORQUE_ENABLE], 0)

    def test_translates_synchronized_commands_to_sdk(self) -> None:
        commands = [
            ServoPositionCommand(6, 2560, 1000, 100),
            ServoPositionCommand(7, 1934, 900, 90),
        ]

        self.bus.command_positions_sync(commands)

        self.assertEqual(
            self.sdk_servo.sync_write_commands,
            [
                (6, 2560, 1000, 100),
                (7, 1934, 900, 90),
            ],
        )
        self.assertEqual(len(self.sdk_servo.groupSyncWrite.tx_history), 1)


if __name__ == "__main__":
    unittest.main()
