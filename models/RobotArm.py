from collections.abc import Sequence
from typing import Any

from models.Joint import Joint


class RobotArm:
    def __init__(self, joints: Sequence[Joint]) -> None:
        if not joints:
            raise ValueError("O braço robótico deve conter ao menos uma junta.")

        self._validate_unique_joints(joints)
        self._joints: tuple[Joint, ...] = tuple(joints)
        self._joints_by_name: dict[str, Joint] = {
            joint.name.lower(): joint for joint in self._joints
        }

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
            # Valida limites através da JointConfig
            joint.config.angle_to_position(angle)

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
