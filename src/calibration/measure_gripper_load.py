import argparse
import csv
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from scservo_sdk import PortHandler, sms_sts

from robot_config import JOINT_CONFIGS
from src.application.joint import Joint
from src.infrastructure.scservo_bus import ScServoBus

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 1_000_000
DEFAULT_STEP_DEG = 1.0
DEFAULT_SPEED = 200
DEFAULT_ACC = 30
SAMPLE_DURATION = 0.5
SAMPLE_INTERVAL = 0.05
LOAD_DIRECTION_BIT = 1 << 10
LOAD_MAGNITUDE_MASK = LOAD_DIRECTION_BIT - 1


def decode_load(raw_load: int) -> tuple[int, str, float]:
    if type(raw_load) is not int:
        raise TypeError("raw_load deve ser um número inteiro")

    if not 0 <= raw_load <= 0xFFFF:
        raise ValueError("raw_load deve estar entre 0 e 65535")

    magnitude = raw_load & LOAD_MAGNITUDE_MASK
    direction = "negativa" if raw_load & LOAD_DIRECTION_BIT else "positiva"
    load_percent = magnitude / 10.0
    return magnitude, direction, load_percent


def default_csv_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"/tmp/gripper_load_{timestamp}.csv")


def gripper_config():
    for config in JOINT_CONFIGS:
        if config.name == "gripper":
            return config

    raise RuntimeError("Configuração da junta 'gripper' não encontrada")


def collect_samples(
    joint: Joint,
    writer,
    label: str,
    operation: str,
    target_angle: float,
    started_at: float,
    magnitudes: list[int],
    output_fn: Callable[[str], None],
    clock: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
    sample_duration: float = SAMPLE_DURATION,
    sample_interval: float = SAMPLE_INTERVAL,
) -> None:
    sample_count = max(1, round(sample_duration / sample_interval))
    operation_magnitudes: list[int] = []

    for _ in range(sample_count):
        raw_load = joint.current_load()
        magnitude, direction, load_percent = decode_load(raw_load)
        position = joint.current_position()
        current_angle = joint.position_to_angle(position)
        elapsed = clock() - started_at

        writer.writerow(
            {
                "elapsed_s": f"{elapsed:.6f}",
                "label": label,
                "operation": operation,
                "target_angle_deg": f"{target_angle:.3f}",
                "current_angle_deg": f"{current_angle:.3f}",
                "position_counts": position,
                "raw_load": raw_load,
                "load_magnitude": magnitude,
                "load_direction": direction,
                "load_percent": f"{load_percent:.1f}",
            }
        )

        magnitudes.append(magnitude)
        operation_magnitudes.append(magnitude)
        output_fn(
            f"carga={magnitude:4d} ({load_percent:5.1f}%) | "
            f"direção={direction:8s} | posição={position:4d} counts | "
            f"ângulo={current_angle:7.2f}°"
        )
        sleep_fn(sample_interval)

    minimum = min(operation_magnitudes)
    maximum = max(operation_magnitudes)
    average = sum(operation_magnitudes) / len(operation_magnitudes)
    output_fn(
        f"Resumo da medição: mínimo={minimum}, média={average:.1f}, máximo={maximum}"
    )


def run_meter(
    joint: Joint,
    csv_path: Path,
    label: str,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    clock: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
    sample_duration: float = SAMPLE_DURATION,
    sample_interval: float = SAMPLE_INTERVAL,
) -> None:
    output_fn("=== Medidor supervisionado de carga da garra ===")
    output_fn("Use um objeto macio e mantenha as mãos afastadas das articulações.")
    output_fn("Este processo deve ser o único acessando a porta serial.")

    confirmation = input_fn("Digite SIM para habilitar o torque da garra: ")
    if confirmation.strip().lower() != "sim":
        output_fn("Medição cancelada. O torque não foi habilitado.")
        return

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    magnitudes: list[int] = []
    should_disable_torque = False

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = (
            "elapsed_s",
            "label",
            "operation",
            "target_angle_deg",
            "current_angle_deg",
            "position_counts",
            "raw_load",
            "load_magnitude",
            "load_direction",
            "load_percent",
        )
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        try:
            should_disable_torque = True
            joint.enable_torque()
            target_angle = max(
                joint.config.min_angle,
                min(joint.config.max_angle, joint.current_angle()),
            )
            started_at = clock()

            output_fn("Comandos: f=fechar 1°, a=abrir 1°, m=medir, q=sair")

            while True:
                command = input_fn("medidor> ").strip().lower()

                if command == "q":
                    break

                if command == "f":
                    next_angle = max(
                        joint.config.min_angle,
                        target_angle - DEFAULT_STEP_DEG,
                    )
                    if next_angle == target_angle:
                        output_fn("Limite mínimo da garra atingido. Comando ignorado.")
                        continue
                    target_angle = next_angle
                    joint.command(target_angle, speed=DEFAULT_SPEED, acc=DEFAULT_ACC)
                    operation = "fechar"
                elif command == "a":
                    next_angle = min(
                        joint.config.max_angle,
                        target_angle + DEFAULT_STEP_DEG,
                    )
                    if next_angle == target_angle:
                        output_fn("Limite máximo da garra atingido. Comando ignorado.")
                        continue
                    target_angle = next_angle
                    joint.command(target_angle, speed=DEFAULT_SPEED, acc=DEFAULT_ACC)
                    operation = "abrir"
                elif command == "m":
                    operation = "medir"
                else:
                    output_fn("Comando inválido. Use f, a, m ou q.")
                    continue

                collect_samples(
                    joint=joint,
                    writer=writer,
                    label=label,
                    operation=operation,
                    target_angle=target_angle,
                    started_at=started_at,
                    magnitudes=magnitudes,
                    output_fn=output_fn,
                    clock=clock,
                    sleep_fn=sleep_fn,
                    sample_duration=sample_duration,
                    sample_interval=sample_interval,
                )
                csv_file.flush()
        except KeyboardInterrupt:
            output_fn("\nMedição encerrada pelo operador.")
        finally:
            if magnitudes:
                minimum = min(magnitudes)
                maximum = max(magnitudes)
                average = sum(magnitudes) / len(magnitudes)
                output_fn(
                    f"Resumo global: mínimo={minimum}, média={average:.1f}, pico={maximum}"
                )

            if should_disable_torque:
                try:
                    joint.disable_torque()
                except RuntimeError as error:
                    output_fn(f"Falha ao desabilitar torque: {error}")

    output_fn(f"Medições salvas em: {csv_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mede a carga da garra em passos supervisionados de 1 grau."
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--label", default="ensaio")
    parser.add_argument("--csv", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = args.csv if args.csv is not None else default_csv_path()

    port = PortHandler(args.port)
    servo = sms_sts(port)
    port_open = False

    try:
        if not port.openPort():
            raise RuntimeError(f"Erro abrindo a porta {args.port}")
        port_open = True

        if not port.setBaudRate(args.baudrate):
            raise RuntimeError(f"Erro configurando baudrate {args.baudrate}")

        port.ser.exclusive = True
        servo_bus = ScServoBus(servo)
        joint = Joint(config=gripper_config(), servo_bus=servo_bus)
        run_meter(joint, csv_path=csv_path, label=args.label)
    finally:
        if port_open:
            port.closePort()


if __name__ == "__main__":
    main()
