"""Carregamento explícito de um arquivo cinemático; não inicializa perfis/hardware."""

from pathlib import Path
from typing import Any

import yaml

from src.application.kinematics import DHJoint, KinematicConfig


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """SafeLoader que também rejeita sobrescritas silenciosas de campos."""

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            seen: set[str] = set()
            for key_node, _ in node.value:
                if key_node.tag != "tag:yaml.org,2002:str":
                    raise ValueError("Chaves YAML devem ser strings; merges não são suportados")
                key = self.construct_object(key_node, deep=deep)
                if key in seen:
                    raise ValueError(f"Chave YAML duplicada: {key}")
                seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _fields(value: Any, expected: set[str], location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} deve ser um mapeamento YAML")
    missing = expected - value.keys()
    unexpected = value.keys() - expected
    if missing or unexpected:
        raise ValueError(
            f"{location}: campos ausentes={sorted(missing)}; "
            f"campos desconhecidos={sorted(unexpected)}"
        )
    return value


def load_kinematic_config(path: str | Path) -> KinematicConfig:
    """Lê standard_dh/mm/deg e rejeita dados pendentes, inválidos ou ambíguos.

    O caminho é fornecido pelo chamador; não carrega profile.yml nem robot_config.
    FileNotFoundError/OSError são preservados. Erros de conteúdo incluem o caminho.
    """
    source = Path(path)
    with source.open(encoding="utf-8") as stream:
        try:
            data = yaml.load(stream, Loader=_UniqueKeySafeLoader)
            root = _fields(
                data,
                {"convention", "units", "base_frame", "end_frame", "partial", "chain"},
                "configuração",
            )
            units = _fields(root["units"], {"distance", "angle"}, "units")
            if not isinstance(root["chain"], list):
                raise ValueError("chain deve ser uma lista ordenada")
            chain = tuple(
                DHJoint(**_fields(
                    link,
                    {"joint", "theta_offset_deg", "d_mm", "a_mm", "alpha_deg"},
                    f"chain[{index}]",
                ))
                for index, link in enumerate(root["chain"])
            )
            return KinematicConfig(
                convention=root["convention"],
                distance_unit=units["distance"],
                angle_unit=units["angle"],
                base_frame=root["base_frame"],
                end_frame=root["end_frame"],
                partial=root["partial"],
                chain=chain,
            )
        except (yaml.YAMLError, TypeError, ValueError) as exc:
            raise ValueError(f"Configuração cinemática inválida em {source}: {exc}") from exc
