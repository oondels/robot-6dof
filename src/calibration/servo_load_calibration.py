import argparse
import csv
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from scservo_sdk import PortHandler, sms_sts

from robot_config import JOINT_CONFIGS
from src.application.joint import Joint
from src.infrastructure.input.ps5_controller import (
    Ps5ControllerInput,
    find_ps5_controller_device,
)
from src.infrastructure.scservo_bus import ScServoBus

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 1_000_000
DEFAULT_JOINT = "gripper"
DEFAULT_TRIGGER = "l2"
DEFAULT_JOG_SPEED_DEG_S = 60.0
LOOP_INTERVAL = 0.02
LOAD_DIRECTION_BIT = 1 << 10
LOAD_MAGNITUDE_MASK = LOAD_DIRECTION_BIT - 1
MEASUREMENTS_DIRECTORY = Path(
    "/home/oendel/code/robotics/src/calibration/load_measurements"
)
CSV_FIELDS = (
    "timestamp",
    "controller_timestamp_s",
    "label",
    "joint_name",
    "servo_id",
    "control_name",
    "control_value",
    "delta_time_s",
    "target_rate_deg_s",
    "measured_velocity_deg_s",
    "command_speed",
    "command_acceleration",
    "target_angle_deg",
    "current_angle_deg",
    "angle_error_deg",
    "target_position_counts",
    "current_position_counts",
    "position_error_counts",
    "raw_load",
    "load_magnitude",
    "load_direction",
    "load_percent",
    "voltage_v",
    "temperature_c",
    "current_a",
    "moving",
)


def find_joint_config(joint_name: str):
    normalized_name = joint_name.strip().lower()
    for config in JOINT_CONFIGS:
        if config.name.lower() == normalized_name:
            return config

    raise ValueError(f"Junta '{joint_name}' não encontrada em robot_config.py")


def decode_load(raw_load: int) -> tuple[int, str, float]:
    magnitude = raw_load & LOAD_MAGNITUDE_MASK
    direction = "negativa" if raw_load & LOAD_DIRECTION_BIT else "positiva"
    return magnitude, direction, magnitude / 10.0


def create_output_path(joint_name: str, label: str) -> Path:
    clean_label = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in label.strip()
    )
    if not clean_label:
        clean_label = "ensaio"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return MEASUREMENTS_DIRECTORY / (
        f"servo_load_{joint_name}_{clean_label}_{timestamp}.csv"
    )


def collect_servo_measurement(
    joint: Joint,
    label: str,
    control_name: str,
    control_value: float,
    controller_timestamp: float,
    delta_time: float,
    target_rate: float,
    previous_current_angle: float | None,
    command_speed: int,
    command_acceleration: int,
    target_angle: float,
    target_position: int,
) -> dict[str, object]:
    current_position = joint.current_position()
    current_angle = joint.position_to_angle(current_position)
    measured_velocity = 0.0
    if previous_current_angle is not None and delta_time > 0.0:
        measured_velocity = (current_angle - previous_current_angle) / delta_time
    raw_load = joint.current_load()
    load_magnitude, load_direction, load_percent = decode_load(raw_load)

    return {
        "timestamp": datetime.now().astimezone().isoformat(),
        "controller_timestamp_s": f"{controller_timestamp:.6f}",
        "label": label,
        "joint_name": joint.name,
        "servo_id": joint.servo_id,
        "control_name": control_name,
        "control_value": f"{control_value:.6f}",
        "delta_time_s": f"{delta_time:.6f}",
        "target_rate_deg_s": f"{target_rate:.6f}",
        "measured_velocity_deg_s": f"{measured_velocity:.6f}",
        "command_speed": command_speed,
        "command_acceleration": command_acceleration,
        "target_angle_deg": f"{target_angle:.6f}",
        "current_angle_deg": f"{current_angle:.6f}",
        "angle_error_deg": f"{abs(target_angle - current_angle):.6f}",
        "target_position_counts": target_position,
        "current_position_counts": current_position,
        "position_error_counts": abs(target_position - current_position),
        "raw_load": raw_load,
        "load_magnitude": load_magnitude,
        "load_direction": load_direction,
        "load_percent": f"{load_percent:.1f}",
        "voltage_v": f"{joint.current_voltage():.2f}",
        "temperature_c": f"{joint.current_temperature():.1f}",
        "current_a": f"{joint.current_current():.4f}",
        "moving": joint.is_moving(),
    }


def run_collection(
    joint: Joint,
    controller: Ps5ControllerInput,
    output_path: Path,
    label: str,
    trigger_name: str,
    command_speed: int,
    command_acceleration: int,
    jog_speed_deg_s: float,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    confirmation = input_fn(
        f"Digite SIM para habilitar o torque da junta '{joint.name}': "
    )
    if confirmation.strip().lower() != "sim":
        output_fn("Coleta cancelada. O torque não foi habilitado.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_angle = max(
        joint.config.min_angle,
        min(joint.config.max_angle, joint.current_angle()),
    )
    previous_current_angle: float | None = None
    should_disable_torque = False

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()

        try:
            should_disable_torque = True
            joint.enable_torque()
            output_fn("Pressione PS para habilitar o movimento.")
            output_fn(
                f"Use {trigger_name.upper()} para controlar a junta. "
                "L2 reduz o ângulo e R2 aumenta o ângulo."
            )
            output_fn("Pressione L2 e R2 juntos para emergência ou Ctrl+C para sair.")

            while True:
                state = controller.read()
                if state.emergency_stop:
                    output_fn("[ALERTA] Parada de emergência acionada.")
                    break

                delta_time = state.delta_time if state.delta_time is not None else 0.0
                trigger_value = state.axes.get(trigger_name, 0.0)

                if state.movement_enabled and trigger_value > 0.0:
                    direction = -1.0 if trigger_name == "l2" else 1.0
                    target_rate = direction * jog_speed_deg_s * trigger_value
                    desired_angle = target_angle + target_rate * delta_time
                    target_angle = max(
                        joint.config.min_angle,
                        min(joint.config.max_angle, desired_angle),
                    )
                    target_position = joint.command(
                        target_angle,
                        speed=command_speed,
                        acc=command_acceleration,
                    )
                    measurement = collect_servo_measurement(
                        joint=joint,
                        label=label,
                        control_name=trigger_name,
                        control_value=trigger_value,
                        controller_timestamp=state.timestamp,
                        delta_time=delta_time,
                        target_rate=target_rate,
                        previous_current_angle=previous_current_angle,
                        command_speed=command_speed,
                        command_acceleration=command_acceleration,
                        target_angle=target_angle,
                        target_position=target_position,
                    )
                    writer.writerow(measurement)
                    csv_file.flush()
                    previous_current_angle = float(measurement["current_angle_deg"])

                    output_fn(
                        f"trigger={trigger_value:.2f} | "
                        f"velocidade={measurement['measured_velocity_deg_s']}°/s | "
                        f"load={measurement['load_magnitude']} | "
                        f"tensão={measurement['voltage_v']}V | "
                        f"temperatura={measurement['temperature_c']}°C | "
                        f"corrente={measurement['current_a']}A"
                    )

                time.sleep(LOOP_INTERVAL)
        except KeyboardInterrupt:
            output_fn("\nColeta encerrada pelo operador.")
        finally:
            if should_disable_torque:
                try:
                    joint.disable_torque()
                except RuntimeError as error:
                    output_fn(f"Falha ao desabilitar torque: {error}")

    output_fn(f"Medições salvas em: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Coleta telemetria de load de um servo controlado pelo PS5."
    )
    parser.add_argument("--joint", default=DEFAULT_JOINT)
    parser.add_argument("--trigger", choices=("l2", "r2"), default=DEFAULT_TRIGGER)
    parser.add_argument("--speed", type=int)
    parser.add_argument("--acc", type=int)
    parser.add_argument("--jog-speed-deg-s", type=float, default=DEFAULT_JOG_SPEED_DEG_S)
    parser.add_argument("--label", default="ensaio")
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = find_joint_config(args.joint)
    command_speed = config.speed if args.speed is None else args.speed
    command_acceleration = config.acc if args.acc is None else args.acc
    output_path = create_output_path(config.name, args.label)

    port = PortHandler(args.port)
    servo = sms_sts(port)
    controller = Ps5ControllerInput(find_ps5_controller_device())
    port_open = False

    try:
        if not port.openPort():
            raise RuntimeError(f"Erro abrindo a porta {args.port}")
        port_open = True

        if not port.setBaudRate(args.baudrate):
            raise RuntimeError(f"Erro configurando baudrate {args.baudrate}")

        port.ser.exclusive = True
        controller.open()
        joint = Joint(config=config, servo_bus=ScServoBus(servo))
        run_collection(
            joint=joint,
            controller=controller,
            output_path=output_path,
            label=args.label,
            trigger_name=args.trigger,
            command_speed=command_speed,
            command_acceleration=command_acceleration,
            jog_speed_deg_s=args.jog_speed_deg_s,
        )
    finally:
        controller.close()
        if port_open:
            port.closePort()


if __name__ == "__main__":
    main()
