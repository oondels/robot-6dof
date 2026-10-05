"""Cinemática direta DH clássica, sem I/O ou dependências de hardware."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import cos, isfinite, radians, sin


# Matrizes pequenas e imutáveis. As funções deste módulo produzem apenas 4x4/3x3.
Matrix = tuple[tuple[float, ...], ...]
IDENTITY: Matrix = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)


def _finite_number(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} deve ser um número")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} deve ser representável como float finito") from exc
    if not isfinite(number):
        raise ValueError(f"{name} deve ser finito")
    return number


def _validate_name(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} deve ser uma string")
    if not value or value != value.strip():
        raise ValueError(f"{name} deve ser não vazio e sem espaços nas extremidades")


@dataclass(frozen=True, slots=True)
class DHJoint:
    """Geometria de uma junta rotativa; theta = q físico + offset, em graus."""

    joint: str
    theta_offset_deg: float
    d_mm: float
    a_mm: float
    alpha_deg: float

    def __post_init__(self) -> None:
        _validate_name("joint", self.joint)
        for name in ("theta_offset_deg", "d_mm", "a_mm", "alpha_deg"):
            object.__setattr__(self, name, _finite_number(name, getattr(self, name)))


@dataclass(frozen=True, slots=True)
class KinematicConfig:
    """Cadeia ordenada entre base_frame e end_frame, sem calibração de encoder.

    partial indica cobertura parcial do robô, não validação física nem segurança.
    end_frame é o último frame DH; não implica um TCP conhecido.
    """

    convention: str
    distance_unit: str
    angle_unit: str
    base_frame: str
    end_frame: str
    partial: bool
    chain: tuple[DHJoint, ...]

    def __post_init__(self) -> None:
        if self.convention != "standard_dh":
            raise ValueError("Convenção não suportada: use standard_dh")
        if self.distance_unit != "mm" or self.angle_unit != "deg":
            raise ValueError("Unidades não suportadas: use distância mm e ângulo deg")
        _validate_name("base_frame", self.base_frame)
        _validate_name("end_frame", self.end_frame)
        if self.base_frame == self.end_frame:
            raise ValueError("base_frame e end_frame devem ser diferentes")
        if type(self.partial) is not bool:
            raise TypeError("partial deve ser booleano")
        if isinstance(self.chain, (str, bytes)) or not isinstance(self.chain, Sequence):
            raise TypeError("chain deve ser uma sequência de DHJoint")
        chain = tuple(self.chain)
        if not chain:
            raise ValueError("chain não pode ser vazia")
        if not all(isinstance(link, DHJoint) for link in chain):
            raise TypeError("chain deve conter somente DHJoint")
        names = [link.joint for link in chain]
        if len(set(names)) != len(names):
            raise ValueError("chain contém nomes de juntas duplicados")
        object.__setattr__(self, "chain", chain)


@dataclass(frozen=True, slots=True)
class ForwardKinematicsResult:
    """T_base_end e T_base_i; coordenadas expressas no frame base, em mm.

    accumulated_transforms[i] corresponde a joint_names[i], na ordem da cadeia.
    As matrizes atuam sobre vetores-coluna: p_base = T_base_end @ p_end.
    """

    transform: Matrix
    accumulated_transforms: tuple[Matrix, ...]
    joint_names: tuple[str, ...]
    base_frame: str
    end_frame: str
    partial: bool

    @property
    def position_mm(self) -> tuple[float, float, float]:
        """Posição (x, y, z) da origem do frame final."""
        return (self.transform[0][3], self.transform[1][3], self.transform[2][3])

    @property
    def rotation(self) -> Matrix:
        """Orientação 3x3 do frame final em relação à base."""
        return tuple(row[:3] for row in self.transform[:3])


def dh_transform(
    *, theta_deg: float, alpha_deg: float, a_mm: float, d_mm: float
) -> Matrix:
    """RotZ(theta) · TransZ(d) · TransX(a) · RotX(alpha), DH clássico."""
    theta = radians(_finite_number("theta_deg", theta_deg))
    alpha = radians(_finite_number("alpha_deg", alpha_deg))
    a = _finite_number("a_mm", a_mm)
    d = _finite_number("d_mm", d_mm)
    ct, st = cos(theta), sin(theta)
    ca, sa = cos(alpha), sin(alpha)
    return (
        (ct, -st * ca, st * sa, a * ct),
        (st, ct * ca, -ct * sa, a * st),
        (0.0, sa, ca, d),
        (0.0, 0.0, 0.0, 1.0),
    )


def _multiply(left: Matrix, right: Matrix) -> Matrix:
    result = tuple(
        tuple(sum(left[i][k] * right[k][j] for k in range(4)) for j in range(4))
        for i in range(4)
    )
    if not all(isfinite(value) for row in result for value in row):
        raise ValueError("Composição DH excedeu a precisão numérica de float")
    return result


def forward_kinematics(
    config: KinematicConfig, joint_angles: Mapping[str, float]
) -> ForwardKinematicsResult:
    """Calcula a cadeia a partir de ângulos físicos em graus, por nome exato.

    Exige exatamente as juntas da cadeia. Não lê encoder, aplica direction,
    limita ângulos ou certifica que a pose seja segura/alcançável fisicamente.
    """
    if not isinstance(config, KinematicConfig):
        raise TypeError("config deve ser KinematicConfig")
    if not isinstance(joint_angles, Mapping):
        raise TypeError("joint_angles deve ser um mapeamento por nome")
    for name in joint_angles:
        _validate_name("nome da junta", name)
    names = tuple(link.joint for link in config.chain)
    missing = set(names) - joint_angles.keys()
    unexpected = joint_angles.keys() - set(names)
    if missing or unexpected:
        raise ValueError(
            f"Ângulos incompatíveis com a cadeia: juntas ausentes={sorted(missing)}; "
            f"juntas inesperadas={sorted(unexpected)}"
        )
    angles = {name: _finite_number(name, joint_angles[name]) for name in names}
    accumulated: list[Matrix] = []
    transform = IDENTITY
    for link in config.chain:
        local = dh_transform(
            theta_deg=angles[link.joint] + link.theta_offset_deg,
            alpha_deg=link.alpha_deg,
            a_mm=link.a_mm,
            d_mm=link.d_mm,
        )
        transform = _multiply(transform, local)
        accumulated.append(transform)
    return ForwardKinematicsResult(
        transform=transform,
        accumulated_transforms=tuple(accumulated),
        joint_names=names,
        base_frame=config.base_frame,
        end_frame=config.end_frame,
        partial=config.partial,
    )
