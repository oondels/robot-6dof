import json
import time
from typing import Mapping

from src.infrastructure.input.ps5_controller import (
    Ps5ControllerInput,
    TriggerDoublePressDetector,
    find_ps5_controller_device,
)
from src.application.robot_arm import RobotArm
from src.actions.home_pose import move_arm_to_home
from src.application.ports.control_input import ControlState
from src.utils.adaptive_trigger import (
    apply_load_to_adaptive_trigger,
    set_dualsense_color,
)
from src.utils.dualsense_color import color_for_controller_state
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
GRIPPER_ABILITY_RELEASE_VALIDATIONS = 3
GRIPPER_ABILITY_ANGLE_TOLERANCE_DEG = 1.0
CONTROLLER_IDLE_TIMEOUT_S = 10.0

def handle_command(arm: RobotArm, command: str) -> None:
    pass

def collect_metrics(arm: RobotArm) -> None:
    robot_metrics = arm.get_status()
    joint_metrics = []
    for joint in arm.joints:
        joint_status = robot_metrics.joints[joint.name]
        joint_metrics.append(
            {
                "id": joint.servo_id,
                "temperature": joint_status.temperature,
                "current": joint_status.current,
                "load": joint_status.load,
                "load_direction": joint_status.load_direction,
                "speed": joint_status.speed,
                "acceleration": joint_status.acceleration,
                "position": joint_status.position,
            }
        )

    metrics_payload = json.dumps(
        {
            "timestamp": int(time.time() * 1000),
            "joints": joint_metrics,
        }
    )

    try:
        from websocket import WebSocketException, create_connection
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Instale as dependências do projeto para enviar métricas via WebSocket"
        ) from error

    websocket = None
    try:
        websocket = create_connection(
            "ws://localhost:2399/metrics",
            timeout=1,
        )
        websocket.send(metrics_payload)
    except (OSError, WebSocketException) as error:
        # print(f"[MÉTRICAS] Falha ao enviar dados: {error}")
        pass
    finally:
        if websocket is not None:
            websocket.close()

def run_control_loop(arm: RobotArm, controller: Ps5ControllerInput) -> None:
    target_angles = arm.current_angles()
    previous_axes: Mapping[str, float] | None = None
    previous_movement_enabled: bool | None = None
    previous_emergency_stop: bool | None = None
    home_shortcut_active = False
    gripper_load_alert_active = False
    previous_gripper_angle = target_angles["gripper"]
    consecutive_gripper_load_validations = 0
    consecutive_gripper_load_releases = 0
    l2_double_press_detector = TriggerDoublePressDetector()
    last_metrics_collection = 0.0
    last_controller_activity = time.monotonic()
    previous_controller_color = None

    while True:
        current_time = time.monotonic()
        if current_time - last_metrics_collection >= 0.5:
            collect_metrics(arm)
            last_metrics_collection = current_time

        state = controller.read()
        delta_time = state.delta_time if state.delta_time is not None else 0.0

        controller_has_activity = (
            previous_axes is not None
            and (
                state.axes != previous_axes
                or bool(state.buttons_pressed)
                or bool(state.buttons_released)
            )
        )
        if controller_has_activity:
            last_controller_activity = current_time

        controller_is_idle = (
            current_time - last_controller_activity
            >= CONTROLLER_IDLE_TIMEOUT_S
        )
        controller_color = color_for_controller_state(
            movement_enabled=state.movement_enabled,
            controller_is_idle=controller_is_idle,
        )
        if controller_color != previous_controller_color:
            set_dualsense_color(controller_color)
            previous_controller_color = controller_color

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
            apply_load_to_adaptive_trigger(0, 0.0, 0.0, shutdown=True)
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
            arm.finish_close_gripper_ability()
            gripper_load_alert_active = False
            previous_gripper_angle = target_angles["gripper"]
            consecutive_gripper_load_validations = 0
            apply_load_to_adaptive_trigger(0, 0.0, 0.0)
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

        # Desabilitar o movimento também encerra qualquer comando automático.
        # Uma habilidade nunca deve voltar a mover o robô ao rearmar o controle.
        if not state.movement_enabled:
            arm.finish_close_gripper_ability()

        # L2 + L2 -> habilidade de fechamento completo da garra.
        # A detecção usa a borda de pressão do eixo analógico. Assim, segurar o
        # L2 não é confundido com vários toques consecutivos.
        if (
            state.movement_enabled
            and l2_double_press_detector.update(l2, current_time)
        ):
            arm.start_close_gripper_ability()
            consecutive_gripper_load_releases = 0
            print("[HABILIDADE] Fechamento automático da garra iniciado.")

        if (
            not state.movement_enabled
            or (l2 == 0.0 and not arm.atuator_object)
        ):
            apply_load_to_adaptive_trigger(0, 0.0, 0.0)

        if state.movement_enabled and arm.atuator_object:
            apply_load_to_adaptive_trigger(
                raw_load=0,
                measured_velocity_deg_s=0.0,
                trigger_value=l2,
                hold_force=True,
            )

        if state.movement_enabled and r2 != 0.0 and not home_shortcut_active:
            target_angles["gripper"] += JOG_SPEED_DEG_S * delta_time * r2
            arm.atuator_object = False
            arm.finish_close_gripper_ability()
            gripper_load_alert_active = False
            consecutive_gripper_load_validations = 0
            consecutive_gripper_load_releases = 0
            target_changed = True
        elif (
            state.movement_enabled
            and not arm.atuator_object
            and (l2 != 0.0 or arm.close_gripper_ability_active)
        ):
            # Na habilidade, a garra fecha na velocidade integral mesmo depois
            # que o operador solta o L2. O limite físico ainda será aplicado.
            close_intensity = (
                1.0 if arm.close_gripper_ability_active else l2
            )
            target_angles["gripper"] -= (
                JOG_SPEED_DEG_S * delta_time * close_intensity
            )
            target_changed = True
        elif (
            state.movement_enabled
            and arm.atuator_object
            and arm.close_gripper_ability_active
        ):
            # Durante uma obstrução, continuamos apenas coletando o estado do
            # servo. O comando permanece na posição atual e não aperta mais.
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

                    if l2 != 0.0:
                        apply_load_to_adaptive_trigger(
                            raw_load=gripper_load,
                            measured_velocity_deg_s=measured_gripper_velocity,
                            trigger_value=l2,
                        )
                        
                    gripper_validation_target = clamped_angle
                    if arm.close_gripper_ability_active:
                        # Mantemos como referência o destino final da habilidade.
                        # Isso permite reconhecer que ainda existe uma obstrução,
                        # embora o servo esteja parado com segurança onde tocou.
                        gripper_validation_target = joint.config.min_angle

                    gripper_angle_error = (
                        gripper_validation_target - current_gripper_angle
                    )
                    gripper_current = joint.current_current()
                    previous_gripper_angle = current_gripper_angle

                    if l2 != 0.0:
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

                    gripper_is_closing = (
                        l2 != 0.0 or arm.close_gripper_ability_active
                    )
                    if gripper_is_closing:
                        # TODO: Essa verficiação deve ser feita dentro da classe do braço -> robot_arm
                        gripper_load_is_valid = validate_load(
                            raw_load=gripper_load,
                            measured_velocity_deg_s=measured_gripper_velocity,
                            angle_error_deg=gripper_angle_error,
                            current_a=gripper_current,
                        )

                        if arm.atuator_object and arm.close_gripper_ability_active:
                            # A habilidade não termina quando encontra algo.
                            # Ela aguarda a pressão desaparecer por algumas
                            # amostras antes de voltar a fechar automaticamente.
                            if gripper_load_is_valid:
                                consecutive_gripper_load_releases = 0
                            else:
                                consecutive_gripper_load_releases += 1

                            if (
                                consecutive_gripper_load_releases
                                >= GRIPPER_ABILITY_RELEASE_VALIDATIONS
                            ):
                                arm.atuator_object = False
                                consecutive_gripper_load_releases = 0
                                print(
                                    "[HABILIDADE] Obstrução removida. "
                                    "Retomando fechamento da garra."
                                )
                        elif gripper_load_is_valid:
                            consecutive_gripper_load_validations += 1
                        else:
                            consecutive_gripper_load_validations = 0

                        if (
                            not arm.atuator_object
                            and consecutive_gripper_load_validations >= 3
                        ):
                            target_angles["gripper"] = current_gripper_angle
                            joint.command(
                                current_gripper_angle,
                                speed=joint_speed,
                                acc=joint_acc,
                            )
                            arm.atuator_object = True
                            apply_load_to_adaptive_trigger(
                                raw_load=gripper_load,
                                measured_velocity_deg_s=(
                                    measured_gripper_velocity
                                ),
                                trigger_value=l2,
                                hold_force=True,
                            )
                            gripper_load_alert_active = False
                            consecutive_gripper_load_validations = 0
                            print(
                                f"[GARRA] Objeto detectado. "
                                f"Load={gripper_load_magnitude}, "
                                f"Velocidade={measured_gripper_velocity:.2f}°/s, "
                                f"Erro={abs(gripper_angle_error):.2f}°, "
                                f"Corrente={gripper_current:.3f} A"
                            )

                    if (
                        arm.close_gripper_ability_active
                        and not arm.atuator_object
                        and clamped_angle == joint.config.min_angle
                        and abs(gripper_angle_error)
                        <= GRIPPER_ABILITY_ANGLE_TOLERANCE_DEG
                    ):
                        arm.finish_close_gripper_ability()
                        print(
                            "[HABILIDADE] Fechamento automático da garra "
                            "concluído."
                        )
                else:
                    joint.command(clamped_angle)
        time.sleep(0.02)  # Pequena pausa para evitar uso excessivo da CPU


def controller_control(arm: RobotArm) -> None:
    controller = Ps5ControllerInput(find_ps5_controller_device())
    apply_load_to_adaptive_trigger(0, 0.0, 0.0, initialize=True)
    controller.open()

    try:
        run_control_loop(arm, controller)
    except KeyboardInterrupt:
        print("\n[AUDIT] Encerrando monitor...")
    finally:
        apply_load_to_adaptive_trigger(0, 0.0, 0.0, shutdown=True)
        move_arm_to_home(arm, output_fn=print)
        controller.close()
