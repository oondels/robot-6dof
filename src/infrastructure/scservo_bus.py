from collections.abc import Sequence

from scservo_sdk import COMM_SUCCESS, sms_sts

from src.application.ports.servo_bus import ServoBus, ServoPositionCommand

ADDR_TORQUE_ENABLE = 40
TORQUE_DISABLED = 0
TORQUE_ENABLED = 1


class ScServoBus(ServoBus):
    def __init__(self, servo: sms_sts) -> None:
        self._servo = servo

    def read_position(self, servo_id: int) -> int:
        position, _, result, error = self._servo.ReadPosSpeed(servo_id)
        self._validate_result(result, error, "leitura de posição")
        return position
    
    def read_load(self, servo_id: int) -> int:
      load, result, error = self._servo.read2ByteTxRx(
          servo_id,
          60, # endereço do registrador de memória do servo onde esta o load
      )
      self._validate_result(result, error, "leitura de carga")
      return load

    def is_moving(self, servo_id: int) -> bool:
        moving, result, error = self._servo.ReadMoving(servo_id)
        self._validate_result(result, error, "leitura do estado de movimento")
        return moving != 0

    def command_position(
        self,
        servo_id: int,
        position: int,
        speed: int,
        acceleration: int,
    ) -> None:
        result, error = self._servo.WritePosEx(
            servo_id,
            position,
            speed,
            acceleration,
        )
        self._validate_result(result, error, "comando de movimento")

    def is_torque_enabled(self, servo_id: int) -> bool:
        value, result, error = self._servo.read1ByteTxRx(
            servo_id,
            ADDR_TORQUE_ENABLE,
        )
        self._validate_result(result, error, "leitura do torque")
        return value == TORQUE_ENABLED

    def enable_torque(self, servo_id: int) -> None:
        self._write_torque(servo_id, TORQUE_ENABLED)

    def disable_torque(self, servo_id: int) -> None:
        self._write_torque(servo_id, TORQUE_DISABLED)

    def command_positions_sync(
        self,
        commands: Sequence[ServoPositionCommand],
    ) -> None:
        if not commands:
            raise ValueError("commands não pode estar vazio")

        try:
            self._servo.groupSyncWrite.clearParam()

            for command in commands:
                success = self._servo.SyncWritePosEx(
                    command.servo_id,
                    command.position,
                    command.speed,
                    command.acceleration,
                )
                if not success:
                    raise RuntimeError(
                        "Falha ao preparar comando sincronizado "
                        f"para o servo ID {command.servo_id}"
                    )

            result = self._servo.groupSyncWrite.txPacket()
            self._validate_result(result, 0, "envio de pose sincronizada")
        finally:
            self._servo.groupSyncWrite.clearParam()

    def _write_torque(self, servo_id: int, value: int) -> None:
        result, error = self._servo.write1ByteTxRx(
            servo_id,
            ADDR_TORQUE_ENABLE,
            value,
        )
        self._validate_result(result, error, "alteração do torque")

    def _validate_result(
        self,
        result: int,
        error: int,
        operation: str,
    ) -> None:
        if result != COMM_SUCCESS:
            raise RuntimeError(
                f"{operation}: {self._servo.getTxRxResult(result)}"
            )

        if error != 0:
            raise RuntimeError(
                f"{operation}: {self._servo.getRxPacketError(error)}"
            )
