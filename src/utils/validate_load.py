LOAD_DIRECTION_BIT = 1 << 10
LOAD_MAGNITUDE_MASK = LOAD_DIRECTION_BIT - 1

BASE_LOAD_AT_REST = 36.31
LOAD_PER_DEGREE_SECOND = 4.10

MINIMUM_LOAD_EXCESS = 100.0
MAXIMUM_CONTACT_VELOCITY_DEG_S = 5.0
MINIMUM_CONTACT_ANGLE_ERROR_DEG = 5.0
MINIMUM_CONTACT_CURRENT_A = 0.10


def validate_load(
    raw_load: int,
    measured_velocity_deg_s: float,
    angle_error_deg: float,
    current_a: float,
) -> bool:
    """Indica se o load atual é compatível com contato ou bloqueio mecânico.

    Os limites foram obtidos na calibração do servo Feetech STS3215 ID 6,
    usando speed 700, aceleração 30 e fechamento pelo gatilho L2. A função
    avalia uma amostra; o controle deve exigir amostras consecutivas antes de
    alterar o movimento.
    """
    load_magnitude = raw_load & LOAD_MAGNITUDE_MASK
    absolute_velocity = abs(measured_velocity_deg_s)
    absolute_angle_error = abs(angle_error_deg)
    absolute_current = abs(current_a)

    expected_movement_load = (
        BASE_LOAD_AT_REST
        + LOAD_PER_DEGREE_SECOND * absolute_velocity
    )
    load_excess = load_magnitude - expected_movement_load

    load_is_above_movement = load_excess >= MINIMUM_LOAD_EXCESS
    servo_is_slow = absolute_velocity <= MAXIMUM_CONTACT_VELOCITY_DEG_S
    position_is_blocked = (
        absolute_angle_error >= MINIMUM_CONTACT_ANGLE_ERROR_DEG
    )
    current_indicates_effort = absolute_current >= MINIMUM_CONTACT_CURRENT_A

    return (
        load_is_above_movement
        and servo_is_slow
        and position_is_blocked
        and current_indicates_effort
    )
