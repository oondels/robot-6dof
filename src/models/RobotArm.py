from collections.abc import Sequence
from math import isfinite
from time import monotonic, sleep
from typing import Any

from src.models.Joint import Joint, MovementStatus
from src.utils.validation import validate_result


class RobotArm:
    def __init__(self, joints: Sequence[Joint]) -> None:
        if not joints:
            raise ValueError("O braço robótico deve conter ao menos uma junta.")

        self._validate_unique_joints(joints)
        self._joints: tuple[Joint, ...] = tuple(joints)
        self._joints_by_name: dict[str, Joint] = {
            joint.name.lower(): joint for joint in self._joints
        }
        self._servo = self._joints[0].servo # Driver do protocolo de comunicação de todas as juntas -> Feeteck mesmo barramento

    @property
    def joints(self) -> tuple[Joint, ...]:
        """Retorna a coleção imutável e ordenada de juntas do robô."""
        return self._joints

    @property
    def joint_names(self) -> tuple[str, ...]:
        """Retorna os nomes de todas as juntas na ordem do braço."""
        return tuple(joint.name for joint in self._joints)

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

        pose_names = {name.strip().lower() for name in pose.keys()}
        expected_names = set(self._joints_by_name.keys())

        missing = expected_names - pose_names
        if missing:
            raise ValueError(f"Pose incompleta. Juntas ausentes: {sorted(missing)}")

        extra = pose_names - expected_names
        if extra:
            raise ValueError(f"Pose contém juntas desconhecidas: {sorted(extra)}")

        for name, angle in pose.items():
            joint = self._joints_by_name[name.strip().lower()]
            joint.config.angle_to_position(angle)

    @staticmethod
    def _validate_wait_parameter(parameter_name: str, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{parameter_name} deve ser um número")
        if not isfinite(value):
            raise ValueError(f"{parameter_name} deve ser finito")
        if value <= 0:
            raise ValueError(f"{parameter_name} deve ser maior que zero")

    def command_pose(self, pose: dict[str, float], acc: float | None = None, speed: float | None = None) -> dict[str, int]:
        """Transmite uma pose síncrona para todas as juntas usando SyncWritePosEx."""            
        self.validate_pose(pose)

        target_positions: dict[str, int] = {}
        try:
            self._servo.groupSyncWrite.clearParam()

            for joint in self._joints:
                angle = pose[joint.name]
                target_position = joint.angle_to_position(angle)
                target_positions[joint.name] = target_position

                success = self._servo.SyncWritePosEx(
                    joint.servo_id,
                    target_position,
                    speed if speed else joint.speed,
                    acc if acc else joint.acc,
                )
                if not success:
                    raise RuntimeError(
                        f"Falha ao empacotar SyncWrite para a junta '{joint.name}' (ID {joint.servo_id})"
                    )

            result = self._servo.groupSyncWrite.txPacket()
            validate_result(
                self._servo,
                result,
                0,
                "envio de pose sincronizada (SyncWrite)",
            )
        finally:
            self._servo.groupSyncWrite.clearParam()

        return target_positions

    def move_pose(
        self,
        pose: dict[str, float],
        timeout: float = 8.0,
        poll_interval: float = 0.05,
    ) -> dict[str, MovementStatus]:
        """Transmite a pose e aguarda todas as juntas alcançarem a tolerância com timeout conjunto."""
        self._validate_wait_parameter("timeout", timeout)
        self._validate_wait_parameter("poll_interval", poll_interval)

        target_positions = self.command_pose(pose)
        deadline = monotonic() + timeout

        while True:
            all_within_tolerance = True
            latest_statuses: dict[str, MovementStatus] = {}

            for joint in self._joints:
                target_pos = target_positions[joint.name]
                status = joint.movement_status(target_pos)
                latest_statuses[joint.name] = status

                if not status.within_tolerance:
                    all_within_tolerance = False

            if all_within_tolerance:
                return latest_statuses

            # Verifica se alguma junta parou fora da tolerância
            for joint in self._joints:
                status = latest_statuses[joint.name]
                if not status.within_tolerance and not status.moving:
                    raise RuntimeError(
                        f"Pose falhou: junta '{joint.name}' parou fora do alvo "
                        f"(alvo={status.target_position}, posição={status.current_position}, "
                        f"erro={status.position_error} counts, tolerância={joint.config.tolerance_counts} counts)"
                    )

            remaining_time = deadline - monotonic()
            if remaining_time <= 0:
                unreached = [
                    f"{name} (erro={st.position_error} counts)"
                    for name, st in latest_statuses.items()
                    if not st.within_tolerance
                ]
                raise TimeoutError(
                    f"Timeout após {timeout:.3f}s aguardando pose. Juntas que não alcançaram o alvo: {unreached}"
                )

            sleep(min(poll_interval, remaining_time))

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
