import time
from typing import Mapping

from src.infrastructure.input.ps5_controller import (
    Ps5ControllerInput,
    find_ps5_controller_device,
)
from src.application.robot_arm import RobotArm
from src.actions.home_pose import move_arm_to_home
from src.application.ports.control_input import ControlState
from src.utils.validate_load import validate_load


def print_input_changes(
    state: ControlState,
    previous_axes: Mapping[str, float] | None,
    previous_movement_enabled: bool | None,
    previous_emergency_stop: bool | None,
) -> None:
    """Exibe somente alterações relevantes recebidas do controle."""
    if previous_axes is not None:
        changed_axes = {
            name: value
            for name, value in state.axes.items()
            if value != previous_axes.get(name, 0.0)
        }
        # if changed_axes:
        #     print("\n[ANALÓGICOS]")
        #     for name, value in changed_axes.items():
        #         print(f"  {name}: {value:+.2f}")

    # if state.buttons_pressed or state.buttons_released:
    #     print("\n[ BOTÕES ]")
    #     for name in sorted(state.buttons_pressed):
    #         print(f"  pressionado: {name}")
    #     for name in sorted(state.buttons_released):
    #         print(f"  solto: {name}")

    movement_changed = previous_movement_enabled != state.movement_enabled
    emergency_changed = previous_emergency_stop != state.emergency_stop
    if previous_movement_enabled is not None and (movement_changed or emergency_changed):
        print("\n[ SEGURANÇA ]")
        if movement_changed:
            status = "ATIVADO" if state.movement_enabled else "DESATIVADO"
            print(f"  movimento: {status}")
        if emergency_changed:
            status = "ATIVA" if state.emergency_stop else "LIBERADA"
            print(f"  emergência: {status}")


JOG_SPEED_DEG_S = 60.0  # Velocidade de movimento em graus por segundo
INVERSE_MODE = True # Inververte o sentido do eixo x, por motivos de vizualização, para que o movimento do joystick seja intuitivo para o usuário.

def run_control_loop(arm: RobotArm, controller: Ps5ControllerInput) -> None:
    target_angles = arm.current_angles()
    previous_axes: Mapping[str, float] | None = None
    previous_movement_enabled: bool | None = None
    previous_emergency_stop: bool | None = None
    home_shortcut_active = False
    gripper_load_alert_active = False
    previous_gripper_angle = target_angles["gripper"]
    consecutive_gripper_load_validations = 0

    while True:
        state = controller.read()
        delta_time = state.delta_time if state.delta_time is not None else 0.0
        print_input_changes(
            state,
            previous_axes,
            previous_movement_enabled,
            previous_emergency_stop,
        )
        previous_axes = dict(state.axes)
        previous_movement_enabled = state.movement_enabled
        previous_emergency_stop = state.emergency_stop

        if state.emergency_stop:
            print("[ALERTA] Parada de emergência acionada!")
            arm.disable_torque()
            break

        target_changed = False

        axes = state.axes

        # R2 + X -> Posição Home
        r2 = axes.get("r2", 0.0)
        if home_shortcut_active and r2 == 0.0:
            home_shortcut_active = False

        if state.movement_enabled and r2 > 0.0 and "cross" in state.buttons_pressed:
            move_arm_to_home(arm, output_fn=print, service="r2-x")
            target_angles = arm.current_angles()
            arm.atuator_object = False
            gripper_load_alert_active = False
            previous_gripper_angle = target_angles["gripper"]
            consecutive_gripper_load_validations = 0
            home_shortcut_active = True
            continue

        # Movimento analogico esquerdo eixo x -> Base (base_yaw)
        if INVERSE_MODE:
            left_x = axes.get("left_x", 0.0) # Tranformar em tipo para ficar mais legivel no codgio
            if state.movement_enabled and left_x != 0.0:
                target_angles["base_yaw"] -= JOG_SPEED_DEG_S * delta_time * left_x
                target_changed = True
        else:
            left_x = axes.get("left_x", 0.0) # Tranformar em tipo para ficar mais legivel no codgio
            if state.movement_enabled and left_x != 0.0:
                target_angles["base_yaw"] += JOG_SPEED_DEG_S * delta_time * left_x
                target_changed = True

        # Movimento analogico esquerdo eixo y -> Ombro e cotovelo
        left_y = axes.get("left_y", 0.0)
        if state.movement_enabled and left_y != 0.0:
            target_angles["shoulder_pitch"] += JOG_SPEED_DEG_S * delta_time * left_y
            target_angles["elbow_pitch"] += JOG_SPEED_DEG_S * delta_time * left_y
            target_changed = True

        # Setas para cima/baixo -> Cotovelo (elbow_pitch)
        dpad_y = axes.get("dpad_y", 0.0)
        if state.movement_enabled and dpad_y != 0.0:
            target_angles["elbow_pitch"] += JOG_SPEED_DEG_S * delta_time * dpad_y
            target_changed = True
        
        # Setas para esquerda/direita -> Cotovelo (elbow_pitch)
        dpad_x = axes.get("dpad_x", 0.0)
        if INVERSE_MODE:
            if state.movement_enabled and dpad_x != 0.0:
                target_angles["base_yaw"] -= JOG_SPEED_DEG_S * delta_time * dpad_x
                target_changed = True
        else:
            if state.movement_enabled and dpad_x != 0.0:
                target_angles["base_yaw"] += JOG_SPEED_DEG_S * delta_time * dpad_x
                target_changed = True

        # Movimento analogico direito eixo y -> Punho (wrist_pitch) -> Cima Baixo
        right_y = axes.get("right_y", 0.0)
        if state.movement_enabled and right_y != 0.0:
            target_angles["wrist_pitch"] += JOG_SPEED_DEG_S * delta_time * right_y
            target_changed = True
        
        # Movimento analogico direito eixo s -> Punho (wrist_roll) -> Girar
        right_x = axes.get("right_x", 0.0)
        if INVERSE_MODE:
            if state.movement_enabled and right_x != 0.0:
                target_angles["wrist_roll"] -= JOG_SPEED_DEG_S * delta_time * right_x
                target_changed = True
        else:
            if state.movement_enabled and right_x != 0.0:
                target_angles["wrist_roll"] += JOG_SPEED_DEG_S * delta_time * right_x
                target_changed = True

        # Gatilhos -> Garra: R2 abre; L2 fecha.
        l2 = axes.get("l2", 0.0)
        if state.movement_enabled and r2 != 0.0 and not home_shortcut_active:
            target_angles["gripper"] += JOG_SPEED_DEG_S * delta_time * r2
            arm.atuator_object = False
            gripper_load_alert_active = False
            consecutive_gripper_load_validations = 0
            target_changed = True
        elif state.movement_enabled and l2 != 0.0 and not arm.atuator_object:
            target_angles["gripper"] -= JOG_SPEED_DEG_S * delta_time * l2
            target_changed = True
            
        # Movimento não bloqueante com `command` para cada junta
        if target_changed:
            for joint_name, desired_angle in target_angles.items():
                joint = arm.joint(joint_name)

                # Garante que não ultrapassa os limites físicos (Limitando os angulos ao limite máximo e mínimo da junta)
                clamped_angle = max(
                    joint.config.min_angle, min(joint.config.max_angle, desired_angle)
                )
                target_angles[joint_name] = clamped_angle

                # Envio não-bloqueante para o hardware
                # TODO: Separar essa responsabilidade em 'TeleOperation'
                if joint.name == "gripper":
                    joint_speed = 700
                    joint_acc = 30
                    
                    # Coletar dados -> load X vcc x acc
                    joint.command(clamped_angle, speed=joint_speed, acc=joint_acc)
                    gripper_load = joint.current_load()
                    gripper_load_magnitude = gripper_load & 0x3FF
                    current_gripper_angle = joint.current_angle()
                    measured_gripper_velocity = 0.0
                    
                    if delta_time > 0.0:
                        measured_gripper_velocity = (
                            current_gripper_angle - previous_gripper_angle
                        ) / delta_time
                        
                    gripper_angle_error = clamped_angle - current_gripper_angle
                    gripper_current = joint.current_current()
                    previous_gripper_angle = current_gripper_angle

                    if l2 != 0.0:
                        print(f"[GARRA] Config Atual: Vcc: {joint_speed}, Acc: {joint_acc}, Angulo: {clamped_angle}, Load: {gripper_load_magnitude}")
                        print(f"[GARRA] Load atual: {gripper_load_magnitude}")
                        with open(
                            "/home/oendel/code/robotics/src/calibration/load_measurements/calibracoes_triggerps5_load.txt",
                            "a",
                            encoding="utf-8",
                        ) as load_measurements_file:
                            load_measurements_file.write(
                                f"[GARRA] Config Atual: Vcc: {joint_speed}, Acc: {joint_acc}, "
                                f"Angulo: {clamped_angle}, Load: {gripper_load_magnitude}\n"
                            )
                            load_measurements_file.write(
                                f"[GARRA] Load atual: {gripper_load_magnitude}\n"
                            )

                    if l2 != 0.0 and not arm.atuator_object:
                        gripper_load_is_valid = validate_load(
                            raw_load=gripper_load,
                            measured_velocity_deg_s=measured_gripper_velocity,
                            angle_error_deg=gripper_angle_error,
                            current_a=gripper_current,
                        )

                        if gripper_load_is_valid:
                            consecutive_gripper_load_validations += 1
                        else:
                            consecutive_gripper_load_validations = 0

                        if consecutive_gripper_load_validations >= 3:
                            target_angles["gripper"] = current_gripper_angle
                            joint.command(
                                current_gripper_angle,
                                speed=joint_speed,
                                acc=joint_acc,
                            )
                            arm.atuator_object = True
                            gripper_load_alert_active = False
                            consecutive_gripper_load_validations = 0
                            print(
                                f"[GARRA] Objeto detectado. "
                                f"Load={gripper_load_magnitude}, "
                                f"Velocidade={measured_gripper_velocity:.2f}°/s, "
                                f"Erro={abs(gripper_angle_error):.2f}°, "
                                f"Corrente={gripper_current:.3f} A"
                            )
                else:
                    joint.command(clamped_angle)
        time.sleep(0.02)  # Pequena pausa para evitar uso excessivo da CPU


def controller_control(arm: RobotArm) -> None:
    controller = Ps5ControllerInput(find_ps5_controller_device())
    controller.open()

    try:
        run_control_loop(arm, controller)
    except KeyboardInterrupt:
        print("\n[AUDIT] Encerrando monitor...")
    finally:
        move_arm_to_home(arm, output_fn=print)
        controller.close()
