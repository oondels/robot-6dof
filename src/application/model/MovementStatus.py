from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class MovementStatus:
    target_position: int
    current_position: int
    position_error: int
    moving: bool
    within_tolerance: bool