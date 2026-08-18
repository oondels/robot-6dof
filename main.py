from scservo_sdk import *
from models.Joint import Joint 

PORT = "/dev/ttyUSB0"
BAUDRATE = 1_000_000

port = PortHandler(PORT)
servo = sms_sts(port)

try:
    if not port.openPort():
        raise RuntimeError("Erro abrindo porta")

    if not port.setBaudRate(BAUDRATE):
        raise RuntimeError("Erro configurando baudrate")

    joint_1 = Joint(
        servo_id=6,
        servo=servo,
        name="Joint 1",
        min_pos=0,
        max_pos=4095,
    )

    joint_1.enable_torque()

    joint_1.move(
        angle=5,
        speed=1000,
        acc=100,
    )

finally:
    port.closePort()