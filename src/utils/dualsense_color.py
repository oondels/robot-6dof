from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DualSenseColorConfig:
    """Configuração RGB da barra de luz do controle DualSense."""

    red: int
    green: int
    blue: int

    def __post_init__(self) -> None:
        for channel_name, channel_value in (
            ("red", self.red),
            ("green", self.green),
            ("blue", self.blue),
        ):
            if type(channel_value) is not int:
                raise TypeError(f"{channel_name} deve ser inteiro")

            if not 0 <= channel_value <= 255:
                raise ValueError(
                    f"{channel_name} deve estar entre 0 e 255"
                )


# Movimento bloqueado ou controle recém-conectado.
MOVEMENT_DISABLED_COLOR = DualSenseColorConfig(
    red=255,
    green=0,
    blue=0,
)

# Movimento liberado pelo botão PS.
MOVEMENT_ENABLED_COLOR = DualSenseColorConfig(
    red=0,
    green=255,
    blue=0,
)

# Controle sem interação durante o intervalo de inatividade.
CONTROLLER_IDLE_COLOR = DualSenseColorConfig(
    red=255,
    green=80,
    blue=0,
)

DEFAULT_DUALSENSE_COLOR = MOVEMENT_DISABLED_COLOR


def color_for_controller_state(
    movement_enabled: bool,
    controller_is_idle: bool,
) -> DualSenseColorConfig:
    """Retorna a cor correspondente ao estado operacional do controle."""
    if controller_is_idle:
        return CONTROLLER_IDLE_COLOR

    if movement_enabled:
        return MOVEMENT_ENABLED_COLOR

    return MOVEMENT_DISABLED_COLOR
