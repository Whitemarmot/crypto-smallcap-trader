"""
Multi-chain EVM network configuration.
Supports Ethereum, BSC, Base, and Arbitrum.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class NetworkConfig:
    """Configuration for an EVM network."""
    chain_id: int
    name: str
    symbol: str
    rpc_url: str
    explorer_url: str
    decimals: int = 18
    is_testnet: bool = False


# Mainnet configurations
NETWORKS: Dict[str, NetworkConfig] = {
    # Ethereum Mainnet
    "ethereum": NetworkConfig(
        chain_id=1,
        name="Ethereum Mainnet",
        symbol="ETH",
        rpc_url="https://eth.llamarpc.com",
        explorer_url="https://etherscan.io",
    ),
    
    # Binance Smart Chain
    "bsc": NetworkConfig(
        chain_id=56,
        name="BNB Smart Chain",
        symbol="BNB",
        rpc_url="https://bsc-dataseed.binance.org",
        explorer_url="https://bscscan.com",
    ),
    
    # Base (Coinbase L2)
    "base": NetworkConfig(
        chain_id=8453,
        name="Base",
        symbol="ETH",
        rpc_url="https://mainnet.base.org",
        explorer_url="https://basescan.org",
    ),
    
    # Arbitrum One
    "arbitrum": NetworkConfig(
        chain_id=42161,
        name="Arbitrum One",
        symbol="ETH",
        rpc_url="https://arb1.arbitrum.io/rpc",
        explorer_url="https://arbiscan.io",
    ),
}

# Testnet configurations
TESTNETS: Dict[str, NetworkConfig] = {
    # Ethereum Sepolia
    "sepolia": NetworkConfig(
        chain_id=11155111,
        name="Sepolia Testnet",
        symbol="ETH",
        rpc_url="https://rpc.sepolia.org",
        explorer_url="https://sepolia.etherscan.io",
        is_testnet=True,
    ),
    
    # BSC Testnet
    "bsc_testnet": NetworkConfig(
        chain_id=97,
        name="BSC Testnet",
        symbol="tBNB",
        rpc_url="https://data-seed-prebsc-1-s1.binance.org:8545",
        explorer_url="https://testnet.bscscan.com",
        is_testnet=True,
    ),
    
    # Base Sepolia
    "base_sepolia": NetworkConfig(
        chain_id=84532,
        name="Base Sepolia",
        symbol="ETH",
        rpc_url="https://sepolia.base.org",
        explorer_url="https://sepolia.basescan.org",
        is_testnet=True,
    ),
    
    # Arbitrum Sepolia
    "arbitrum_sepolia": NetworkConfig(
        chain_id=421614,
        name="Arbitrum Sepolia",
        symbol="ETH",
        rpc_url="https://sepolia-rollup.arbitrum.io/rpc",
        explorer_url="https://sepolia.arbiscan.io",
        is_testnet=True,
    ),
}

# All networks combined
ALL_NETWORKS: Dict[str, NetworkConfig] = {**NETWORKS, **TESTNETS}


def get_network(network_name: str) -> NetworkConfig:
    """
    Get network configuration by name.
    
    Args:
        network_name: Name of the network (e.g., 'ethereum', 'bsc', 'base')
        
    Returns:
        NetworkConfig for the requested network
        
    Raises:
        ValueError: If network is not supported
    """
    network_name = network_name.lower()
    if network_name not in ALL_NETWORKS:
        supported = ", ".join(ALL_NETWORKS.keys())
        raise ValueError(f"Unknown network: {network_name}. Supported: {supported}")
    return ALL_NETWORKS[network_name]


def get_chain_id(network_name: str) -> int:
    """Get chain ID for a network."""
    return get_network(network_name).chain_id


def get_rpc_url(network_name: str, custom_rpc: Optional[str] = None) -> str:
    """
    Get RPC URL for a network.
    
    Args:
        network_name: Name of the network
        custom_rpc: Optional custom RPC URL to use instead of default
        
    Returns:
        RPC URL string
    """
    if custom_rpc:
        return custom_rpc
    return get_network(network_name).rpc_url


def list_networks(include_testnets: bool = False) -> list[str]:
    """List available network names."""
    if include_testnets:
        return list(ALL_NETWORKS.keys())
    return list(NETWORKS.keys())
