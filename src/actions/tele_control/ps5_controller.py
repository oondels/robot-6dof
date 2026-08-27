import time
from typing import Mapping

from src.infrastructure.input.ps5_controller import (
    Ps5ControllerInput,
    find_ps5_controller_device,
)
from src.application.robot_arm import RobotArm
from src.actions.home_pose import move_arm_to_home
from src.application.ports.control_input import ControlState


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
        if changed_axes:
            print("\n[ANALÓGICOS]")
            for name, value in changed_axes.items():
                print(f"  {name}: {value:+.2f}")

    if state.buttons_pressed or state.buttons_released:
        print("\n[ BOTÕES ]")
        for name in sorted(state.buttons_pressed):
            print(f"  pressionado: {name}")
        for name in sorted(state.buttons_released):
            print(f"  solto: {name}")

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


JOG_SPEED_DEG_S = 50.0  # Velocidade de movimento em graus por segundo
INVERSE_MODE = True # Inververte o sentido do eixo x, por motivos de vizualização, para que o movimento do joystick seja intuitivo para o usuário.

def run_control_loop(arm: RobotArm, controller: Ps5ControllerInput) -> None:
    target_angles = arm.current_angles()
    previous_axes: Mapping[str, float] | None = None
    previous_movement_enabled: bool | None = None
    previous_emergency_stop: bool | None = None
    home_shortcut_active = False

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
        gripper_joint = arm.joint("gripper")
        l2 = axes.get("l2", 0.0)
        if state.movement_enabled and r2 != 0.0 and not home_shortcut_active:
            target_angles["gripper"] += JOG_SPEED_DEG_S * delta_time * r2
            arm.atuator_object = False
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
                # TODO: Impolementar controle de vcc e acc para determinadas juntas
                if joint.name == "gripper":
                    joint.command(clamped_angle, speed=200, acc=30)
                    gripper_load = joint.current_load()
                    
                    # Criar logioca de detecao de load
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
