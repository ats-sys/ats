from dataclasses import dataclass


@dataclass(frozen=True)
class AssetBalance:
    """
    Holds the state of a single asset.
    Note: This class is immutable, hence thread safe in python
    """
    symbol: str  # Asset symbol such as BTC
    free: float  # Amount of assets used for trading
    holding: float  # Amount of assets temporarily held due to reasons like PENDING orders
    frozen: float = 0.0  # Amount of frozen assets. Reasons could be security reasons, violations etc.
