"""
Strategy Engine - Stratégies disponibles
"""
from .dca import DCAStrategy
from .grid import GridStrategy
from .momentum import MomentumStrategy

__all__ = [
    "DCAStrategy",
    "GridStrategy", 
    "MomentumStrategy",
]

# Registry des stratégies disponibles
STRATEGY_REGISTRY = {
    "dca": DCAStrategy,
    "grid": GridStrategy,
    "momentum": MomentumStrategy,
}


def get_strategy_class(strategy_type: str):
    """
    Retourne la classe de stratégie correspondante
    
    Args:
        strategy_type: Type de stratégie ("dca", "grid", "momentum")
    
    Returns:
        Classe de stratégie
    
    Raises:
        ValueError: Si le type n'existe pas
    """
    if strategy_type not in STRATEGY_REGISTRY:
        available = ", ".join(STRATEGY_REGISTRY.keys())
        raise ValueError(f"Unknown strategy type: {strategy_type}. Available: {available}")
    return STRATEGY_REGISTRY[strategy_type]


def create_strategy(strategy_type: str, config):
    """
    Factory pour créer une stratégie
    
    Args:
        strategy_type: Type de stratégie
        config: StrategyConfig
    
    Returns:
        Instance de stratégie
    """
    strategy_class = get_strategy_class(strategy_type)
    return strategy_class(config)
