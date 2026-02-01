"""
DEX Aggregator - Multi-chain swap via 1inch Fusion API
Supports: Ethereum, Base, Arbitrum, BSC, Polygon

Mode dry_run par défaut - NE PAS exécuter de vrais trades sans confirmation.
"""

import asyncio
import httpx
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class Network(Enum):
    """Supported networks with chain IDs"""
    ETHEREUM = 1
    BSC = 56
    POLYGON = 137
    ARBITRUM = 42161
    BASE = 8453
    OPTIMISM = 10
    
    @classmethod
    def from_name(cls, name: str) -> "Network":
        """Get network from string name"""
        mapping = {
            "ethereum": cls.ETHEREUM,
            "eth": cls.ETHEREUM,
            "mainnet": cls.ETHEREUM,
            "bsc": cls.BSC,
            "bnb": cls.BSC,
            "polygon": cls.POLYGON,
            "matic": cls.POLYGON,
            "arbitrum": cls.ARBITRUM,
            "arb": cls.ARBITRUM,
            "base": cls.BASE,
            "optimism": cls.OPTIMISM,
            "op": cls.OPTIMISM,
        }
        return mapping.get(name.lower(), cls.ETHEREUM)


@dataclass
class TokenInfo:
    """Token information"""
    address: str
    symbol: str
    decimals: int
    name: str = ""
    logo_uri: str = ""
    
    @property
    def is_native(self) -> bool:
        return self.address.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    
    def to_wei(self, amount: Decimal) -> int:
        """Convert human amount to wei"""
        return int(amount * Decimal(10 ** self.decimals))
    
    def from_wei(self, wei_amount: int) -> Decimal:
        """Convert wei to human amount"""
        return Decimal(wei_amount) / Decimal(10 ** self.decimals)


@dataclass
class Quote:
    """Swap quote result"""
    src_token: TokenInfo
    dst_token: TokenInfo
    src_amount: int  # in wei
    dst_amount: int  # in wei (estimated)
    
    price: Decimal  # dst per src
    price_usd: Optional[Decimal] = None
    gas_estimate: int = 0
    protocols: List[Dict] = field(default_factory=list)
    
    quoted_at: datetime = field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None
    
    @property
    def src_amount_human(self) -> Decimal:
        return self.src_token.from_wei(self.src_amount)
    
    @property
    def dst_amount_human(self) -> Decimal:
        return self.dst_token.from_wei(self.dst_amount)
    
    @property
    def price_impact(self) -> Decimal:
        """Estimated price impact (placeholder)"""
        return Decimal("0")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "src_token": self.src_token.symbol,
            "dst_token": self.dst_token.symbol,
            "src_amount": str(self.src_amount_human),
            "dst_amount": str(self.dst_amount_human),
            "price": str(self.price),
            "gas_estimate": self.gas_estimate,
            "quoted_at": self.quoted_at.isoformat(),
        }


@dataclass
class SwapResult:
    """Result of a swap execution"""
    success: bool
    tx_hash: Optional[str] = None
    src_amount: int = 0
    dst_amount: int = 0
    gas_used: int = 0
    gas_price: int = 0
    total_cost_wei: int = 0
    error: Optional[str] = None
    is_dry_run: bool = True
    executed_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tx_hash": self.tx_hash,
            "src_amount": str(self.src_amount),
            "dst_amount": str(self.dst_amount),
            "gas_used": self.gas_used,
            "total_cost_wei": str(self.total_cost_wei),
            "error": self.error,
            "is_dry_run": self.is_dry_run,
            "executed_at": self.executed_at.isoformat(),
        }


# Common token addresses by network
COMMON_TOKENS: Dict[int, Dict[str, TokenInfo]] = {
    # Ethereum
    1: {
        "ETH": TokenInfo("0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", "ETH", 18, "Ethereum"),
        "WETH": TokenInfo("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "WETH", 18, "Wrapped Ether"),
        "USDC": TokenInfo("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC", 6, "USD Coin"),
        "USDT": TokenInfo("0xdAC17F958D2ee523a2206206994597C13D831ec7", "USDT", 6, "Tether"),
        "DAI": TokenInfo("0x6B175474E89094C44Da98b954EescdeCB5BE3830", "DAI", 18, "Dai"),
        "WBTC": TokenInfo("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", "WBTC", 8, "Wrapped BTC"),
        "PEPE": TokenInfo("0x6982508145454ce325ddbe47a25d4ec3d2311933", "PEPE", 18, "Pepe"),
    },
    # Base
    8453: {
        "ETH": TokenInfo("0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", "ETH", 18, "Ethereum"),
        "WETH": TokenInfo("0x4200000000000000000000000000000000000006", "WETH", 18, "Wrapped Ether"),
        "USDC": TokenInfo("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "USDC", 6, "USD Coin"),
        "USDbC": TokenInfo("0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA", "USDbC", 6, "Bridged USDC"),
        "DAI": TokenInfo("0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb", "DAI", 18, "Dai"),
        "BRETT": TokenInfo("0x532f27101965dd16442E59d40670FaF5eBB142E4", "BRETT", 18, "Brett"),
        "DEGEN": TokenInfo("0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed", "DEGEN", 18, "Degen"),
    },
    # Arbitrum
    42161: {
        "ETH": TokenInfo("0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", "ETH", 18, "Ethereum"),
        "WETH": TokenInfo("0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", "WETH", 18, "Wrapped Ether"),
        "USDC": TokenInfo("0xaf88d065e77c8cC2239327C5EDb3A432268e5831", "USDC", 6, "USD Coin"),
        "USDT": TokenInfo("0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", "USDT", 6, "Tether"),
        "ARB": TokenInfo("0x912CE59144191C1204E64559FE8253a0e49E6548", "ARB", 18, "Arbitrum"),
        "GMX": TokenInfo("0xfc5A1A6EB076a2C7aD06eD22C90d7E710E35ad0a", "GMX", 18, "GMX"),
    },
    # BSC
    56: {
        "BNB": TokenInfo("0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", "BNB", 18, "BNB"),
        "WBNB": TokenInfo("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c", "WBNB", 18, "Wrapped BNB"),
        "USDC": TokenInfo("0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", "USDC", 18, "USD Coin"),
        "USDT": TokenInfo("0x55d398326f99059fF775485246999027B3197955", "USDT", 18, "Tether"),
        "BUSD": TokenInfo("0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56", "BUSD", 18, "Binance USD"),
        "CAKE": TokenInfo("0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82", "CAKE", 18, "PancakeSwap"),
    },
    # Polygon
    137: {
        "MATIC": TokenInfo("0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", "MATIC", 18, "Polygon"),
        "WMATIC": TokenInfo("0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270", "WMATIC", 18, "Wrapped MATIC"),
        "USDC": TokenInfo("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", "USDC", 6, "USD Coin"),
        "USDT": TokenInfo("0xc2132D05D31c914a87C6611C10748AEb04B58e8F", "USDT", 6, "Tether"),
        "WETH": TokenInfo("0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619", "WETH", 18, "Wrapped Ether"),
    },
}


# RPC URLs (public, can be overridden)
DEFAULT_RPC_URLS = {
    1: "https://eth.llamarpc.com",
    56: "https://bsc-dataseed1.binance.org",
    137: "https://polygon-rpc.com",
    42161: "https://arb1.arbitrum.io/rpc",
    8453: "https://mainnet.base.org",
    10: "https://mainnet.optimism.io",
}


class DexAggregator:
    """
    Multi-chain DEX aggregator using 1inch API
    
    Usage:
        async with DexAggregator() as dex:
            quote = await dex.get_quote("ETH", "USDC", Decimal("0.1"), Network.ETHEREUM)
            print(f"Price: {quote.price}")
    """
    
    # 1inch API base URL (Fusion v2 is free, Classic needs key)
    BASE_URL = "https://api.1inch.dev"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        dry_run: bool = True,
        rpc_urls: Optional[Dict[int, str]] = None,
    ):
        """
        Initialize DEX aggregator
        
        Args:
            api_key: Optional 1inch API key (for higher rate limits)
            dry_run: If True, never execute real transactions (default: True)
            rpc_urls: Custom RPC URLs by chain ID
        """
        self.api_key = api_key
        self.dry_run = dry_run
        self.rpc_urls = rpc_urls or DEFAULT_RPC_URLS.copy()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        await self._init_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _init_client(self):
        """Initialize HTTP client"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=httpx.Timeout(30.0),
        )
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make API request"""
        if not self._client:
            await self._init_client()
        
        try:
            if method == "GET":
                response = await self._client.get(endpoint, params=params)
            else:
                response = await self._client.post(endpoint, json=params)
            
            if response.status_code == 429:
                raise Exception("Rate limit exceeded - wait before retrying")
            
            data = response.json()
            
            if response.status_code >= 400:
                error_msg = data.get("description", data.get("error", str(data)))
                raise Exception(f"API error ({response.status_code}): {error_msg}")
            
            return data
            
        except httpx.TimeoutException:
            raise Exception("Request timeout")
        except httpx.RequestError as e:
            raise Exception(f"Request failed: {e}")
    
    def get_token(self, symbol_or_address: str, network: Network) -> Optional[TokenInfo]:
        """
        Get token info by symbol or address
        
        Args:
            symbol_or_address: Token symbol (e.g., "ETH") or address
            network: Target network
        
        Returns:
            TokenInfo or None if not found
        """
        chain_id = network.value
        tokens = COMMON_TOKENS.get(chain_id, {})
        
        # Try by symbol
        if symbol_or_address.upper() in tokens:
            return tokens[symbol_or_address.upper()]
        
        # Try by address
        for token in tokens.values():
            if token.address.lower() == symbol_or_address.lower():
                return token
        
        return None
    
    async def get_quote(
        self,
        token_in: str,
        token_out: str,
        amount: Decimal,
        network: Network,
    ) -> Quote:
        """
        Get swap quote
        
        Args:
            token_in: Source token symbol or address
            token_out: Destination token symbol or address
            amount: Amount to swap (human readable)
            network: Target network
        
        Returns:
            Quote with price and estimated output
        
        Example:
            quote = await dex.get_quote("ETH", "USDC", Decimal("0.1"), Network.BASE)
        """
        chain_id = network.value
        
        # Resolve tokens
        src_token = self.get_token(token_in, network)
        dst_token = self.get_token(token_out, network)
        
        if not src_token:
            raise ValueError(f"Unknown source token: {token_in} on {network.name}")
        if not dst_token:
            raise ValueError(f"Unknown destination token: {token_out} on {network.name}")
        
        # Convert to wei
        src_amount = src_token.to_wei(amount)
        
        # Call 1inch API
        params = {
            "src": src_token.address,
            "dst": dst_token.address,
            "amount": str(src_amount),
            "includeProtocols": "true",
            "includeGas": "true",
        }
        
        data = await self._request("GET", f"/swap/v6.0/{chain_id}/quote", params)
        
        dst_amount = int(data["dstAmount"])
        gas_estimate = int(data.get("gas", 0))
        
        # Calculate price
        src_dec = src_token.from_wei(src_amount)
        dst_dec = dst_token.from_wei(dst_amount)
        price = dst_dec / src_dec if src_dec > 0 else Decimal("0")
        
        return Quote(
            src_token=src_token,
            dst_token=dst_token,
            src_amount=src_amount,
            dst_amount=dst_amount,
            price=price,
            gas_estimate=gas_estimate,
            protocols=data.get("protocols", []),
            quoted_at=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(seconds=30),
        )
    
    async def execute_swap(
        self,
        wallet_address: str,
        private_key: str,
        token_in: str,
        token_out: str,
        amount: Decimal,
        slippage: Decimal = Decimal("1.0"),
        network: Network = Network.ETHEREUM,
    ) -> SwapResult:
        """
        Execute a swap (REQUIRES CONFIRMATION - respects dry_run mode)
        
        Args:
            wallet_address: Wallet address executing the swap
            private_key: Private key for signing (NOT USED in dry_run mode)
            token_in: Source token symbol or address
            token_out: Destination token symbol or address
            amount: Amount to swap (human readable)
            slippage: Max slippage percentage (default 1%)
            network: Target network
        
        Returns:
            SwapResult with transaction details
        
        ⚠️ IMPORTANT: In dry_run mode (default), this simulates the swap without execution.
        """
        # Get quote first
        quote = await self.get_quote(token_in, token_out, amount, network)
        
        # DRY RUN MODE - simulate without executing
        if self.dry_run:
            return SwapResult(
                success=True,
                tx_hash=None,
                src_amount=quote.src_amount,
                dst_amount=quote.dst_amount,
                gas_used=quote.gas_estimate,
                gas_price=0,
                total_cost_wei=0,
                error=None,
                is_dry_run=True,
                executed_at=datetime.utcnow(),
            )
        
        # REAL EXECUTION - only if dry_run=False
        # This requires web3 and proper account setup
        try:
            from web3 import Web3
            from eth_account import Account
            
            chain_id = network.value
            
            # Get swap transaction data
            params = {
                "src": quote.src_token.address,
                "dst": quote.dst_token.address,
                "amount": str(quote.src_amount),
                "from": wallet_address,
                "slippage": str(float(slippage)),
                "includeGas": "true",
            }
            
            swap_data = await self._request("GET", f"/swap/v6.0/{chain_id}/swap", params)
            
            # Build transaction
            tx_data = swap_data["tx"]
            
            w3 = Web3(Web3.HTTPProvider(self.rpc_urls[chain_id]))
            account = Account.from_key(private_key)
            
            nonce = w3.eth.get_transaction_count(account.address)
            
            tx = {
                "to": Web3.to_checksum_address(tx_data["to"]),
                "data": tx_data["data"],
                "value": int(tx_data.get("value", 0)),
                "gas": int(tx_data.get("gas", 300000)),
                "nonce": nonce,
                "chainId": chain_id,
            }
            
            # Add gas price (EIP-1559 if supported)
            try:
                base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
                max_priority = w3.to_wei(2, "gwei")
                max_fee = base_fee * 2 + max_priority
                tx["maxFeePerGas"] = max_fee
                tx["maxPriorityFeePerGas"] = max_priority
            except Exception:
                tx["gasPrice"] = w3.eth.gas_price
            
            # Sign and send
            signed_tx = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            # Wait for confirmation
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            return SwapResult(
                success=receipt["status"] == 1,
                tx_hash=tx_hash.hex(),
                src_amount=quote.src_amount,
                dst_amount=int(swap_data.get("dstAmount", quote.dst_amount)),
                gas_used=receipt["gasUsed"],
                gas_price=receipt.get("effectiveGasPrice", 0),
                total_cost_wei=receipt["gasUsed"] * receipt.get("effectiveGasPrice", 0),
                is_dry_run=False,
                executed_at=datetime.utcnow(),
            )
            
        except Exception as e:
            return SwapResult(
                success=False,
                error=str(e),
                is_dry_run=False,
                executed_at=datetime.utcnow(),
            )
    
    async def get_token_list(self, network: Network) -> Dict[str, TokenInfo]:
        """
        Get list of supported tokens for a network
        
        Args:
            network: Target network
        
        Returns:
            Dict of token address -> TokenInfo
        """
        chain_id = network.value
        
        try:
            data = await self._request("GET", f"/swap/v6.0/{chain_id}/tokens")
            
            tokens = {}
            for addr, info in data.get("tokens", {}).items():
                tokens[addr.lower()] = TokenInfo(
                    address=addr,
                    symbol=info["symbol"],
                    decimals=info["decimals"],
                    name=info.get("name", ""),
                    logo_uri=info.get("logoURI", ""),
                )
            return tokens
        except Exception:
            # Fallback to local cache
            return {t.address.lower(): t for t in COMMON_TOKENS.get(chain_id, {}).values()}


# Simplified functions for easy import
async def get_quote(
    token_in: str,
    token_out: str,
    amount: Decimal,
    network: str = "ethereum",
) -> Quote:
    """
    Simple function to get a swap quote
    
    Args:
        token_in: Source token (symbol or address)
        token_out: Destination token (symbol or address)
        amount: Amount to swap
        network: Network name (ethereum, base, arbitrum, bsc, polygon)
    
    Returns:
        Quote object
    
    Example:
        quote = await get_quote("ETH", "USDC", Decimal("0.1"), "base")
    """
    net = Network.from_name(network)
    async with DexAggregator() as dex:
        return await dex.get_quote(token_in, token_out, amount, net)


async def execute_swap(
    wallet_address: str,
    private_key: str,
    token_in: str,
    token_out: str,
    amount: Decimal,
    slippage: Decimal = Decimal("1.0"),
    network: str = "ethereum",
    dry_run: bool = True,
) -> SwapResult:
    """
    Execute a swap (dry_run=True by default for safety)
    
    Args:
        wallet_address: Wallet address
        private_key: Private key for signing
        token_in: Source token
        token_out: Destination token
        amount: Amount to swap
        slippage: Max slippage %
        network: Network name
        dry_run: If True, simulate without executing (default: True)
    
    Returns:
        SwapResult
    """
    net = Network.from_name(network)
    async with DexAggregator(dry_run=dry_run) as dex:
        return await dex.execute_swap(
            wallet_address, private_key,
            token_in, token_out, amount, slippage, net
        )


# CLI test
if __name__ == "__main__":
    async def main():
        print("🔄 Testing DEX Aggregator...")
        
        async with DexAggregator() as dex:
            # Test quote on Base
            print("\n📊 Getting quote: 0.01 ETH → USDC on Base...")
            try:
                quote = await dex.get_quote("ETH", "USDC", Decimal("0.01"), Network.BASE)
                print(f"   Input: {quote.src_amount_human} {quote.src_token.symbol}")
                print(f"   Output: {quote.dst_amount_human} {quote.dst_token.symbol}")
                print(f"   Price: 1 ETH = {quote.price:.2f} USDC")
                print(f"   Gas: {quote.gas_estimate}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            # Test quote on Ethereum
            print("\n📊 Getting quote: 0.1 ETH → USDC on Ethereum...")
            try:
                quote = await dex.get_quote("ETH", "USDC", Decimal("0.1"), Network.ETHEREUM)
                print(f"   Input: {quote.src_amount_human} {quote.src_token.symbol}")
                print(f"   Output: {quote.dst_amount_human} {quote.dst_token.symbol}")
                print(f"   Price: 1 ETH = {quote.price:.2f} USDC")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            # Test dry run swap
            print("\n🔄 Testing DRY RUN swap...")
            result = await dex.execute_swap(
                wallet_address="0x0000000000000000000000000000000000000000",
                private_key="0x" + "00" * 32,
                token_in="ETH",
                token_out="USDC",
                amount=Decimal("0.01"),
                network=Network.BASE,
            )
            print(f"   Success: {result.success}")
            print(f"   Dry run: {result.is_dry_run}")
            print(f"   Would receive: ~{result.dst_amount} wei")
    
    asyncio.run(main())
