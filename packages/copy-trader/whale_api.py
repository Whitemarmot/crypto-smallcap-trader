"""
Whale API - High-level API for whale tracking with caching.
Provides easy-to-use functions for getting whale transactions and portfolio analysis.
"""
import os
import json
import time
import hashlib
import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CACHE SYSTEM
# ============================================================================

class SimpleCache:
    """Simple file-based cache for API responses."""
    
    def __init__(self, cache_dir: str = None, ttl_seconds: int = 300):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), '.cache')
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> str:
        """Generate cache file path from key."""
        hashed = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{hashed}.json")
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if exists and not expired."""
        path = self._get_cache_path(key)
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            if time.time() - data['timestamp'] > self.ttl_seconds:
                os.remove(path)
                return None
            
            return data['value']
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    def set(self, key: str, value: Any):
        """Store value in cache."""
        path = self._get_cache_path(key)
        try:
            with open(path, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'value': value
                }, f)
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    def clear(self):
        """Clear all cache files."""
        for file in os.listdir(self.cache_dir):
            if file.endswith('.json'):
                os.remove(os.path.join(self.cache_dir, file))


# Global cache instance
_cache = SimpleCache(ttl_seconds=300)  # 5 min cache


# ============================================================================
# KNOWN WHALES DATABASE
# ============================================================================

KNOWN_WHALES_ETHEREUM = {
    # Major Exchanges
    "0x28c6c06298d514db089934071355e5743bf21d60": {
        "name": "Binance Hot Wallet",
        "type": "exchange",
        "importance": "high",
        "description": "Main Binance deposit/withdrawal wallet"
    },
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": {
        "name": "Binance Cold Wallet",
        "type": "exchange",
        "importance": "high"
    },
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": {
        "name": "Coinbase Hot Wallet",
        "type": "exchange",
        "importance": "high"
    },
    "0x503828976d22510aad0201ac7ec88293211d23da": {
        "name": "Coinbase Cold Wallet",
        "type": "exchange",
        "importance": "high"
    },
    
    # Market Makers & Trading Firms
    "0x0716a17fbaee714f1e6ab0f9d59edbc5f09815c0": {
        "name": "Jump Trading",
        "type": "market_maker",
        "importance": "high",
        "description": "Major crypto market maker"
    },
    "0xf584f8728b874a6a5c7a8d4d387c9aae9172d621": {
        "name": "Wintermute",
        "type": "market_maker",
        "importance": "high",
        "description": "Major algorithmic trading firm"
    },
    "0x5041ed759dd4afc3a72b8192c143f72f4724081a": {
        "name": "GSR Markets",
        "type": "market_maker",
        "importance": "medium"
    },
    "0x7a91f950b6925efc5c41c19e0c7c9d91a3a59d2f": {
        "name": "Alameda Research",
        "type": "market_maker",
        "importance": "low",
        "description": "Defunct but still monitored"
    },
    
    # Smart Money / Famous Traders
    "0xd8da6bf26964af9d7eed9e03e53415d37aa96045": {
        "name": "vitalik.eth",
        "type": "smart_money",
        "importance": "high",
        "description": "Vitalik Buterin"
    },
    "0xab5801a7d398351b8be11c439e05c5b3259aec9b": {
        "name": "Vitalik Cold Wallet",
        "type": "smart_money",
        "importance": "medium"
    },
    
    # DeFi Whales
    "0x1b3cb81e51011b549d78bf720b0d924ac763a7c2": {
        "name": "Aave Whale 1",
        "type": "defi_whale",
        "importance": "medium"
    },
    "0x7a16ff8270133f063aab6c9977183d9e72835428": {
        "name": "Compound Whale",
        "type": "defi_whale",
        "importance": "medium"
    },
    
    # NFT Whales
    "0xce90a7949bb78892f159f428d0dc23a8e3584d75": {
        "name": "Pranksy",
        "type": "nft_whale",
        "importance": "medium",
        "description": "Famous NFT collector"
    },
}

KNOWN_WHALES_BASE = {
    # Base-specific whales
    "0x3304e22ddaa22bcdc5fca2269b418046ae7b566a": {
        "name": "Base Foundation",
        "type": "foundation",
        "importance": "high",
        "description": "Base ecosystem treasury"
    },
    "0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22": {
        "name": "Base Bridge",
        "type": "bridge",
        "importance": "high"
    },
    "0x4200000000000000000000000000000000000006": {
        "name": "WETH (Base)",
        "type": "contract",
        "importance": "medium"
    },
    "0x4e59b44847b379578588920ca78fbf26c0b4956c": {
        "name": "Create2 Deployer",
        "type": "contract",
        "importance": "low"
    },
    
    # DeFi on Base
    "0xd34ea7278e6bd48defe656bbe263aef11101469c": {
        "name": "Aerodrome Finance",
        "type": "defi",
        "importance": "high",
        "description": "Major Base DEX"
    },
    
    # Known active traders on Base (from on-chain analysis)
    "0x6fcd8d0c80d3c27f11d88dc2a43d7b27ca8d7d46": {
        "name": "Base Whale #1",
        "type": "whale",
        "importance": "medium"
    },
    "0x8b6b1e00c71d2c9ed1a8a3c4e9f4f1a3e7d6c5b4": {
        "name": "Base DeFi Whale",
        "type": "defi_whale",
        "importance": "medium"
    },
}

# Combined list
KNOWN_WHALES = {
    "ethereum": KNOWN_WHALES_ETHEREUM,
    "base": KNOWN_WHALES_BASE,
}


# ============================================================================
# API WRAPPER WITH RATE LIMITING
# ============================================================================

class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls_per_second: float = 5.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
    
    async def wait(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_call = time.time()


class EtherscanAPI:
    """Etherscan/Basescan API wrapper with rate limiting and caching."""
    
    BASE_URLS = {
        "ethereum": "https://api.etherscan.io/api",
        "base": "https://api.basescan.org/api",
        "bsc": "https://api.bscscan.com/api",
        "arbitrum": "https://api.arbiscan.io/api",
        "polygon": "https://api.polygonscan.com/api",
    }
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('ETHERSCAN_API_KEY', '')
        self.rate_limiter = RateLimiter(calls_per_second=4.5)  # Stay under 5/sec
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _request(
        self, 
        network: str, 
        params: Dict[str, Any],
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Make an API request with rate limiting and caching."""
        
        base_url = self.BASE_URLS.get(network, self.BASE_URLS["ethereum"])
        params["apikey"] = self.api_key
        
        # Check cache
        cache_key = f"{network}:{json.dumps(params, sort_keys=True)}"
        if use_cache:
            cached = _cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {cache_key[:50]}...")
                return cached
        
        # Rate limit
        await self.rate_limiter.wait()
        
        # Make request
        session = await self._get_session()
        try:
            async with session.get(base_url, params=params) as resp:
                data = await resp.json()
                
                if data.get("status") == "1":
                    result = data.get("result", [])
                    if use_cache:
                        _cache.set(cache_key, result)
                    return result
                else:
                    logger.warning(f"API error: {data.get('message')}")
                    return []
        except Exception as e:
            logger.error(f"Request error: {e}")
            return []
    
    async def get_transactions(
        self,
        address: str,
        network: str = "ethereum",
        limit: int = 50,
        start_block: int = 0
    ) -> List[Dict[str, Any]]:
        """Get normal (ETH) transactions for an address."""
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": 99999999,
            "page": 1,
            "offset": min(limit, 10000),
            "sort": "desc"
        }
        return await self._request(network, params)
    
    async def get_token_transfers(
        self,
        address: str,
        network: str = "ethereum",
        limit: int = 50,
        contract_address: str = None
    ) -> List[Dict[str, Any]]:
        """Get ERC-20 token transfers for an address."""
        params = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "page": 1,
            "offset": min(limit, 10000),
            "sort": "desc"
        }
        if contract_address:
            params["contractaddress"] = contract_address
        return await self._request(network, params)
    
    async def get_token_balance(
        self,
        address: str,
        contract_address: str,
        network: str = "ethereum"
    ) -> int:
        """Get ERC-20 token balance for an address."""
        params = {
            "module": "account",
            "action": "tokenbalance",
            "address": address,
            "contractaddress": contract_address,
            "tag": "latest"
        }
        result = await self._request(network, params)
        return int(result) if result else 0
    
    async def get_eth_balance(
        self,
        address: str,
        network: str = "ethereum"
    ) -> float:
        """Get native token (ETH/BNB) balance."""
        params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest"
        }
        result = await self._request(network, params)
        return float(result) / 1e18 if result else 0.0


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class WhaleTransaction:
    """Formatted whale transaction."""
    hash: str
    from_address: str
    to_address: str
    value: float
    value_usd: Optional[float]
    token_symbol: str
    token_address: Optional[str]
    timestamp: datetime
    block_number: int
    gas_used: int
    gas_price_gwei: float
    is_swap: bool
    swap_direction: Optional[str]  # "buy" or "sell"
    method_name: Optional[str]
    network: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class TokenHolding:
    """Token holding in a portfolio."""
    token_address: str
    symbol: str
    name: str
    balance: float
    decimals: int
    value_usd: Optional[float] = None
    price_usd: Optional[float] = None
    percentage: float = 0.0


@dataclass
class WhalePortfolio:
    """Whale portfolio analysis."""
    address: str
    name: Optional[str]
    network: str
    native_balance: float
    native_balance_usd: Optional[float]
    holdings: List[TokenHolding]
    total_value_usd: Optional[float]
    last_activity: Optional[datetime]
    transaction_count: int
    analyzed_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'address': self.address,
            'name': self.name,
            'network': self.network,
            'native_balance': self.native_balance,
            'native_balance_usd': self.native_balance_usd,
            'holdings': [asdict(h) for h in self.holdings],
            'total_value_usd': self.total_value_usd,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'transaction_count': self.transaction_count,
            'analyzed_at': self.analyzed_at.isoformat()
        }


@dataclass
class WhaleAlert:
    """Alert when a whale makes a significant trade."""
    whale_address: str
    whale_name: Optional[str]
    alert_type: str  # "buy", "sell", "large_transfer"
    token_symbol: str
    token_address: Optional[str]
    amount: float
    amount_usd: Optional[float]
    tx_hash: str
    network: str
    timestamp: datetime
    importance: str = "medium"  # "low", "medium", "high"
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }


# ============================================================================
# MAIN API FUNCTIONS
# ============================================================================

# Global API instance
_api: Optional[EtherscanAPI] = None

def get_api(api_key: str = None) -> EtherscanAPI:
    """Get or create the API instance."""
    global _api
    if _api is None:
        _api = EtherscanAPI(api_key)
    return _api


# Known swap method signatures
SWAP_METHODS = {
    "0x7ff36ab5": "swapExactETHForTokens",
    "0x18cbafe5": "swapExactTokensForETH",
    "0x38ed1739": "swapExactTokensForTokens",
    "0xfb3bdb41": "swapETHForExactTokens",
    "0x5c11d795": "swapExactTokensForTokensSupportingFeeOnTransferTokens",
    "0x791ac947": "swapExactTokensForETHSupportingFeeOnTransferTokens",
    "0xb6f9de95": "swapExactETHForTokensSupportingFeeOnTransferTokens",
    "0x04e45aaf": "exactInputSingle",
    "0xc04b8d59": "exactInput",
    "0xdb3e2198": "exactOutputSingle",
    "0xf28c0498": "exactOutput",
    "0x472b43f3": "swapExactTokensForTokens (V3)",
    "0x5ae401dc": "multicall",
}

# DEX Router addresses
DEX_ROUTERS = {
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap Universal Router",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3",
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch V5",
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x Exchange",
    "0xcf77a3ba9a5ca399b7c97c74d54e5b1beb874e43": "Aerodrome Router (Base)",
    "0x4752ba5dbc23f44d87826276bf6fd6b1c372ad24": "QuickSwap",
}


async def get_whale_transactions(
    wallet_address: str,
    network: str = "ethereum",
    limit: int = 50,
    api_key: str = None
) -> List[WhaleTransaction]:
    """
    Get recent transactions from a whale wallet.
    
    Args:
        wallet_address: The wallet address to track
        network: Network name ("ethereum", "base", "bsc", etc.)
        limit: Maximum number of transactions to return
        api_key: Optional Etherscan API key
    
    Returns:
        List of WhaleTransaction objects
    """
    api = get_api(api_key)
    wallet_address = wallet_address.lower()
    
    # Get both normal transactions and token transfers
    normal_txs = await api.get_transactions(wallet_address, network, limit)
    token_transfers = await api.get_token_transfers(wallet_address, network, limit)
    
    transactions = []
    seen_hashes = set()
    
    # Process normal transactions
    for tx in normal_txs[:limit]:
        tx_hash = tx.get('hash', '')
        if tx_hash in seen_hashes:
            continue
        seen_hashes.add(tx_hash)
        
        # Determine if it's a swap
        method_id = tx.get('input', '')[:10] if tx.get('input') else ''
        method_name = SWAP_METHODS.get(method_id)
        to_address = tx.get('to', '').lower()
        is_swap = method_name is not None or to_address in DEX_ROUTERS
        
        # Determine swap direction
        swap_direction = None
        if is_swap:
            if "ForETH" in (method_name or ''):
                swap_direction = "sell"
            elif "ForTokens" in (method_name or ''):
                swap_direction = "buy"
        
        try:
            timestamp = datetime.fromtimestamp(int(tx.get('timeStamp', 0)))
        except:
            timestamp = datetime.utcnow()
        
        wt = WhaleTransaction(
            hash=tx_hash,
            from_address=tx.get('from', '').lower(),
            to_address=to_address,
            value=float(tx.get('value', 0)) / 1e18,
            value_usd=None,  # Would need price API
            token_symbol="ETH",
            token_address=None,
            timestamp=timestamp,
            block_number=int(tx.get('blockNumber', 0)),
            gas_used=int(tx.get('gasUsed', 0)),
            gas_price_gwei=float(tx.get('gasPrice', 0)) / 1e9,
            is_swap=is_swap,
            swap_direction=swap_direction,
            method_name=method_name or DEX_ROUTERS.get(to_address),
            network=network
        )
        transactions.append(wt)
    
    # Process token transfers
    for transfer in token_transfers[:limit]:
        tx_hash = transfer.get('hash', '')
        
        try:
            decimals = int(transfer.get('tokenDecimal', 18))
            value = float(transfer.get('value', 0)) / (10 ** decimals)
            timestamp = datetime.fromtimestamp(int(transfer.get('timeStamp', 0)))
        except:
            continue
        
        # Determine direction for this wallet
        from_addr = transfer.get('from', '').lower()
        to_addr = transfer.get('to', '').lower()
        
        is_incoming = to_addr == wallet_address
        swap_direction = "buy" if is_incoming else "sell"
        
        wt = WhaleTransaction(
            hash=tx_hash,
            from_address=from_addr,
            to_address=to_addr,
            value=value,
            value_usd=None,
            token_symbol=transfer.get('tokenSymbol', 'UNKNOWN'),
            token_address=transfer.get('contractAddress', '').lower(),
            timestamp=timestamp,
            block_number=int(transfer.get('blockNumber', 0)),
            gas_used=int(transfer.get('gasUsed', 0)),
            gas_price_gwei=float(transfer.get('gasPrice', 0)) / 1e9,
            is_swap=tx_hash in seen_hashes,  # If we also saw it in normal txs
            swap_direction=swap_direction,
            method_name=None,
            network=network
        )
        transactions.append(wt)
    
    # Sort by timestamp descending
    transactions.sort(key=lambda x: x.timestamp, reverse=True)
    
    return transactions[:limit]


async def analyze_whale_portfolio(
    wallet_address: str,
    network: str = "ethereum",
    api_key: str = None
) -> WhalePortfolio:
    """
    Analyze a whale's portfolio based on recent activity.
    
    Args:
        wallet_address: The wallet address to analyze
        network: Network name ("ethereum", "base", etc.)
        api_key: Optional Etherscan API key
    
    Returns:
        WhalePortfolio object with holdings analysis
    """
    api = get_api(api_key)
    wallet_address = wallet_address.lower()
    
    # Get whale name if known
    whale_name = None
    if network in KNOWN_WHALES:
        whale_info = KNOWN_WHALES[network].get(wallet_address)
        if whale_info:
            whale_name = whale_info.get('name')
    
    # Get native balance
    native_balance = await api.get_eth_balance(wallet_address, network)
    
    # Get token transfers to identify held tokens
    token_transfers = await api.get_token_transfers(wallet_address, network, limit=100)
    
    # Track unique tokens
    token_map: Dict[str, Dict] = {}
    
    for transfer in token_transfers:
        token_address = transfer.get('contractAddress', '').lower()
        if not token_address or token_address in token_map:
            continue
        
        token_map[token_address] = {
            'address': token_address,
            'symbol': transfer.get('tokenSymbol', 'UNKNOWN'),
            'name': transfer.get('tokenName', 'Unknown Token'),
            'decimals': int(transfer.get('tokenDecimal', 18))
        }
    
    # Get balances for each token (rate limited)
    holdings = []
    for token_addr, token_info in list(token_map.items())[:20]:  # Limit to 20 tokens
        try:
            balance_raw = await api.get_token_balance(wallet_address, token_addr, network)
            balance = balance_raw / (10 ** token_info['decimals'])
            
            if balance > 0:
                holdings.append(TokenHolding(
                    token_address=token_addr,
                    symbol=token_info['symbol'],
                    name=token_info['name'],
                    balance=balance,
                    decimals=token_info['decimals']
                ))
        except Exception as e:
            logger.warning(f"Error getting balance for {token_addr}: {e}")
    
    # Get transaction count
    transactions = await api.get_transactions(wallet_address, network, limit=1)
    last_activity = None
    if transactions:
        try:
            last_activity = datetime.fromtimestamp(int(transactions[0].get('timeStamp', 0)))
        except:
            pass
    
    return WhalePortfolio(
        address=wallet_address,
        name=whale_name,
        network=network,
        native_balance=native_balance,
        native_balance_usd=None,  # Would need price API
        holdings=holdings,
        total_value_usd=None,  # Would need price API
        last_activity=last_activity,
        transaction_count=len(token_transfers)
    )


def get_known_whales(network: str = "ethereum") -> Dict[str, Dict]:
    """
    Get list of known whale addresses for a network.
    
    Args:
        network: Network name ("ethereum", "base", etc.)
    
    Returns:
        Dictionary of whale addresses and their info
    """
    return KNOWN_WHALES.get(network, {})


async def check_for_alerts(
    wallet_address: str,
    network: str = "ethereum",
    min_amount_usd: float = 10000,
    lookback_minutes: int = 60,
    api_key: str = None
) -> List[WhaleAlert]:
    """
    Check for significant whale activity that warrants alerts.
    
    Args:
        wallet_address: The wallet address to check
        network: Network name
        min_amount_usd: Minimum transaction value to alert on
        lookback_minutes: How far back to check
        api_key: Optional API key
    
    Returns:
        List of WhaleAlert objects
    """
    transactions = await get_whale_transactions(
        wallet_address, network, limit=20, api_key=api_key
    )
    
    alerts = []
    cutoff = datetime.utcnow() - timedelta(minutes=lookback_minutes)
    
    # Get whale name
    whale_name = None
    whale_importance = "medium"
    if network in KNOWN_WHALES:
        whale_info = KNOWN_WHALES[network].get(wallet_address.lower())
        if whale_info:
            whale_name = whale_info.get('name')
            whale_importance = whale_info.get('importance', 'medium')
    
    for tx in transactions:
        if tx.timestamp < cutoff:
            continue
        
        # For now, alert on all swaps (in real system, would check USD value)
        if tx.is_swap or tx.value > 1.0:  # More than 1 ETH or any swap
            alert_type = tx.swap_direction or "large_transfer"
            
            message = f"🐋 {whale_name or tx.from_address[:10]}... "
            if tx.is_swap:
                if tx.swap_direction == "buy":
                    message += f"bought {tx.value:.4f} {tx.token_symbol}"
                else:
                    message += f"sold {tx.value:.4f} {tx.token_symbol}"
            else:
                message += f"transferred {tx.value:.4f} {tx.token_symbol}"
            
            alerts.append(WhaleAlert(
                whale_address=wallet_address,
                whale_name=whale_name,
                alert_type=alert_type,
                token_symbol=tx.token_symbol,
                token_address=tx.token_address,
                amount=tx.value,
                amount_usd=tx.value_usd,
                tx_hash=tx.hash,
                network=network,
                timestamp=tx.timestamp,
                importance=whale_importance,
                message=message
            ))
    
    return alerts


# ============================================================================
# SYNC WRAPPERS (for use in Streamlit)
# ============================================================================

def get_whale_transactions_sync(
    wallet_address: str,
    network: str = "ethereum",
    limit: int = 50,
    api_key: str = None
) -> List[Dict[str, Any]]:
    """Synchronous wrapper for get_whale_transactions."""
    loop = asyncio.new_event_loop()
    try:
        transactions = loop.run_until_complete(
            get_whale_transactions(wallet_address, network, limit, api_key)
        )
        return [tx.to_dict() for tx in transactions]
    finally:
        loop.close()


def analyze_whale_portfolio_sync(
    wallet_address: str,
    network: str = "ethereum",
    api_key: str = None
) -> Dict[str, Any]:
    """Synchronous wrapper for analyze_whale_portfolio."""
    loop = asyncio.new_event_loop()
    try:
        portfolio = loop.run_until_complete(
            analyze_whale_portfolio(wallet_address, network, api_key)
        )
        return portfolio.to_dict()
    finally:
        loop.close()


def check_for_alerts_sync(
    wallet_address: str,
    network: str = "ethereum",
    min_amount_usd: float = 10000,
    lookback_minutes: int = 60,
    api_key: str = None
) -> List[Dict[str, Any]]:
    """Synchronous wrapper for check_for_alerts."""
    loop = asyncio.new_event_loop()
    try:
        alerts = loop.run_until_complete(
            check_for_alerts(wallet_address, network, min_amount_usd, lookback_minutes, api_key)
        )
        return [alert.to_dict() for alert in alerts]
    finally:
        loop.close()


# Cleanup function
async def cleanup():
    """Clean up API resources."""
    global _api
    if _api:
        await _api.close()
        _api = None
