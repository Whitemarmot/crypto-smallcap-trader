"""
Fetch real balances from blockchain
Supports top 1000+ CoinGecko tokens via Multicall for efficiency
"""
from web3 import Web3
import requests
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import time

# ========== CONFIG ==========

# Cache directory
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
TOKENS_CACHE_FILE = os.path.join(CACHE_DIR, 'coingecko_tokens.json')
CACHE_MAX_AGE_HOURS = 24

# RPC endpoints (publics et gratuits)
RPC_ENDPOINTS = {
    'base': 'https://mainnet.base.org',
    'ethereum': 'https://eth.llamarpc.com',
    'arbitrum': 'https://arb1.arbitrum.io/rpc',
    'bsc': 'https://bsc-dataseed.binance.org',
    'polygon': 'https://polygon-rpc.com',
    'optimism': 'https://mainnet.optimism.io',
}

# CoinGecko platform IDs mapping
NETWORK_TO_PLATFORM = {
    'ethereum': 'ethereum',
    'base': 'base',
    'arbitrum': 'arbitrum-one',
    'bsc': 'binance-smart-chain',
    'polygon': 'polygon-pos',
    'optimism': 'optimistic-ethereum',
}

# Native token symbols
NATIVE_SYMBOLS = {
    'base': 'ETH',
    'ethereum': 'ETH',
    'arbitrum': 'ETH',
    'optimism': 'ETH',
    'bsc': 'BNB',
    'polygon': 'MATIC',
}

# Multicall3 contract (same address on all EVM chains)
MULTICALL3_ADDRESS = '0xcA11bde05977b3631167028862bE2a173976CA11'

# Multicall3 ABI (minimal)
MULTICALL3_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "target", "type": "address"},
                    {"name": "callData", "type": "bytes"}
                ],
                "name": "calls",
                "type": "tuple[]"
            }
        ],
        "name": "aggregate",
        "outputs": [
            {"name": "blockNumber", "type": "uint256"},
            {"name": "returnData", "type": "bytes[]"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# ERC20 ABI minimal
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
    coingecko_id: Optional[str] = None

@dataclass  
class TokenInfo:
    address: str
    symbol: str
    decimals: int
    coingecko_id: str
    name: str

# ========== COINGECKO TOKEN LIST ==========

def fetch_coingecko_tokens(limit: int = 1000) -> Dict[str, List[TokenInfo]]:
    """
    Fetch tokens from CoinGecko with contract addresses
    Single API call approach to avoid rate limits
    Returns dict: network -> list of TokenInfo
    """
    tokens_by_network = {net: [] for net in RPC_ENDPOINTS.keys()}
    
    try:
        # Single API call: /coins/list with platforms
        print("Fetching CoinGecko token list (single request)...")
        
        resp = requests.get(
            'https://api.coingecko.com/api/v3/coins/list',
            params={'include_platform': 'true'},
            timeout=60
        )
        resp.raise_for_status()
        all_coins = resp.json()
        
        print(f"Got {len(all_coins)} coins from CoinGecko")
        
        # Build token list per network (take all tokens with valid addresses)
        for coin in all_coins:
            coin_id = coin.get('id', '')
            symbol = coin.get('symbol', '').upper()
            name = coin.get('name', '')
            platforms = coin.get('platforms', {})
            
            if not symbol or not coin_id:
                continue
            
            for network, platform_id in NETWORK_TO_PLATFORM.items():
                if platform_id in platforms and platforms[platform_id]:
                    address = platforms[platform_id]
                    # Validate address format
                    if address and len(address) == 42 and address.startswith('0x'):
                        try:
                            tokens_by_network[network].append(TokenInfo(
                                address=Web3.to_checksum_address(address),
                                symbol=symbol,
                                decimals=18,  # Default, will be corrected by price lookup
                                coingecko_id=coin_id,
                                name=name
                            ))
                        except Exception:
                            pass  # Invalid address
        
        # Limit per network to avoid too many RPC calls (250 is a good balance)
        MAX_TOKENS_PER_NETWORK = 250
        for network in tokens_by_network:
            if len(tokens_by_network[network]) > MAX_TOKENS_PER_NETWORK:
                tokens_by_network[network] = tokens_by_network[network][:MAX_TOKENS_PER_NETWORK]
        
        print(f"Loaded tokens: {', '.join(f'{k}:{len(v)}' for k, v in tokens_by_network.items())}")
        return tokens_by_network
        
    except Exception as e:
        print(f"Error fetching CoinGecko tokens: {e}")
        return tokens_by_network

def load_tokens_cache() -> Optional[Dict]:
    """Load tokens from cache file"""
    try:
        if os.path.exists(TOKENS_CACHE_FILE):
            with open(TOKENS_CACHE_FILE, 'r') as f:
                data = json.load(f)
            
            # Check if cache is fresh
            cached_at = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
            if datetime.now() - cached_at < timedelta(hours=CACHE_MAX_AGE_HOURS):
                return data
    except Exception as e:
        print(f"Error loading cache: {e}")
    return None

def save_tokens_cache(tokens_by_network: Dict[str, List[TokenInfo]]):
    """Save tokens to cache file"""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        data = {
            'cached_at': datetime.now().isoformat(),
            'tokens': {
                network: [
                    {
                        'address': t.address,
                        'symbol': t.symbol,
                        'decimals': t.decimals,
                        'coingecko_id': t.coingecko_id,
                        'name': t.name
                    }
                    for t in tokens
                ]
                for network, tokens in tokens_by_network.items()
            }
        }
        with open(TOKENS_CACHE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving cache: {e}")

def get_tokens_for_network(network: str) -> List[TokenInfo]:
    """Get token list for a network (from cache or fetch)"""
    cache = load_tokens_cache()
    
    if cache and 'tokens' in cache:
        tokens_data = cache['tokens'].get(network.lower(), [])
        return [
            TokenInfo(
                address=t['address'],
                symbol=t['symbol'],
                decimals=t['decimals'],
                coingecko_id=t['coingecko_id'],
                name=t['name']
            )
            for t in tokens_data
        ]
    
    # Fetch fresh data
    tokens_by_network = fetch_coingecko_tokens(limit=1000)
    save_tokens_cache(tokens_by_network)
    return tokens_by_network.get(network.lower(), [])

# ========== WEB3 HELPERS ==========

def get_web3(network: str) -> Web3:
    """Get Web3 instance for network"""
    rpc = RPC_ENDPOINTS.get(network.lower())
    if not rpc:
        raise ValueError(f"Unknown network: {network}")
    return Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))

def get_native_balance(address: str, network: str) -> TokenBalance:
    """Get native token balance (ETH/BNB/etc)"""
    w3 = get_web3(network)
    
    balance_wei = w3.eth.get_balance(Web3.to_checksum_address(address))
    balance = balance_wei / 10**18
    
    return TokenBalance(
        symbol=NATIVE_SYMBOLS.get(network.lower(), 'ETH'),
        balance=balance,
        balance_raw=balance_wei,
        decimals=18
    )

# ========== MULTICALL BALANCE FETCHING ==========

def get_balances_multicall(address: str, tokens: List[TokenInfo], network: str) -> List[TokenBalance]:
    """
    Fetch multiple token balances in a single RPC call using Multicall3
    """
    if not tokens:
        return []
    
    w3 = get_web3(network)
    user_address = Web3.to_checksum_address(address)
    
    # Create Multicall contract instance
    multicall = w3.eth.contract(
        address=Web3.to_checksum_address(MULTICALL3_ADDRESS),
        abi=MULTICALL3_ABI
    )
    
    # Build balanceOf call data for each token
    # balanceOf(address) selector = 0x70a08231
    balance_of_selector = bytes.fromhex('70a08231')
    
    calls = []
    for token in tokens:
        # Encode balanceOf(user_address)
        call_data = balance_of_selector + bytes.fromhex(user_address[2:].zfill(64))
        calls.append((Web3.to_checksum_address(token.address), call_data))
    
    # Execute multicall in batches (100 calls per batch for reliability)
    BATCH_SIZE = 100
    all_results = []
    
    for i in range(0, len(calls), BATCH_SIZE):
        batch = calls[i:i + BATCH_SIZE]
        try:
            _, return_data = multicall.functions.aggregate(batch).call()
            all_results.extend(return_data)
        except Exception as e:
            print(f"Multicall batch {i//BATCH_SIZE + 1} failed: {e}")
            # Fill with zeros for failed batch
            all_results.extend([b'\x00' * 32] * len(batch))
    
    # Parse results
    balances = []
    for idx, token in enumerate(tokens):
        try:
            if idx < len(all_results) and all_results[idx]:
                balance_raw = int.from_bytes(all_results[idx], 'big')
                if balance_raw > 0:
                    # Use default 18 decimals, will be corrected by price lookup
                    balance = balance_raw / 10**token.decimals
                    balances.append(TokenBalance(
                        symbol=token.symbol,
                        balance=balance,
                        balance_raw=balance_raw,
                        decimals=token.decimals,
                        contract=token.address,
                        coingecko_id=token.coingecko_id
                    ))
        except Exception as e:
            pass  # Skip problematic tokens silently
    
    return balances

def get_token_balance(address: str, token_address: str, network: str) -> Optional[TokenBalance]:
    """Get single ERC20 token balance (fallback method)"""
    try:
        w3 = get_web3(network)
        
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        
        balance_raw = token_contract.functions.balanceOf(
            Web3.to_checksum_address(address)
        ).call()
        
        if balance_raw == 0:
            return None
        
        try:
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
        except:
            symbol = "???"
            decimals = 18
        
        balance = balance_raw / 10**decimals
        
        return TokenBalance(
            symbol=symbol,
            balance=balance,
            balance_raw=balance_raw,
            decimals=decimals,
            contract=token_address
        )
    except Exception as e:
        return None

# ========== POPULAR TOKENS (Fast Mode) ==========

# Top 50 most traded tokens per network for fast scanning
POPULAR_TOKENS = {
    'ethereum': [
        ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'USDC', 6, 'usd-coin'),
        ('0xdAC17F958D2ee523a2206206994597C13D831ec7', 'USDT', 6, 'tether'),
        ('0x6B175474E89094C44Da98b954EedeAC495271d0F', 'DAI', 18, 'dai'),
        ('0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', 'WBTC', 8, 'wrapped-bitcoin'),
        ('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', 'WETH', 18, 'weth'),
        ('0x514910771AF9Ca656af840dff83E8264EcF986CA', 'LINK', 18, 'chainlink'),
        ('0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984', 'UNI', 18, 'uniswap'),
        ('0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9', 'AAVE', 18, 'aave'),
        ('0x6982508145454Ce325dDbE47a25d4ec3d2311933', 'PEPE', 18, 'pepe'),
        ('0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE', 'SHIB', 18, 'shiba-inu'),
    ],
    'base': [
        ('0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', 'USDC', 6, 'usd-coin'),
        ('0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb', 'DAI', 18, 'dai'),
        ('0x4200000000000000000000000000000000000006', 'WETH', 18, 'weth'),
        ('0x532f27101965dd16442E59d40670FaF5eBB142E4', 'BRETT', 18, 'brett'),
        ('0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b', 'VIRTUAL', 18, 'virtual-protocol'),
        ('0x940181a94A35A4569E4529A3CDfB74e38FD98631', 'AERO', 18, 'aerodrome-finance'),
        ('0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22', 'cbETH', 18, 'coinbase-wrapped-staked-eth'),
        ('0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA', 'USDbC', 6, 'usd-coin'),
    ],
    'arbitrum': [
        ('0xaf88d065e77c8cC2239327C5EDb3A432268e5831', 'USDC', 6, 'usd-coin'),
        ('0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9', 'USDT', 6, 'tether'),
        ('0x82aF49447D8a07e3bd95BD0d56f35241523fBab1', 'WETH', 18, 'weth'),
        ('0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f', 'WBTC', 8, 'wrapped-bitcoin'),
        ('0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1', 'DAI', 18, 'dai'),
        ('0x912CE59144191C1204E64559FE8253a0e49E6548', 'ARB', 18, 'arbitrum'),
        ('0xfc5A1A6EB076a2C7aD06eD22C90d7E710E35ad0a', 'GMX', 18, 'gmx'),
    ],
    'bsc': [
        ('0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d', 'USDC', 18, 'usd-coin'),
        ('0x55d398326f99059fF775485246999027B3197955', 'USDT', 18, 'tether'),
        ('0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', 'WBNB', 18, 'wbnb'),
        ('0x2170Ed0880ac9A755fd29B2688956BD959F933F8', 'ETH', 18, 'ethereum'),
        ('0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c', 'BTCB', 18, 'bitcoin-bep2'),
        ('0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82', 'CAKE', 18, 'pancakeswap-token'),
    ],
    'polygon': [
        ('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', 'USDC', 6, 'usd-coin'),
        ('0xc2132D05D31c914a87C6611C10748AEb04B58e8F', 'USDT', 6, 'tether'),
        ('0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270', 'WMATIC', 18, 'wmatic'),
        ('0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619', 'WETH', 18, 'weth'),
        ('0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6', 'WBTC', 8, 'wrapped-bitcoin'),
        ('0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063', 'DAI', 18, 'dai'),
    ],
    'optimism': [
        ('0x7F5c764cBc14f9669B88837ca1490cCa17c31607', 'USDC', 6, 'usd-coin'),
        ('0x94b008aA00579c1307B0EF2c499aD98a8ce58e58', 'USDT', 6, 'tether'),
        ('0x4200000000000000000000000000000000000006', 'WETH', 18, 'weth'),
        ('0x4200000000000000000000000000000000000042', 'OP', 18, 'optimism'),
        ('0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1', 'DAI', 18, 'dai'),
    ],
}

# ========== MAIN BALANCE FUNCTIONS ==========

def get_all_balances(address: str, network: str, fast_mode: bool = True) -> List[TokenBalance]:
    """
    Get native + token balances
    
    Args:
        address: Wallet address
        network: Network name (ethereum, base, etc.)
        fast_mode: If True, only check popular tokens (faster). 
                   If False, check full CoinGecko list (slower but complete)
    """
    balances = []
    
    # 1. Native balance
    try:
        native = get_native_balance(address, network)
        if native.balance > 0:
            balances.append(native)
    except Exception as e:
        print(f"Error fetching native balance: {e}")
    
    # 2. Token balances
    if fast_mode:
        # Fast mode: use hardcoded popular tokens
        popular = POPULAR_TOKENS.get(network.lower(), [])
        if popular:
            tokens = [
                TokenInfo(address=addr, symbol=sym, decimals=dec, coingecko_id=cg_id, name=sym)
                for addr, sym, dec, cg_id in popular
            ]
            try:
                token_balances = get_balances_multicall(address, tokens, network)
                balances.extend(token_balances)
            except Exception as e:
                print(f"Error in fast mode: {e}")
    else:
        # Full mode: use CoinGecko list
        try:
            tokens = get_tokens_for_network(network)
            if tokens:
                print(f"Checking {len(tokens)} tokens on {network}...")
                token_balances = get_balances_multicall(address, tokens, network)
                balances.extend(token_balances)
                print(f"Found {len(token_balances)} tokens with balance")
        except Exception as e:
            print(f"Error fetching token balances: {e}")
    
    return balances

def get_all_balances_full(address: str, network: str) -> List[TokenBalance]:
    """Full scan with CoinGecko top tokens (slower)"""
    return get_all_balances(address, network, fast_mode=False)

# ========== PRICE FUNCTIONS ==========

def get_prices(symbols: List[str], coingecko_ids: List[str] = None) -> Dict[str, float]:
    """Get prices for multiple tokens from CoinGecko"""
    try:
        # Mapping for common symbols
        symbol_to_id = {
            'ETH': 'ethereum',
            'WETH': 'ethereum',
            'BNB': 'binancecoin',
            'WBNB': 'binancecoin',
            'MATIC': 'matic-network',
            'WMATIC': 'matic-network',
            'USDC': 'usd-coin',
            'USDT': 'tether',
            'DAI': 'dai',
            'PEPE': 'pepe',
            'SHIB': 'shiba-inu',
            'DOGE': 'dogecoin',
            'LINK': 'chainlink',
            'UNI': 'uniswap',
            'AAVE': 'aave',
        }
        
        # Build ID list
        ids_to_fetch = set()
        symbol_to_coingecko = {}
        
        for i, symbol in enumerate(symbols):
            if coingecko_ids and i < len(coingecko_ids) and coingecko_ids[i]:
                cg_id = coingecko_ids[i]
            else:
                cg_id = symbol_to_id.get(symbol.upper(), symbol.lower())
            
            ids_to_fetch.add(cg_id)
            symbol_to_coingecko[symbol] = cg_id
        
        if not ids_to_fetch:
            return {}
        
        ids_str = ','.join(ids_to_fetch)
        
        resp = requests.get(
            'https://api.coingecko.com/api/v3/simple/price',
            params={'ids': ids_str, 'vs_currencies': 'usd'},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        prices = {}
        for symbol in symbols:
            cg_id = symbol_to_coingecko.get(symbol)
            if cg_id and cg_id in data and 'usd' in data[cg_id]:
                prices[symbol] = data[cg_id]['usd']
        
        return prices
        
    except Exception as e:
        print(f"Error fetching prices: {e}")
        return {}

def get_prices_for_balances(balances: List[TokenBalance]) -> Dict[str, float]:
    """Get prices for a list of token balances"""
    symbols = [b.symbol for b in balances]
    coingecko_ids = [b.coingecko_id for b in balances]
    return get_prices(symbols, coingecko_ids)

# ========== UTILITY ==========

def refresh_token_cache():
    """Force refresh the CoinGecko token cache"""
    print("Refreshing CoinGecko token cache...")
    tokens = fetch_coingecko_tokens(limit=1000)
    save_tokens_cache(tokens)
    total = sum(len(v) for v in tokens.values())
    print(f"Cached {total} tokens across {len(tokens)} networks")
    return tokens
