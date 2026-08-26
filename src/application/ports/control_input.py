
from dataclasses import dataclass, field
from typing import Mapping
from abc import ABC, abstractmethod

@dataclass
class ControlState:
    """
    Snapshot de entrada do contole operador
    em um determinado instante de tempo.
    """
    
    axes: Mapping[str, float] = field(default_factory=dict)
    buttons_pressed: frozenset[str] = field(default_factory=frozenset)
    buttons_held: frozenset[str] = field(default_factory=frozenset)
    buttons_released: frozenset[str] = field(default_factory=frozenset)
    
    timestamp: float = 0.0
    delta_time: float = 0.0
    
    movement_enabled: bool = False
    emergency_stop: bool = False

class ControlInput(ABC):
    """
    Contrato para qualquer dispositivo que for controlar o robô
    """
    
    @abstractmethod
    def open(self) -> None:
        """Abre a conexão com o dispositivo de controle"""
        pass

    @abstractmethod
    def read(self) -> ControlState:
        """Lê o estado atual do dispositivo de controle"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Verifica se o dispositivo de controle está disponível"""
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reseta o estado do dispositivo de controle"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Fecha a conexão com o dispositivo de controle"""
        pass