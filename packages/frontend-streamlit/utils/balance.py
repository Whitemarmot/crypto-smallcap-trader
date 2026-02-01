"""
Fetch real balances from blockchain
"""
from web3 import Web3
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass

# RPC endpoints (publics et gratuits)
RPC_ENDPOINTS = {
    'base': 'https://mainnet.base.org',
    'ethereum': 'https://eth.llamarpc.com',
    'arbitrum': 'https://arb1.arbitrum.io/rpc',
    'bsc': 'https://bsc-dataseed.binance.org',
    'polygon': 'https://polygon-rpc.com',
    'optimism': 'https://mainnet.optimism.io',
}

# Tokens populaires par réseau (address -> symbol, decimals)
POPULAR_TOKENS = {
    'base': {
        '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913': ('USDC', 6),
        '0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb': ('DAI', 18),
        '0x4200000000000000000000000000000000000006': ('WETH', 18),
        '0x532f27101965dd16442E59d40670FaF5eBB142E4': ('BRETT', 18),
        '0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b': ('VIRTUAL', 18),
    },
    'ethereum': {
        '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48': ('USDC', 6),
        '0xdAC17F958D2ee523a2206206994597C13D831ec7': ('USDT', 6),
        '0x6982508145454Ce325dDbE47a25d4ec3d2311933': ('PEPE', 18),
    },
    'arbitrum': {
        '0xaf88d065e77c8cC2239327C5EDb3A432268e5831': ('USDC', 6),
        '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9': ('USDT', 6),
    },
    'bsc': {
        '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d': ('USDC', 18),
        '0x55d398326f99059fF775485246999027B3197955': ('USDT', 18),
    },
}

# ERC20 ABI minimal pour balanceOf
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]

@dataclass
class TokenBalance:
    symbol: str
    balance: float
    balance_raw: int
    decimals: int
    contract: Optional[str] = None
    usd_value: Optional[float] = None

def get_web3(network: str) -> Web3:
    """Get Web3 instance for network"""
    rpc = RPC_ENDPOINTS.get(network.lower())
    if not rpc:
        raise ValueError(f"Unknown network: {network}")
    return Web3(Web3.HTTPProvider(rpc))

def get_native_balance(address: str, network: str) -> TokenBalance:
    """Get native token balance (ETH/BNB/etc)"""
    w3 = get_web3(network)
    
    native_symbols = {
        'base': 'ETH',
        'ethereum': 'ETH',
        'arbitrum': 'ETH',
        'optimism': 'ETH',
        'bsc': 'BNB',
        'polygon': 'MATIC',
    }
    
    balance_wei = w3.eth.get_balance(Web3.to_checksum_address(address))
    balance = balance_wei / 10**18
    
    return TokenBalance(
        symbol=native_symbols.get(network.lower(), 'ETH'),
        balance=balance,
        balance_raw=balance_wei,
        decimals=18
    )

def get_token_balance(address: str, token_address: str, network: str) -> Optional[TokenBalance]:
    """Get ERC20 token balance"""
    try:
        w3 = get_web3(network)
        
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        
        balance_raw = token_contract.functions.balanceOf(
            Web3.to_checksum_address(address)
        ).call()
        
        # Get token info from cache or contract
        tokens = POPULAR_TOKENS.get(network.lower(), {})
        if token_address in tokens:
            symbol, decimals = tokens[token_address]
        else:
            try:
                symbol = token_contract.functions.symbol().call()
                decimals = token_contract.functions.decimals().call()
            except:
                return None
        
        balance = balance_raw / 10**decimals
        
        return TokenBalance(
            symbol=symbol,
            balance=balance,
            balance_raw=balance_raw,
            decimals=decimals,
            contract=token_address
        )
    except Exception as e:
        print(f"Error fetching token {token_address}: {e}")
        return None

def get_all_balances(address: str, network: str) -> List[TokenBalance]:
    """Get native + popular token balances"""
    balances = []
    
    # Native balance
    try:
        native = get_native_balance(address, network)
        if native.balance > 0:
            balances.append(native)
    except Exception as e:
        print(f"Error fetching native balance: {e}")
    
    # Token balances
    tokens = POPULAR_TOKENS.get(network.lower(), {})
    for token_address in tokens:
        token_bal = get_token_balance(address, token_address, network)
        if token_bal and token_bal.balance > 0:
            balances.append(token_bal)
    
    return balances

def get_eth_price() -> float:
    """Get ETH price in USD from CoinGecko"""
    try:
        resp = requests.get(
            'https://api.coingecko.com/api/v3/simple/price',
            params={'ids': 'ethereum', 'vs_currencies': 'usd'},
            timeout=5
        )
        return resp.json()['ethereum']['usd']
    except:
        return 0

def get_prices(symbols: List[str]) -> Dict[str, float]:
    """Get prices for multiple tokens"""
    try:
        # Map symbols to CoinGecko IDs
        symbol_to_id = {
            'ETH': 'ethereum',
            'BNB': 'binancecoin',
            'MATIC': 'matic-network',
            'USDC': 'usd-coin',
            'USDT': 'tether',
            'DAI': 'dai',
            'WETH': 'ethereum',
            'PEPE': 'pepe',
            'BRETT': 'brett',
            'VIRTUAL': 'virtual-protocol',
        }
        
        ids = [symbol_to_id.get(s.upper(), s.lower()) for s in symbols]
        ids_str = ','.join(set(ids))
        
        resp = requests.get(
            'https://api.coingecko.com/api/v3/simple/price',
            params={'ids': ids_str, 'vs_currencies': 'usd'},
            timeout=5
        )
        data = resp.json()
        
        prices = {}
        for symbol in symbols:
            coin_id = symbol_to_id.get(symbol.upper(), symbol.lower())
            if coin_id in data:
                prices[symbol] = data[coin_id]['usd']
        
        return prices
    except Exception as e:
        print(f"Error fetching prices: {e}")
        return {}
