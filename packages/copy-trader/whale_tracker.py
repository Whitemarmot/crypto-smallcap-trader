"""
Whale Tracker - Monitor large wallets on-chain using Etherscan and DexScreener APIs.
"""
import asyncio
import aiohttp
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import os

from .models import TrackedWallet, DetectedTrade, TradeType, WalletType

logger = logging.getLogger(__name__)


# Well-known whale addresses (examples - should be updated with real addresses)
KNOWN_WHALES = {
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance Hot Wallet",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance Cold Wallet",
    "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503": "Binance Cold 2",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Coinbase Hot Wallet",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase Cold Wallet",
    "0x0716a17fbaee714f1e6ab0f9d59edbc5f09815c0": "Jump Trading",
    "0xf584f8728b874a6a5c7a8d4d387c9aae9172d621": "Wintermute",
    "0x5041ed759dd4afc3a72b8192c143f72f4724081a": "GSR Markets",
}


@dataclass
class WhaleTransaction:
    """Raw transaction data from a whale wallet."""
    hash: str
    from_address: str
    to_address: str
    value: float
    token_address: Optional[str]
    token_symbol: Optional[str]
    token_decimal: int
    block_number: int
    timestamp: datetime
    gas_price: float
    gas_used: int
    method_id: str
    input_data: str


class EtherscanClient:
    """Client for Etherscan API."""
    
    BASE_URLS = {
        "ethereum": "https://api.etherscan.io/api",
        "bsc": "https://api.bscscan.com/api",
        "polygon": "https://api.polygonscan.com/api",
        "arbitrum": "https://api.arbiscan.io/api",
        "base": "https://api.basescan.org/api",
    }
    
    def __init__(self, api_key: str, chain: str = "ethereum"):
        self.api_key = api_key
        self.chain = chain
        self.base_url = self.BASE_URLS.get(chain, self.BASE_URLS["ethereum"])
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_normal_transactions(
        self, 
        address: str, 
        start_block: int = 0,
        end_block: int = 99999999,
        page: int = 1,
        offset: int = 100
    ) -> List[Dict[str, Any]]:
        """Get normal (ETH) transactions for an address."""
        session = await self._get_session()
        
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": "desc",
            "apikey": self.api_key
        }
        
        try:
            async with session.get(self.base_url, params=params) as resp:
                data = await resp.json()
                if data.get("status") == "1":
                    return data.get("result", [])
                else:
                    logger.warning(f"Etherscan API error: {data.get('message')}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching transactions: {e}")
            return []
    
    async def get_token_transfers(
        self,
        address: str,
        contract_address: Optional[str] = None,
        start_block: int = 0,
        end_block: int = 99999999,
        page: int = 1,
        offset: int = 100
    ) -> List[Dict[str, Any]]:
        """Get ERC-20 token transfers for an address."""
        session = await self._get_session()
        
        params = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": "desc",
            "apikey": self.api_key
        }
        
        if contract_address:
            params["contractaddress"] = contract_address
        
        try:
            async with session.get(self.base_url, params=params) as resp:
                data = await resp.json()
                if data.get("status") == "1":
                    return data.get("result", [])
                else:
                    logger.warning(f"Etherscan API error: {data.get('message')}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching token transfers: {e}")
            return []
    
    async def get_internal_transactions(
        self,
        address: str,
        start_block: int = 0,
        end_block: int = 99999999
    ) -> List[Dict[str, Any]]:
        """Get internal transactions for an address."""
        session = await self._get_session()
        
        params = {
            "module": "account",
            "action": "txlistinternal",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "sort": "desc",
            "apikey": self.api_key
        }
        
        try:
            async with session.get(self.base_url, params=params) as resp:
                data = await resp.json()
                if data.get("status") == "1":
                    return data.get("result", [])
                return []
        except Exception as e:
            logger.error(f"Error fetching internal transactions: {e}")
            return []


class DexScreenerClient:
    """Client for DexScreener API (no API key needed)."""
    
    BASE_URL = "https://api.dexscreener.com"
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_token_pairs(self, chain: str, token_address: str) -> List[Dict[str, Any]]:
        """Get trading pairs for a token."""
        session = await self._get_session()
        url = f"{self.BASE_URL}/latest/dex/tokens/{token_address}"
        
        try:
            async with session.get(url) as resp:
                data = await resp.json()
                return data.get("pairs", [])
        except Exception as e:
            logger.error(f"Error fetching token pairs: {e}")
            return []
    
    async def search_pairs(self, query: str) -> List[Dict[str, Any]]:
        """Search for trading pairs by name/symbol."""
        session = await self._get_session()
        url = f"{self.BASE_URL}/latest/dex/search?q={query}"
        
        try:
            async with session.get(url) as resp:
                data = await resp.json()
                return data.get("pairs", [])
        except Exception as e:
            logger.error(f"Error searching pairs: {e}")
            return []
    
    async def get_pair_info(self, chain: str, pair_address: str) -> Optional[Dict[str, Any]]:
        """Get detailed info for a specific pair."""
        session = await self._get_session()
        url = f"{self.BASE_URL}/latest/dex/pairs/{chain}/{pair_address}"
        
        try:
            async with session.get(url) as resp:
                data = await resp.json()
                pairs = data.get("pairs", [])
                return pairs[0] if pairs else None
        except Exception as e:
            logger.error(f"Error fetching pair info: {e}")
            return None


class WhaleTracker:
    """
    Tracks whale wallets and detects their trades.
    """
    
    # Common DEX router addresses
    DEX_ROUTERS = {
        "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": ("uniswap_v2", "ethereum"),
        "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": ("uniswap_v3", "ethereum"),
        "0xe592427a0aece92de3edee1f18e0157c05861564": ("uniswap_v3", "ethereum"),
        "0x1111111254eeb25477b68fb85ed929f73a960582": ("1inch", "ethereum"),
        "0xdef1c0ded9bec7f1a1670819833240f027b25eff": ("0x", "ethereum"),
        "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f": ("sushiswap", "ethereum"),
    }
    
    # Method signatures for swap functions
    SWAP_METHODS = {
        "0x7ff36ab5": "swapExactETHForTokens",
        "0x18cbafe5": "swapExactTokensForETH",
        "0x38ed1739": "swapExactTokensForTokens",
        "0x8803dbee": "swapTokensForExactTokens",
        "0xfb3bdb41": "swapETHForExactTokens",
        "0x5c11d795": "swapExactTokensForTokensSupportingFeeOnTransferTokens",
        "0x791ac947": "swapExactTokensForETHSupportingFeeOnTransferTokens",
        "0xb6f9de95": "swapExactETHForTokensSupportingFeeOnTransferTokens",
        "0x04e45aaf": "exactInputSingle",  # Uniswap V3
        "0xc04b8d59": "exactInput",  # Uniswap V3
        "0xdb3e2198": "exactOutputSingle",  # Uniswap V3
        "0xf28c0498": "exactOutput",  # Uniswap V3
    }
    
    def __init__(
        self,
        etherscan_api_key: str,
        chain: str = "ethereum",
        tracked_wallets: Optional[List[TrackedWallet]] = None
    ):
        self.etherscan = EtherscanClient(etherscan_api_key, chain)
        self.dexscreener = DexScreenerClient()
        self.chain = chain
        self.tracked_wallets: Dict[str, TrackedWallet] = {}
        
        if tracked_wallets:
            for wallet in tracked_wallets:
                self.tracked_wallets[wallet.address.lower()] = wallet
        
        # Track last seen block per wallet
        self._last_blocks: Dict[str, int] = {}
        
        # Callback for trade detection
        self._on_trade_callback = None
    
    def add_known_whales(self):
        """Add known whale addresses to tracking."""
        for address, name in KNOWN_WHALES.items():
            if address.lower() not in self.tracked_wallets:
                wallet = TrackedWallet(
                    address=address,
                    name=name,
                    wallet_type=WalletType.WHALE,
                    weight=0.7  # Default weight for known whales
                )
                self.tracked_wallets[address.lower()] = wallet
                logger.info(f"Added whale: {name} ({address[:10]}...)")
    
    def add_wallet(self, wallet: TrackedWallet):
        """Add a wallet to track."""
        self.tracked_wallets[wallet.address.lower()] = wallet
        logger.info(f"Now tracking: {wallet.name} ({wallet.address[:10]}...)")
    
    def remove_wallet(self, address: str):
        """Remove a wallet from tracking."""
        address = address.lower()
        if address in self.tracked_wallets:
            del self.tracked_wallets[address]
            logger.info(f"Stopped tracking: {address[:10]}...")
    
    def set_trade_callback(self, callback):
        """Set callback function for when trades are detected."""
        self._on_trade_callback = callback
    
    async def scan_wallet(self, wallet: TrackedWallet) -> List[DetectedTrade]:
        """Scan a single wallet for recent trades."""
        detected_trades = []
        last_block = self._last_blocks.get(wallet.address, 0)
        
        # Get token transfers
        transfers = await self.etherscan.get_token_transfers(
            wallet.address,
            start_block=last_block + 1
        )
        
        # Get normal transactions (for swap detection)
        txs = await self.etherscan.get_normal_transactions(
            wallet.address,
            start_block=last_block + 1
        )
        
        # Process transactions to detect swaps
        for tx in txs:
            trade = await self._analyze_transaction(tx, wallet, transfers)
            if trade:
                detected_trades.append(trade)
                wallet.total_trades_detected += 1
                
                # Update last block
                block = int(tx.get("blockNumber", 0))
                if block > self._last_blocks.get(wallet.address, 0):
                    self._last_blocks[wallet.address] = block
                
                # Trigger callback
                if self._on_trade_callback:
                    await self._on_trade_callback(trade)
        
        return detected_trades
    
    async def _analyze_transaction(
        self, 
        tx: Dict[str, Any], 
        wallet: TrackedWallet,
        transfers: List[Dict[str, Any]]
    ) -> Optional[DetectedTrade]:
        """Analyze a transaction to detect if it's a swap."""
        
        to_address = tx.get("to", "").lower()
        method_id = tx.get("input", "")[:10] if tx.get("input") else ""
        
        # Check if transaction is to a known DEX router
        dex_info = self.DEX_ROUTERS.get(to_address)
        if not dex_info:
            return None
        
        dex_name, chain = dex_info
        
        # Check if method is a swap
        method_name = self.SWAP_METHODS.get(method_id)
        if not method_name:
            return None
        
        # Find related token transfers in the same tx
        tx_hash = tx.get("hash", "")
        related_transfers = [
            t for t in transfers 
            if t.get("hash", "").lower() == tx_hash.lower()
        ]
        
        if len(related_transfers) < 2:
            # Need at least 2 transfers for a swap
            return None
        
        # Identify token in/out
        token_in = None
        token_out = None
        
        for transfer in related_transfers:
            if transfer.get("from", "").lower() == wallet.address.lower():
                token_in = transfer
            if transfer.get("to", "").lower() == wallet.address.lower():
                token_out = transfer
        
        if not token_in or not token_out:
            return None
        
        # Calculate amounts
        decimals_in = int(token_in.get("tokenDecimal", 18))
        decimals_out = int(token_out.get("tokenDecimal", 18))
        
        amount_in = float(token_in.get("value", 0)) / (10 ** decimals_in)
        amount_out = float(token_out.get("value", 0)) / (10 ** decimals_out)
        
        # Get USD value from DexScreener
        token_out_address = token_out.get("contractAddress", "")
        pairs = await self.dexscreener.get_token_pairs(self.chain, token_out_address)
        
        price_usd = 0.0
        if pairs:
            price_usd = float(pairs[0].get("priceUsd", 0))
        
        amount_usd = amount_out * price_usd if price_usd else 0.0
        
        # Determine trade type
        # If output token is ETH/WETH/stablecoin, it's a SELL
        stable_tokens = ["usdc", "usdt", "dai", "weth", "eth"]
        token_out_symbol = token_out.get("tokenSymbol", "").lower()
        
        if token_out_symbol in stable_tokens:
            trade_type = TradeType.SELL
        else:
            trade_type = TradeType.BUY
        
        return DetectedTrade(
            tx_hash=tx_hash,
            wallet_address=wallet.address,
            wallet_name=wallet.name,
            trade_type=trade_type,
            token_in=token_in.get("contractAddress", ""),
            token_out=token_out.get("contractAddress", ""),
            token_in_symbol=token_in.get("tokenSymbol", "UNKNOWN"),
            token_out_symbol=token_out.get("tokenSymbol", "UNKNOWN"),
            amount_in=amount_in,
            amount_out=amount_out,
            amount_usd=amount_usd,
            price_impact=0.0,  # Would need to calculate from pool data
            dex=dex_name,
            chain=self.chain,
            block_number=int(tx.get("blockNumber", 0)),
            timestamp=datetime.fromtimestamp(int(tx.get("timeStamp", 0))),
            gas_price_gwei=float(tx.get("gasPrice", 0)) / 1e9,
            wallet_weight=wallet.weight,
            confidence_score=1.0
        )
    
    async def scan_all_wallets(self) -> List[DetectedTrade]:
        """Scan all tracked wallets for trades."""
        all_trades = []
        
        for wallet in self.tracked_wallets.values():
            if not wallet.enabled:
                continue
            
            try:
                trades = await self.scan_wallet(wallet)
                all_trades.extend(trades)
                logger.debug(f"Found {len(trades)} trades for {wallet.name}")
            except Exception as e:
                logger.error(f"Error scanning wallet {wallet.name}: {e}")
            
            # Rate limiting - Etherscan has 5 calls/sec limit
            await asyncio.sleep(0.25)
        
        return all_trades
    
    async def start_monitoring(self, interval_seconds: float = 15.0):
        """
        Start continuous monitoring of tracked wallets.
        Polls for new transactions at the specified interval.
        """
        logger.info(f"Starting whale monitoring with {len(self.tracked_wallets)} wallets")
        
        while True:
            try:
                trades = await self.scan_all_wallets()
                if trades:
                    logger.info(f"Detected {len(trades)} new trades")
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            await asyncio.sleep(interval_seconds)
    
    async def close(self):
        """Clean up resources."""
        await self.etherscan.close()
        await self.dexscreener.close()
