"""
Crypto SmallCap Trader - Configuration Management
Export/Import configuration, API keys, etc.
"""

import json
import os
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any
from datetime import datetime


CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'config.json')


@dataclass
class NetworkSettings:
    """Network-specific settings"""
    enabled: bool = True
    rpc_url: Optional[str] = None
    explorer_url: Optional[str] = None


@dataclass 
class APIKeys:
    """API keys configuration"""
    oneinch_api_key: Optional[str] = None
    infura_api_key: Optional[str] = None
    alchemy_api_key: Optional[str] = None
    etherscan_api_key: Optional[str] = None
    coingecko_api_key: Optional[str] = None
    

@dataclass
class TradingSettings:
    """Trading-related settings"""
    max_slippage: float = 1.0
    default_gas_limit: int = 300000
    max_gas_price_gwei: float = 100.0
    min_trade_usd: float = 10.0
    max_trade_usd: float = 10000.0
    auto_approve: bool = False


@dataclass
class AppConfig:
    """Main application configuration"""
    # Networks
    networks: Dict[str, NetworkSettings] = field(default_factory=lambda: {
        'ethereum': NetworkSettings(),
        'bsc': NetworkSettings(),
        'base': NetworkSettings(),
        'arbitrum': NetworkSettings(),
    })
    
    # API Keys
    api_keys: APIKeys = field(default_factory=APIKeys)
    
    # Trading
    trading: TradingSettings = field(default_factory=TradingSettings)
    
    # UI Preferences
    theme: str = 'dark'
    language: str = 'en'
    notifications_enabled: bool = True
    
    # Active network
    active_network: str = 'ethereum'
    
    # Last updated
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {}
        for key, value in asdict(self).items():
            if isinstance(value, dict) and value:
                # Check if dict contains dataclasses
                first_val = list(value.values())[0] if value else None
                if isinstance(first_val, dict):
                    result[key] = value
                else:
                    result[key] = value
            elif hasattr(value, '__dict__'):
                result[key] = asdict(value)
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create config from dictionary"""
        config = cls()
        
        if 'networks' in data:
            config.networks = {
                k: NetworkSettings(**v) if isinstance(v, dict) else v 
                for k, v in data['networks'].items()
            }
        
        if 'api_keys' in data:
            config.api_keys = APIKeys(**data['api_keys'])
        
        if 'trading' in data:
            config.trading = TradingSettings(**data['trading'])
        
        for key in ['theme', 'language', 'notifications_enabled', 'active_network', 'updated_at']:
            if key in data:
                setattr(config, key, data[key])
        
        return config


def load_config(config_path: str = CONFIG_PATH) -> AppConfig:
    """Load configuration from file"""
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            return AppConfig.from_dict(data)
        except Exception as e:
            print(f"Error loading config: {e}")
    return AppConfig()


def save_config(config: AppConfig, config_path: str = CONFIG_PATH):
    """Save configuration to file"""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    config.updated_at = datetime.now().isoformat()
    with open(config_path, 'w') as f:
        json.dump(config.to_dict(), f, indent=2)


def export_config(config: AppConfig, export_path: str, include_api_keys: bool = False):
    """Export configuration to a file"""
    data = config.to_dict()
    
    # Optionally mask API keys
    if not include_api_keys:
        data['api_keys'] = {k: '***' if v else None for k, v in data['api_keys'].items()}
    
    data['exported_at'] = datetime.now().isoformat()
    
    with open(export_path, 'w') as f:
        json.dump(data, f, indent=2)


def import_config(import_path: str, merge: bool = True) -> AppConfig:
    """Import configuration from a file"""
    with open(import_path, 'r') as f:
        data = json.load(f)
    
    # Remove export metadata
    data.pop('exported_at', None)
    
    if merge:
        # Load existing config and merge
        existing = load_config()
        existing_dict = existing.to_dict()
        
        # Only merge non-masked values
        if 'api_keys' in data:
            for key, value in data['api_keys'].items():
                if value and value != '***':
                    existing_dict.setdefault('api_keys', {})[key] = value
            data['api_keys'] = existing_dict.get('api_keys', data['api_keys'])
        
        # Merge other settings
        for key, value in data.items():
            if key != 'api_keys':
                existing_dict[key] = value
        
        return AppConfig.from_dict(existing_dict)
    
    return AppConfig.from_dict(data)


# Default networks info
SUPPORTED_NETWORKS = {
    'ethereum': {
        'name': 'Ethereum Mainnet',
        'chain_id': 1,
        'symbol': 'ETH',
        'icon': '🔷',
        'default_rpc': 'https://eth.llamarpc.com',
        'explorer': 'https://etherscan.io',
    },
    'bsc': {
        'name': 'BNB Smart Chain',
        'chain_id': 56,
        'symbol': 'BNB',
        'icon': '🟡',
        'default_rpc': 'https://bsc-dataseed.binance.org',
        'explorer': 'https://bscscan.com',
    },
    'base': {
        'name': 'Base',
        'chain_id': 8453,
        'symbol': 'ETH',
        'icon': '🔵',
        'default_rpc': 'https://mainnet.base.org',
        'explorer': 'https://basescan.org',
    },
    'arbitrum': {
        'name': 'Arbitrum One',
        'chain_id': 42161,
        'symbol': 'ETH',
        'icon': '🔶',
        'default_rpc': 'https://arb1.arbitrum.io/rpc',
        'explorer': 'https://arbiscan.io',
    },
}
