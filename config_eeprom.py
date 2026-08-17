from scservo_sdk import *

PORT = "/dev/ttyUSB0"
BAUDRATE = 1_000_000
SERVO_ID = 6

MIN_ANGLE_ADDR = 9
MAX_ANGLE_ADDR = 11

port = PortHandler(PORT)
servo = sms_sts(port)

try:
    if not port.openPort():
        raise RuntimeError("Erro ao abrir porta")

    if not port.setBaudRate(BAUDRATE):
        raise RuntimeError("Erro ao configurar baudrate")

    # Desabilita torque antes de alterar EEPROM
    servo.write1ByteTxRx(SERVO_ID, 40, 0)

    # Desbloqueia EEPROM
    result, error = servo.unLockEprom(SERVO_ID)
    print("Unlock EEPROM:", result, error)

    # Range máximo: 0 ~ 4095
    result, error = servo.write2ByteTxRx(
        SERVO_ID,
        MIN_ANGLE_ADDR,
        0
    )
    print("Min:", result, error)

    result, error = servo.write2ByteTxRx(
        SERVO_ID,
        MAX_ANGLE_ADDR,
        4095
    )
    print("Max:", result, error)

    # Bloqueia novamente
    result, error = servo.LockEprom(SERVO_ID)
    print("Lock EEPROM:", result, error)

    # Confirma os valores
    min_angle, result, error = servo.read2ByteTxRx(
        SERVO_ID,
        MIN_ANGLE_ADDR
    )

    max_angle, result, error = servo.read2ByteTxRx(
        SERVO_ID,
        MAX_ANGLE_ADDR
    )

    print()
    print("Range configurado:")
    print("Min:", min_angle)
    print("Max:", max_angle)

finally:
    port.closePort()