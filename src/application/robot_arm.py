from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isfinite
from time import monotonic, sleep

from .joint import Joint, JointStatus
from .joint_config import JointConfig
from .movement_status import MovementStatus
from .ports.servo_bus import ServoBus, ServoPositionCommand


@dataclass(frozen=True, slots=True)
class RobotStatus:
    """Fotografia dos status de todas as juntas do robô."""

    joints: dict[str, JointStatus]
    timestamp: float = field(default_factory=monotonic)


class RobotArm:
    def __init__(
        self,
        servo_bus: ServoBus,
        joints: Sequence[Joint],
        atuator_object: bool = False,
    ) -> None:
        if servo_bus is None:
            raise ValueError("servo_bus não pode ser None")

        if not joints:
            raise ValueError("O braço robótico deve conter ao menos uma junta.")

        if not isinstance(atuator_object, bool):
            raise TypeError("atuator_object deve ser booleano")

        self._validate_unique_joints(joints)
        self._joints: tuple[Joint, ...] = tuple(joints)
        self._joints_by_name: dict[str, Joint] = {
            joint.name.lower(): joint for joint in self._joints
        }
        self._servo_bus = servo_bus
        self._atuator_object = atuator_object
        self._close_gripper_ability_active = False
        self._status: RobotStatus | None = None

    @property
    def atuator_object(self) -> bool:
        """Indica se a garra está segurando um objeto por limite de carga."""
        return self._atuator_object

    @atuator_object.setter
    def atuator_object(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("atuator_object deve ser booleano")
        self._atuator_object = value

    @property
    def close_gripper_ability_active(self) -> bool:
        """Indica se o fechamento automático da garra está em execução."""
        return self._close_gripper_ability_active

    def start_close_gripper_ability(self) -> None:
        """Inicia a habilidade de fechar completamente a garra."""
        self._close_gripper_ability_active = True

    def finish_close_gripper_ability(self) -> None:
        """Finaliza a habilidade de fechamento automático da garra."""
        self._close_gripper_ability_active = False

    @property
    def joints(self) -> tuple[Joint, ...]:
        """Retorna a coleção imutável e ordenada de juntas do robô."""
        return self._joints

    @property
    def joint_names(self) -> tuple[str, ...]:
        """Retorna os nomes de todas as juntas na ordem do braço."""
        return tuple(joint.name for joint in self._joints)

    @staticmethod
    def _validate_unique_joints(joints: Sequence[Joint]) -> None:
        seen_names: set[str] = set()
        seen_ids: set[int] = set()

        for joint in joints:
            if not isinstance(joint, Joint):
                raise TypeError("Todos os elementos devem ser instâncias de Joint.")

            normalized_name = joint.name.strip().lower()
            if normalized_name in seen_names:
                raise ValueError(f"Nome de junta duplicado: '{joint.name}'")
            seen_names.add(normalized_name)

            if joint.servo_id in seen_ids:
                raise ValueError(f"ID de servo duplicado: {joint.servo_id}")
            seen_ids.add(joint.servo_id)

    def joint(self, name: str) -> Joint:
        """Obtém uma junta específica pelo nome."""
        if not isinstance(name, str):
            raise TypeError("O nome da junta deve ser uma string.")

        normalized_name = name.strip().lower()
        if normalized_name not in self._joints_by_name:
            raise KeyError(f"Junta '{name}' não encontrada no braço robótico.")

        return self._joints_by_name[normalized_name]

    def __getitem__(self, name: str) -> Joint:
        """Permite acesso indexado por nome: arm['gripper']."""
        return self.joint(name)

    def __len__(self) -> int:
        """Retorna o número de juntas do robô."""
        return len(self._joints)

    def current_angles(self) -> dict[str, float]:
        """Lê e retorna os ângulos físicos atuais de todas as juntas em graus."""
        return {joint.name: joint.current_angle() for joint in self._joints}

    def current_positions(self) -> dict[str, int]:
        """Lê e retorna as posições brutas em counts de todas as juntas."""
        return {joint.name: joint.current_position() for joint in self._joints}

    def get_status(self) -> RobotStatus:
        """Coleta e armazena um pacote com o status de todas as juntas."""
        joint_statuses = {
            joint.name: joint.get_status()
            for joint in self._joints
        }
        self._status = RobotStatus(
            joints=joint_statuses,
            timestamp=monotonic(),
        )

        return self._status

    @property
    def status(self) -> RobotStatus | None:
        """Retorna o último pacote coletado sem consultar o hardware."""
        return self._status

    @property
    def is_movement_safe(self) -> bool:
        """Verifica se todas as juntas estão dentro do load configurado.

        Somente juntas que possuem ``maximum_safe_load`` participam da
        proteção. A leitura é feita no momento da consulta para que a decisão
        de segurança não dependa de um pacote de telemetria antigo.
        """
        return all(joint.is_load_safe for joint in self._joints)

    def enable_torque(self) -> None:
        """Habilita o torque de todas as juntas de forma segura."""
        for joint in self._joints:
            joint.enable_torque()

    def disable_torque(self) -> None:
        """Desabilita o torque de todas as juntas."""
        for joint in self._joints:
            joint.disable_torque()

    def is_torque_enabled(self) -> bool:
        """Retorna True se todas as juntas estiverem com torque habilitado."""
        return all(joint.is_torque_enabled() for joint in self._joints)

    def validate_pose(self, pose: dict[str, float]) -> None:
        """Valida se uma pose contém exatamente todas as juntas e ângulos dentro dos limites."""
        if not isinstance(pose, dict):
            raise TypeError("A pose deve ser um dicionário {nome_junta: angulo}.")

        if any(not isinstance(name, str) for name in pose):
            raise TypeError("Todos os nomes de junta da pose devem ser strings.")

        pose_names = {name.strip().lower() for name in pose}
        if len(pose_names) != len(pose):
            raise ValueError("Pose contém nomes de junta duplicados.")

        expected_names = set(self._joints_by_name)

        missing = expected_names - pose_names
        if missing:
            raise ValueError(f"Pose incompleta. Juntas ausentes: {sorted(missing)}")

        extra = pose_names - expected_names
        if extra:
            raise ValueError(f"Pose contém juntas desconhecidas: {sorted(extra)}")

        for name, angle in pose.items():
            joint = self._joints_by_name[name.strip().lower()]
            joint.angle_to_position(angle)

    @staticmethod
    def _validate_wait_parameter(
        parameter_name: str,
        value: float,
    ) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{parameter_name} deve ser um número")

        if not isfinite(value):
            raise ValueError(f"{parameter_name} deve ser finito")

        if value <= 0:
            raise ValueError(f"{parameter_name} deve ser maior que zero")

    def command_pose(
        self,
        pose: dict[str, float],
        acc: int | None = None,
        speed: int | None = None,
    ) -> dict[str, int]:
        """Envia uma pose sincronizada sem aguardar sua conclusão."""
        self.validate_pose(pose)

        if speed is not None:
            JointConfig.validate_speed(speed)
        if acc is not None:
            JointConfig.validate_acceleration(acc)

        normalized_pose = {
            name.strip().lower(): angle for name, angle in pose.items()
        }
        target_positions: dict[str, int] = {}
        commands: list[ServoPositionCommand] = []

        for joint in self._joints:
            angle = normalized_pose[joint.name.lower()]
            target_position = joint.angle_to_position(angle)
            target_positions[joint.name] = target_position
            commands.append(
                ServoPositionCommand(
                    servo_id=joint.servo_id,
                    position=target_position,
                    speed=joint.speed if speed is None else speed,
                    acceleration=joint.acc if acc is None else acc,
                )
            )

        self._servo_bus.command_positions_sync(commands)
        return target_positions

    def move_pose(
        self,
        pose: dict[str, float],
        timeout: float = 8.0,
        poll_interval: float = 0.05,
    ) -> dict[str, MovementStatus]:
        """Envia uma pose e aguarda todas as juntas alcançarem seus alvos."""
        self._validate_wait_parameter("timeout", timeout)
        self._validate_wait_parameter("poll_interval", poll_interval)

        target_positions = self.command_pose(pose)
        deadline = monotonic() + timeout

        while True:
            statuses = {
                joint.name: joint.movement_status(
                    target_positions[joint.name]
                )
                for joint in self._joints
            }

            if all(status.within_tolerance for status in statuses.values()):
                return statuses

            for joint in self._joints:
                status = statuses[joint.name]
                if not status.within_tolerance and not status.moving:
                    raise RuntimeError(
                        f"Pose falhou: junta '{joint.name}' parou fora do alvo "
                        f"(alvo={status.target_position}, "
                        f"posição={status.current_position}, "
                        f"erro={status.position_error} counts, "
                        f"tolerância="
                        f"{joint.tolerance_counts} counts)"
                    )

            remaining_time = deadline - monotonic()
            if remaining_time <= 0:
                unreached = [
                    f"{name} (erro={status.position_error} counts)"
                    for name, status in statuses.items()
                    if not status.within_tolerance
                ]
                raise TimeoutError(
                    f"Timeout após {timeout:.3f}s aguardando pose. "
                    f"Juntas que não alcançaram o alvo: {unreached}"
                )

            sleep(min(poll_interval, remaining_time))
