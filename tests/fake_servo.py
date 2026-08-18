from scservo_sdk import COMM_SUCCESS


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

        self.position_sequence: list[int] = []
        self.moving_sequence: list[int] = []

    def queue_motion(
        self,
        positions: list[int],
        moving_states: list[int],
    ) -> None:
        self.position_sequence.extend(positions)
        self.moving_sequence.extend(moving_states)

    def ReadPosSpeed(
        self,
        servo_id: int,
    ) -> tuple[int, int, int, int]:
        if self.position_sequence:
            self.position = self.position_sequence.pop(0)

        return (
            self.position,
            self.speed,
            self.communication_result,
            self.packet_error,
        )

    def ReadMoving(
        self,
        servo_id: int,
    ) -> tuple[int, int, int]:
        if self.moving_sequence:
            self.moving = self.moving_sequence.pop(0)

        return (
            self.moving,
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

    def getTxRxResult(self, result: int) -> str:
        return f"Erro de comunicação simulado: {result}"

    def getRxPacketError(self, error: int) -> str:
        return f"Erro de pacote simulado: {error}"
