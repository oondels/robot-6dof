from scservo_sdk import *
from dbm import error
from utils.validation import validate_result

DEFAULT_SPEED = 1000
DEFAULT_ACC = 100
BAUDRATE = 1_000_000
POSITION_TOLERANCE = 10
STEPS_PER_REVOLUTION = 4096
ADDR_TORQUE_ENABLE = 40


class Join:
    def __init__(
        self,
        port,
        servo_id,
        servo,
        name,
        min_pos,
        max_pos,
        speed=DEFAULT_SPEED,
        acc=DEFAULT_ACC,
    ):
        self.servo_id = servo_id
        self.port = port
        self.servo = servo
        self.name = name
        self.min_pos = min_pos
        self.max_pos = max_pos
        self.speed = speed
        self.acc = acc
        
        self.connect()

        
    def connect(self):
        if not self.port.openPort():
            raise RuntimeError("Erro abrindo porta")

        if not self.port.setBaudRate(BAUDRATE):
            raise RuntimeError("Erro configurando baudrate")

    def enable_torque(self):
        position = self.current_position()

        # Define posição atual como alvo antes de habilitar torque
        result, error = servo.WritePosEx(
            self.servo_id,
            position,
            self.speed,
            self.acc,
        )

        validate_result(
            servo,
            result,
            error,
            "Preparação da posição"
        )

        result, error = servo.write1ByteTxRx(
            self.servo_id,
            ADDR_TORQUE_ENABLE,
            1,
        )

        validate_result(
            servo,
            result,
            error,
            "Habilitação do torque"
        )

        torque, result, error = servo.read1ByteTxRx(
            self.servo_id,
            ADDR_TORQUE_ENABLE,
        )

        validate_result(
            servo,
            result,
            error,
            "Leitura do torque"
        )

        if torque != 1:
            raise RuntimeError(
                f"Torque não foi habilitado. Valor={torque}"
            )

        print("Torque habilitado")
    
    
    def current_position(self) -> int:
        position, speed, result, error = self.servo.ReadPosSpeed(self.servo_id)

        validate_result(self.servo, result, error, "Leitura de posição")

        return position
    
    def angle_to_position(self, angle: float) -> int:
        if not 0 <= angle <= 360:
            raise ValueError(
                "Ângulo deve estar entre 0° e 360°"
            )

        # 360° corresponde ao último count disponível
        if angle == 360:
            return self.max_pos

        position = round(
            angle * STEPS_PER_REVOLUTION / 360.0
        )

        return min(position, self.max_pos)
    
    # Move a junta com target -> angle                                                             
    def move(self, target, speed=DEFAULT_SPEED, acc=DEFAULT_ACC) -> int:
        if not self.min_pos <= target <= self.max_pos:
            raise ValueError(
                f"Target deve estar entre " f"{self.min_pos} e {self.max_pos}"
            )
            
        tarket_position = self.angle_to_position(target)

        position = self.current_position()
        error_position = abs(tarket_position - position)

        if error_position <= POSITION_TOLERANCE:
            print(f"Posição já atingida: " f"{position} " f"(erro={error_position})")

            return position

        print(f"Movendo {position} -> {tarket_position}")

        result, error = self.servo.WritePosEx(
            self.servo_id,
            tarket_position,
            speed,
            acc,
        )

        validate_result(self.servo, result, error, "Comando de movimento")

        final_position = self.current_position()
    
        final_error = abs(
            tarket_position - final_position
        )
        
        return final_position

PORT = "/dev/ttyUSB0"
port = PortHandler(PORT)
servo = sms_sts(port)

join_1 = Join(
    port,
    servo_id=6,
    servo=servo,
    name="Join 1",
    min_pos=0,
    max_pos=4095,
)

join_1.move(target=90, speed=1000, acc=100)

