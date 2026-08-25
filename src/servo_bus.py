from typing import Any


class ServoBus:
    def __init__(self, id, servo_bus: Any) -> None: # Usei any por preguica, mas aqui seria a representacao classe de um servo bus
        print("ServoBus initialized")
        self.id = id
        self.servo_bus = servo_bus

    def read_current_position(self, servo_id: int) -> int:
        current_pos = 0
        print(f"Reading current position for servo ID: {servo_id}")

        return current_pos

    def is_moving(self, servo_id: int) -> bool:
        moving = False
        print(f"Checking if servo ID: {servo_id} is moving")

        return moving

    def command_single(
        self, servo_id: int, position: int, speed: int, acc: int
    ) -> None:
        print(
            f"Commanding servo ID: {servo_id} to position: {position}, speed: {speed}, acc: {acc}"
        )

    def command_multiple(
        self,
        servo_ids: list[int],
        positions: list[int],
        speeds: list[int],
        accs: list[int],
    ) -> None:
        print(
            f"Commanding multiple servos: {servo_ids} to positions: {positions}, speeds: {speeds}, accs: {accs}"
        )

    def status_torque(self, servo_id: int) -> bool:
        torque_enabled = True
        print(f"Checking torque status for servo ID: {servo_id}")

        return torque_enabled

    def _change_torque(self, servo_id: int, enable: bool) -> None:
        action = "Enabling" if enable else "Disabling"
        print(f"{action} torque for servo ID: {servo_id}")

    def enable_torque(self, servo_id: int) -> None:
        self._change_torque(servo_id, True)

    def disable_torque(self, servo_id: int) -> None:
        self._change_torque(servo_id, False)
