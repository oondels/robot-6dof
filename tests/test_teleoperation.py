from collections import deque
import unittest
from unittest.mock import patch

from src.application.joint import Joint
from src.application.joint_config import JointConfig
from src.application.ports.control_input import ControlInput, ControlState
from src.application.robot_arm import RobotArm
from src.application.teleoperation import TeleOperation
from src.infrastructure.scservo_bus import ScServoBus
from tests.fake_servo import FakeServo


class FakeControlInput(ControlInput):
    def __init__(self, states: list[ControlState] | None = None) -> None:
        self.states = deque(states or [])
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def read(self) -> ControlState:
        if self.states:
            return self.states.popleft()
        return ControlState()

    def is_available(self) -> bool:
        return self.opened and not self.closed

    def reset(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class TeleOperationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_servo = FakeServo(position=2048)
        self.servo_bus = ScServoBus(self.fake_servo)

        self.configs = [
            JointConfig(
                name="base_yaw",
                servo_id=1,
                zero_position=2048,
                direction=1,
                min_angle=-90.0,
                max_angle=90.0,
            ),
            JointConfig(
                name="shoulder_pitch",
                servo_id=2,
                zero_position=2048,
                direction=1,
                min_angle=0.0,
                max_angle=90.0,
            ),
            JointConfig(
                name="elbow_pitch",
                servo_id=3,
                zero_position=2048,
                direction=1,
                min_angle=0.0,
                max_angle=90.0,
            ),
            JointConfig(
                name="wrist_pitch",
                servo_id=4,
                zero_position=2048,
                direction=1,
                min_angle=-45.0,
                max_angle=45.0,
            ),
            JointConfig(
                name="wrist_roll",
                servo_id=5,
                zero_position=2048,
                direction=1,
                min_angle=-90.0,
                max_angle=90.0,
            ),
            JointConfig(
                name="gripper",
                servo_id=6,
                zero_position=2048,
                direction=1,
                min_angle=-10.0,
                max_angle=50.0,
            ),
        ]
        self.joints = [
            Joint(config=config, servo_bus=self.servo_bus)
            for config in self.configs
        ]
        self.arm = RobotArm(self.servo_bus, self.joints)
        self.input_device = FakeControlInput()
        self.output_logs: list[str] = []
        self.teleop = TeleOperation(
            input_control_device=self.input_device,
            robot_arm=self.arm,
            jog_speed=60.0,
            enable_metrics=False,
            output_fn=self.output_logs.append,
        )

    def test_initialization_properties(self) -> None:
        self.assertIs(self.teleop.input_control_device, self.input_device)
        self.assertIs(self.teleop.robot_arm, self.arm)
        self.assertFalse(self.teleop.is_running)

    def test_start_and_stop_lifecycle(self) -> None:
        self.teleop.start()
        self.assertTrue(self.teleop.is_running)

        self.teleop.stop()
        self.assertFalse(self.teleop.is_running)

    def test_step_with_movement_disabled_does_not_command_joints(self) -> None:
        self.teleop.start()
        self.fake_servo.position_commands.clear()

        self.input_device.states.append(
            ControlState(
                axes={"left_x": 1.0},
                movement_enabled=False,
                delta_time=0.02,
            )
        )

        should_continue = self.teleop.step(0.02)
        self.assertTrue(should_continue)
        self.assertEqual(len(self.fake_servo.position_commands), 0)

    def test_step_with_movement_enabled_jogs_base_yaw(self) -> None:
        self.teleop.start()
        self.fake_servo.position_commands.clear()

        self.input_device.states.append(
            ControlState(
                axes={"left_x": 1.0},
                movement_enabled=True,
                delta_time=0.02,
            )
        )

        should_continue = self.teleop.step(0.02)
        self.assertTrue(should_continue)
        # Should have sent position command for base_yaw
        self.assertTrue(
            any(cmd[0] == 1 for cmd in self.fake_servo.position_commands)
        )

    def test_step_with_left_y_jogs_shoulder_and_elbow(self) -> None:
        self.teleop.start()
        self.fake_servo.position_commands.clear()

        self.input_device.states.append(
            ControlState(
                axes={"left_y": 1.0},
                movement_enabled=True,
                delta_time=0.02,
            )
        )

        should_continue = self.teleop.step(0.02)
        self.assertTrue(should_continue)

        servo_ids_moved = {cmd[0] for cmd in self.fake_servo.position_commands}
        self.assertIn(2, servo_ids_moved)  # shoulder_pitch
        self.assertIn(3, servo_ids_moved)  # elbow_pitch

    def test_step_with_dpad_jogs_elbow_and_base(self) -> None:
        self.teleop.start()
        self.fake_servo.position_commands.clear()

        self.input_device.states.append(
            ControlState(
                axes={"dpad_y": 1.0, "dpad_x": 1.0},
                movement_enabled=True,
                delta_time=0.02,
            )
        )

        should_continue = self.teleop.step(0.02)
        self.assertTrue(should_continue)

        servo_ids_moved = {cmd[0] for cmd in self.fake_servo.position_commands}
        self.assertIn(1, servo_ids_moved)  # base_yaw
        self.assertIn(3, servo_ids_moved)  # elbow_pitch

    def test_step_with_wrist_pitch_and_roll(self) -> None:
        self.teleop.start()
        self.fake_servo.position_commands.clear()

        self.input_device.states.append(
            ControlState(
                axes={"right_y": 1.0, "right_x": 1.0},
                movement_enabled=True,
                delta_time=0.02,
            )
        )

        should_continue = self.teleop.step(0.02)
        self.assertTrue(should_continue)

        servo_ids_moved = {cmd[0] for cmd in self.fake_servo.position_commands}
        self.assertIn(4, servo_ids_moved)  # wrist_pitch
        self.assertIn(5, servo_ids_moved)  # wrist_roll

    def test_step_emergency_stop_halts_and_disables_torque(self) -> None:
        self.teleop.start()
        self.input_device.states.append(
            ControlState(
                emergency_stop=True,
                movement_enabled=False,
            )
        )

        should_continue = self.teleop.step()
        self.assertFalse(should_continue)
        self.assertFalse(self.teleop.is_running)
        self.assertTrue(any("emergência" in log.lower() for log in self.output_logs))

    @patch("src.application.teleoperation.move_arm_to_home")
    def test_step_home_shortcut_triggers_home_move(self, mock_home) -> None:
        self.teleop.start()
        self.input_device.states.append(
            ControlState(
                axes={"r2": 1.0},
                buttons_pressed=frozenset({"cross"}),
                movement_enabled=True,
            )
        )

        should_continue = self.teleop.step()
        self.assertTrue(should_continue)
        mock_home.assert_called_once()

    def test_step_gripper_ability_starts_on_l2_double_press(self) -> None:
        self.teleop.start()
        self.assertFalse(self.arm.close_gripper_ability_active)

        # First press
        self.input_device.states.append(
            ControlState(axes={"l2": 1.0}, movement_enabled=True)
        )
        self.teleop.step(0.02)

        # Release
        self.input_device.states.append(
            ControlState(axes={"l2": 0.0}, movement_enabled=True)
        )
        self.teleop.step(0.02)

        # Second press quickly
        self.input_device.states.append(
            ControlState(axes={"l2": 1.0}, movement_enabled=True)
        )
        self.teleop.step(0.02)

        self.assertTrue(self.arm.close_gripper_ability_active)
        self.assertTrue(any("Fechamento automático" in log for log in self.output_logs))


if __name__ == "__main__":
    unittest.main()
