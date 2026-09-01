from scservo_sdk import COMM_SUCCESS


class FakeGroupSyncWrite:
    def __init__(self, parent: "FakeServo") -> None:
        self.parent = parent
        self.data_dict: dict[int, list[int]] = {}
        self.tx_history: list[dict[int, list[int]]] = []

    def clearParam(self) -> None:
        self.data_dict.clear()

    def addParam(self, scs_id: int, data: list[int]) -> bool:
        if scs_id in self.data_dict:
            return False
        self.data_dict[scs_id] = list(data)
        return True

    def txPacket(self) -> int:
        if not self.data_dict:
            return -1
        self.tx_history.append(dict(self.data_dict))
        return self.parent.communication_result


class FakeServo:
    def __init__(
        self,
        position: int = 0,
        speed: int = 0,
        moving: int = 0,
    ) -> None:
        self.position = position
        self.speed = speed
        self.moving = moving

        self.communication_result = COMM_SUCCESS
        self.packet_error = 0

        self.registers: dict[int, int] = {}

        self.position_commands: list[tuple[int, int, int, int]] = []
        self.sync_write_commands: list[tuple[int, int, int, int]] = []

        self.position_sequence: list[int] = []
        self.moving_sequence: list[int] = []

        self.positions_by_servo: dict[int, int] = {}
        self.motion_by_servo: dict[int, tuple[list[int], list[int]]] = {}

        self.groupSyncWrite = FakeGroupSyncWrite(self)

    def queue_motion(
        self,
        positions: list[int],
        moving_states: list[int],
        servo_id: int | None = None,
    ) -> None:
        if servo_id is None:
            self.position_sequence.extend(positions)
            self.moving_sequence.extend(moving_states)
        else:
            pos_list, mov_list = self.motion_by_servo.get(servo_id, ([], []))
            pos_list.extend(positions)
            mov_list.extend(moving_states)
            self.motion_by_servo[servo_id] = (pos_list, mov_list)

    def ReadPosSpeed(
        self,
        servo_id: int,
    ) -> tuple[int, int, int, int]:
        if servo_id in self.motion_by_servo:
            pos_list, _ = self.motion_by_servo[servo_id]
            if pos_list:
                self.positions_by_servo[servo_id] = pos_list.pop(0)
            current_pos = self.positions_by_servo.get(servo_id, self.position)
        elif self.position_sequence:
            self.position = self.position_sequence.pop(0)
            current_pos = self.position
        else:
            current_pos = self.positions_by_servo.get(servo_id, self.position)

        return (
            current_pos,
            self.speed,
            self.communication_result,
            self.packet_error,
        )

    def ReadMoving(
        self,
        servo_id: int,
    ) -> tuple[int, int, int]:
        if servo_id in self.motion_by_servo:
            _, mov_list = self.motion_by_servo[servo_id]
            if mov_list:
                self.moving = mov_list.pop(0)
            current_moving = self.moving
        elif self.moving_sequence:
            self.moving = self.moving_sequence.pop(0)
            current_moving = self.moving
        else:
            current_moving = self.moving

        return (
            current_moving,
            self.communication_result,
            self.packet_error,
        )

    def WritePosEx(
        self,
        servo_id: int,
        position: int,
        speed: int,
        acc: int,
    ) -> tuple[int, int]:
        self.position_commands.append((servo_id, position, speed, acc))

        return (
            self.communication_result,
            self.packet_error,
        )

    def SyncWritePosEx(
        self,
        servo_id: int,
        position: int,
        speed: int,
        acc: int,
    ) -> bool:
        self.sync_write_commands.append((servo_id, position, speed, acc))
        return self.groupSyncWrite.addParam(servo_id, [acc, position, speed])

    def write1ByteTxRx(
        self,
        servo_id: int,
        address: int,
        value: int,
    ) -> tuple[int, int]:
        self.registers[address] = value

        return (
            self.communication_result,
            self.packet_error,
        )

    def read1ByteTxRx(
        self,
        servo_id: int,
        address: int,
    ) -> tuple[int, int, int]:
        value = self.registers.get(address, 0)

        return (
            value,
            self.communication_result,
            self.packet_error,
        )

    def read2ByteTxRx(
        self,
        servo_id: int,
        address: int,
    ) -> tuple[int, int, int]:
        value = self.registers.get(address, 0)

        return (
            value,
            self.communication_result,
            self.packet_error,
        )

    @staticmethod
    def scs_tohost(a: int, b: int) -> int:
        if a & (1 << b):
            return -(a & ~(1 << b))
        return a

    def getTxRxResult(self, result: int) -> str:
        return f"Erro de comunicação simulado: {result}"

    def getRxPacketError(self, error: int) -> str:
        return f"Erro de pacote simulado: {error}"
