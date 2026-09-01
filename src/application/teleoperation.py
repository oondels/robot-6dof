from collections.abc import Callable, Mapping
import json
from time import monotonic, sleep, time

from src.application.ports.control_input import ControlInput, ControlState
from src.application.robot_arm import RobotArm
from src.infrastructure.input.ps5_controller import TriggerDoublePressDetector
from src.utils.adaptive_trigger import (
    apply_load_to_adaptive_trigger,
    set_dualsense_color,
)
from src.utils.dualsense_color import color_for_controller_state
from src.utils.validate_load import validate_load

DEFAULT_JOG_SPEED_DEG_S = 60.0
DEFAULT_IDLE_TIMEOUT_S = 10.0
GRIPPER_ABILITY_RELEASE_VALIDATIONS = 3
GRIPPER_ABILITY_ANGLE_TOLERANCE_DEG = 1.0
GRIPPER_COMMAND_SPEED = 700
GRIPPER_COMMAND_ACC = 30
MAX_DELTA_TIME_S = 0.05


def _collect_metrics(arm: RobotArm) -> None:
    """Coleta e transmite métricas do robô via WebSocket de forma não blocante."""
    try:
        from websocket import WebSocketException, create_connection
    except ModuleNotFoundError:
        return

    robot_metrics = arm.get_status()
    joint_metrics = [
        {
            "id": joint.servo_id,
            "temperature": robot_metrics.joints[joint.name].temperature,
            "current": robot_metrics.joints[joint.name].current,
            "load": robot_metrics.joints[joint.name].load,
            "load_direction": robot_metrics.joints[joint.name].load_direction,
            "speed": robot_metrics.joints[joint.name].speed,
            "acceleration": robot_metrics.joints[joint.name].acceleration,
            "position": robot_metrics.joints[joint.name].position,
        }
        for joint in arm.joints
    ]

    metrics_payload = json.dumps(
        {
            "timestamp": int(time() * 1000),
            "joints": joint_metrics,
        }
    )

    websocket = None
    try:
        websocket = create_connection(
            "ws://localhost:2399/metrics",
            timeout=1,
        )
        websocket.send(metrics_payload)
    except (OSError, WebSocketException):
        pass
    finally:
        if websocket is not None:
            websocket.close()


class TeleOperation:
    """Orquestrador de controle manual e teleoperação do braço robótico.

    Conecta um dispositivo de entrada (`ControlInput`) ao modelo do robô
    (`RobotArm`), integrando comandos de jog no tempo, aplicando restrições
    físicas, gerenciando estados de segurança e disparando feedbacks táteis
    e visuais.
    """

    def __init__(
        self,
        input_control_device: ControlInput,
        robot_arm: RobotArm,
        jog_speed: float = DEFAULT_JOG_SPEED_DEG_S,
        inverse_mode: bool = True,
        idle_timeout_s: float = DEFAULT_IDLE_TIMEOUT_S,
        enable_metrics: bool = True,
        output_fn: Callable[[str], None] = print,
    ) -> None:
        self._input_device = input_control_device
        self._arm = robot_arm
        self._jog_speed = jog_speed
        self._inverse_mode = inverse_mode
        self._idle_timeout_s = idle_timeout_s
        self._enable_metrics = enable_metrics
        self._output_fn = output_fn

        self._is_running = False
        self._target_angles: dict[str, float] = {}
        self._previous_axes: Mapping[str, float] | None = None
        self._previous_movement_enabled: bool | None = None
        self._previous_emergency_stop: bool | None = None
        self._home_shortcut_active = False
        self._previous_gripper_angle = 0.0
        self._consecutive_gripper_load_validations = 0
        self._consecutive_gripper_load_releases = 0
        self._l2_double_press_detector = TriggerDoublePressDetector()
        self._last_metrics_collection = 0.0
        self._last_controller_activity = monotonic()
        self._previous_controller_color = None

    @property
    def input_control_device(self) -> ControlInput:
        return self._input_device

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def robot_arm(self) -> RobotArm:
        return self._arm

    def start(self) -> None:
        """Inicializa alvos e estado operacional para iniciar a teleoperação."""
        self._is_running = True
        self._target_angles = self._arm.current_angles()
        self._previous_gripper_angle = self._target_angles.get("gripper", 0.0)
        self._last_controller_activity = monotonic()

    def stop(self) -> None:
        """Interrompe a teleoperação, desliga torques e zera feedbacks."""
        self._is_running = False
        apply_load_to_adaptive_trigger(0, 0.0, 0.0, shutdown=True)
        self._arm.disable_torque()

    def step(self, dt: float | None = None) -> bool:
        """Executa um único tick / ciclo de controle discreto no tempo.

        Retorna True para continuar o loop e False se o controle deve parar
        (por exemplo, ao acionar a parada de emergência).
        """
        current_time = monotonic()

        if self._enable_metrics and current_time - self._last_metrics_collection >= 0.5:
            _collect_metrics(self._arm)
            self._last_metrics_collection = current_time

        state = self._input_device.read()
        raw_dt = dt if dt is not None else state.delta_time
        delta_time = min(max(0.0, raw_dt or 0.0), MAX_DELTA_TIME_S)

        # 1. Detecção de atividade e status ocioso
        controller_has_activity = (
            self._previous_axes is not None
            and (
                state.axes != self._previous_axes
                or bool(state.buttons_pressed)
                or bool(state.buttons_released)
            )
        )
        if controller_has_activity or self._previous_axes is None:
            self._last_controller_activity = current_time

        controller_is_idle = (
            current_time - self._last_controller_activity >= self._idle_timeout_s
        )
        controller_color = color_for_controller_state(
            movement_enabled=state.movement_enabled,
            controller_is_idle=controller_is_idle,
        )
        if controller_color != self._previous_controller_color:
            set_dualsense_color(controller_color)
            self._previous_controller_color = controller_color

        self._print_input_changes(state)
        self._previous_axes = dict(state.axes)
        self._previous_movement_enabled = state.movement_enabled
        self._previous_emergency_stop = state.emergency_stop

        # 2. Parada de Emergência
        if state.emergency_stop:
            self._output_fn("[ALERTA] Parada de emergência acionada!")
            self.stop()
            return False

        if not self._target_angles:
            self._target_angles = self._arm.current_angles()
            self._previous_gripper_angle = self._target_angles.get("gripper", 0.0)

        target_changed = False
        axes = state.axes

        # 3. Atalho R2 + X -> Posição Home
        r2 = axes.get("r2", 0.0)
        if self._home_shortcut_active and r2 == 0.0:
            self._home_shortcut_active = False

        if state.movement_enabled and r2 > 0.0 and "cross" in state.buttons_pressed:
            move_arm_to_home(self._arm, output_fn=self._output_fn, service="r2-x")
            self._target_angles = self._arm.current_angles()
            self._arm.atuator_object = False
            self._arm.finish_close_gripper_ability()
            self._previous_gripper_angle = self._target_angles.get("gripper", 0.0)
            self._consecutive_gripper_load_validations = 0
            apply_load_to_adaptive_trigger(0, 0.0, 0.0)
            self._home_shortcut_active = True
            return True

        if state.movement_enabled:
            direction_mult = -1.0 if self._inverse_mode else 1.0

            # 4. Movimento Analógico Esquerdo Eixo X -> Base (base_yaw)
            target_changed |= self._apply_axis_jog(
                joint_name="base_yaw",
                input_value=axes.get("left_x", 0.0),
                delta_time=delta_time,
                direction_multiplier=direction_mult,
            )

            # 5. Movimento Analógico Esquerdo Eixo Y -> Ombro e Cotovelo
            left_y = axes.get("left_y", 0.0)
            target_changed |= self._apply_axis_jog(
                joint_name="shoulder_pitch",
                input_value=left_y,
                delta_time=delta_time,
            )
            target_changed |= self._apply_axis_jog(
                joint_name="elbow_pitch",
                input_value=left_y,
                delta_time=delta_time,
            )

            # 6. D-Pad Y -> Cotovelo (elbow_pitch)
            target_changed |= self._apply_axis_jog(
                joint_name="elbow_pitch",
                input_value=axes.get("dpad_y", 0.0),
                delta_time=delta_time,
            )

            # 7. D-Pad X -> Base (base_yaw)
            target_changed |= self._apply_axis_jog(
                joint_name="base_yaw",
                input_value=axes.get("dpad_x", 0.0),
                delta_time=delta_time,
                direction_multiplier=direction_mult,
            )

            # 8. Analógico Direito Eixo Y -> Punho (wrist_pitch)
            target_changed |= self._apply_axis_jog(
                joint_name="wrist_pitch",
                input_value=axes.get("right_y", 0.0),
                delta_time=delta_time,
            )

            # 9. Analógico Direito Eixo X -> Punho (wrist_roll)
            target_changed |= self._apply_axis_jog(
                joint_name="wrist_roll",
                input_value=axes.get("right_x", 0.0),
                delta_time=delta_time,
                direction_multiplier=direction_mult,
            )

        # 10. Gatilhos -> Garra: R2 abre; L2 fecha
        l2 = axes.get("l2", 0.0)

        # Se o movimento geral for desativado, encerra qualquer automação da garra
        if not state.movement_enabled:
            self._arm.finish_close_gripper_ability()

        # Duplo clique rápido no L2: inicia o fechamento automático da garra até encontrar carga/limite
        if (
            state.movement_enabled
            and self._l2_double_press_detector.update(l2, current_time)
        ):
            self._arm.start_close_gripper_ability()
            self._consecutive_gripper_load_releases = 0
            self._output_fn("[HABILIDADE] Fechamento automático da garra iniciado.")

        # Zera resistência do gatilho adaptativo se o movimento estiver desativado ou L2 em repouso
        if not state.movement_enabled or (l2 == 0.0 and not self._arm.atuator_object):
            apply_load_to_adaptive_trigger(0, 0.0, 0.0)

        # Se um objeto já foi detectado, mantém resistência de retenção no gatilho do controle
        if state.movement_enabled and self._arm.atuator_object:
            apply_load_to_adaptive_trigger(
                raw_load=0,
                measured_velocity_deg_s=0.0,
                trigger_value=l2,
                hold_force=True,
            )

        if "gripper" in self._target_angles:
            # Abertura manual da garra (R2):
            # Aumenta o ângulo, cancela automação de fechamento e reseta estado de objeto detectado
            if state.movement_enabled and r2 != 0.0 and not self._home_shortcut_active:
                self._target_angles["gripper"] += self._jog_speed * delta_time * r2
                self._arm.atuator_object = False
                self._arm.finish_close_gripper_ability()
                self._consecutive_gripper_load_validations = 0
                self._consecutive_gripper_load_releases = 0
                target_changed = True

            # Fechamento da garra (manual via L2 ou automático via habilidade):
            # Reduz o ângulo apenas se nenhum objeto foi detectado ainda
            elif (
                state.movement_enabled
                and not self._arm.atuator_object
                and (l2 != 0.0 or self._arm.close_gripper_ability_active)
            ):
                close_intensity = (
                    1.0 if self._arm.close_gripper_ability_active else l2
                )
                self._target_angles["gripper"] -= (
                    self._jog_speed * delta_time * close_intensity
                )
                target_changed = True

            # Garra parada segurando objeto durante fechamento automático:
            # Mantém target_changed ativo para continuar processando a remoção de obstrução no loop
            elif (
                state.movement_enabled
                and self._arm.atuator_object
                and self._arm.close_gripper_ability_active
            ):
                target_changed = True

        # 11. Aplicação não-bloqueante dos comandos para cada junta
        if target_changed:
            self._apply_joint_targets(l2, delta_time)

        return True

    def _apply_axis_jog(
        self,
        joint_name: str,
        input_value: float,
        delta_time: float,
        direction_multiplier: float = 1.0,
    ) -> bool:
        """Atualiza incrementalmente o ângulo alvo de uma junta a partir de um valor de entrada normalizado.

        Retorna True se o alvo foi alterado e False caso contrário (ex.: valor zerado,
        delta_time inválido ou junta não inicializada).
        """
        if (
            input_value == 0.0
            or delta_time <= 0.0
            or direction_multiplier == 0.0
            or joint_name not in self._target_angles
        ):
            return False

        angular_delta = (
            input_value
            * self._jog_speed
            * delta_time
            * direction_multiplier
        )
        self._target_angles[joint_name] += angular_delta
        return True

    def _apply_joint_targets(self, l2: float, delta_time: float) -> None:
        """Aplica os alvos calculados nas juntas com clamping e segurança."""
        for joint_name, desired_angle in self._target_angles.items():
            joint = self._arm.joint(joint_name)
            clamped_angle = max(
                joint.config.min_angle,
                min(joint.config.max_angle, desired_angle),
            )
            self._target_angles[joint_name] = clamped_angle

            if joint.name == "gripper":
                self._process_gripper_movement(
                    joint=joint,
                    clamped_angle=clamped_angle,
                    l2=l2,
                    delta_time=delta_time,
                )
            else:
                joint.command(clamped_angle)

    def _process_gripper_movement(
        self,
        joint,
        clamped_angle: float,
        l2: float,
        delta_time: float,
    ) -> None:
        """Executa controle especializado da garra com validação de carga."""
        joint.command(
            clamped_angle,
            speed=GRIPPER_COMMAND_SPEED,
            acc=GRIPPER_COMMAND_ACC,
        )
        gripper_load = joint.current_load()
        gripper_load_magnitude = gripper_load & 0x3FF
        current_gripper_angle = joint.current_angle()
        measured_gripper_velocity = 0.0

        if delta_time > 0.0:
            measured_gripper_velocity = (
                current_gripper_angle - self._previous_gripper_angle
            ) / delta_time

        if l2 != 0.0:
            apply_load_to_adaptive_trigger(
                raw_load=gripper_load,
                measured_velocity_deg_s=measured_gripper_velocity,
                trigger_value=l2,
            )

        gripper_validation_target = (
            joint.config.min_angle
            if self._arm.close_gripper_ability_active
            else clamped_angle
        )
        gripper_angle_error = gripper_validation_target - current_gripper_angle
        gripper_current = joint.current_current()
        self._previous_gripper_angle = current_gripper_angle

        gripper_is_closing = l2 != 0.0 or self._arm.close_gripper_ability_active
        if gripper_is_closing:
            gripper_load_is_valid = validate_load(
                raw_load=gripper_load,
                measured_velocity_deg_s=measured_gripper_velocity,
                angle_error_deg=gripper_angle_error,
                current_a=gripper_current,
            )

            if self._arm.atuator_object and self._arm.close_gripper_ability_active:
                if gripper_load_is_valid:
                    self._consecutive_gripper_load_releases = 0
                else:
                    self._consecutive_gripper_load_releases += 1

                if (
                    self._consecutive_gripper_load_releases
                    >= GRIPPER_ABILITY_RELEASE_VALIDATIONS
                ):
                    self._arm.atuator_object = False
                    self._consecutive_gripper_load_releases = 0
                    self._output_fn(
                        "[HABILIDADE] Obstrução removida. Retomando fechamento da garra."
                    )
            elif gripper_load_is_valid:
                self._consecutive_gripper_load_validations += 1
            else:
                self._consecutive_gripper_load_validations = 0

            if (
                not self._arm.atuator_object
                and self._consecutive_gripper_load_validations >= 3
            ):
                self._target_angles["gripper"] = current_gripper_angle
                joint.command(
                    current_gripper_angle,
                    speed=GRIPPER_COMMAND_SPEED,
                    acc=GRIPPER_COMMAND_ACC,
                )
                self._arm.atuator_object = True
                apply_load_to_adaptive_trigger(
                    raw_load=gripper_load,
                    measured_velocity_deg_s=measured_gripper_velocity,
                    trigger_value=l2,
                    hold_force=True,
                )
                self._consecutive_gripper_load_validations = 0
                self._output_fn(
                    f"[GARRA] Objeto detectado. Load={gripper_load_magnitude}, "
                    f"Velocidade={measured_gripper_velocity:.2f}°/s, "
                    f"Erro={abs(gripper_angle_error):.2f}°, "
                    f"Corrente={gripper_current:.3f} A"
                )

        if (
            self._arm.close_gripper_ability_active
            and not self._arm.atuator_object
            and clamped_angle == joint.config.min_angle
            and abs(gripper_angle_error) <= GRIPPER_ABILITY_ANGLE_TOLERANCE_DEG
        ):
            self._arm.finish_close_gripper_ability()
            self._output_fn("[HABILIDADE] Fechamento automático da garra concluído.")

    def _print_input_changes(self, state: ControlState) -> None:
        """Exibe alterações no estado de segurança operacional."""
        movement_changed = (
            self._previous_movement_enabled is not None
            and self._previous_movement_enabled != state.movement_enabled
        )
        emergency_changed = (
            self._previous_emergency_stop is not None
            and self._previous_emergency_stop != state.emergency_stop
        )

        if movement_changed or emergency_changed:
            self._output_fn("\n[ SEGURANÇA ]")
            if movement_changed:
                status = "ATIVADO" if state.movement_enabled else "DESATIVADO"
                self._output_fn(f"  movimento: {status}")
            if emergency_changed:
                status = "ATIVA" if state.emergency_stop else "LIBERADA"
                self._output_fn(f"  emergência: {status}")

    def run(self, frequency: float = 50.0) -> None:
        """Executa o loop contínuo de tempo real."""
        self.start()
        period = 1.0 / frequency if frequency > 0 else 0.02
        last_tick = monotonic()

        while self._is_running:
            current_tick = monotonic()
            dt = current_tick - last_tick
            last_tick = current_tick

            if not self.step(dt):
                break

            sleep(period)


from src.actions.home_pose import move_arm_to_home  # noqa: E402


