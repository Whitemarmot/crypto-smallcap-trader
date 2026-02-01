"""
Balance retrieval for EVM wallets.
Supports native tokens (ETH/BNB) and ERC20 tokens.
"""

from decimal import Decimal
from typing import Optional, Dict, List
from dataclasses import dataclass

from web3 import Web3
from web3.exceptions import ContractLogicError

from .networks import get_network, get_rpc_url, NetworkConfig


# Standard ERC20 ABI for balanceOf, decimals, symbol
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
]


@dataclass
class TokenBalance:
    """Token balance information."""
    address: str
    symbol: str
    name: str
    balance_raw: int
    decimals: int
    balance: Decimal
    
    @property
    def balance_formatted(self) -> str:
        """Return formatted balance string."""
        return f"{self.balance:.6f} {self.symbol}"


@dataclass
class NativeBalance:
    """Native token balance (ETH/BNB)."""
    symbol: str
    balance_raw: int
    decimals: int = 18
    balance: Decimal = Decimal("0")
    
    def __post_init__(self):
        if self.balance == Decimal("0") and self.balance_raw > 0:
            self.balance = Decimal(self.balance_raw) / Decimal(10 ** self.decimals)
    
    @property
    def balance_formatted(self) -> str:
        """Return formatted balance string."""
        return f"{self.balance:.6f} {self.symbol}"


class BalanceChecker:
    """Check balances on EVM networks."""
    
    def __init__(
        self,
        network: str = "ethereum",
        custom_rpc: Optional[str] = None,
    ):
        """
        Initialize balance checker.
        
        Args:
            network: Network name (ethereum, bsc, base, arbitrum, etc.)
            custom_rpc: Optional custom RPC URL
        """
        self.network_config = get_network(network)
        self.rpc_url = get_rpc_url(network, custom_rpc)
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to {network} RPC: {self.rpc_url}")
    
    def get_native_balance(self, address: str) -> NativeBalance:
        """
        Get native token balance (ETH/BNB).
        
        Args:
            address: Wallet address (checksummed or not)
            
        Returns:
            NativeBalance with balance information
        """
        address = Web3.to_checksum_address(address)
        balance_wei = self.w3.eth.get_balance(address)
        
        return NativeBalance(
            symbol=self.network_config.symbol,
            balance_raw=balance_wei,
            decimals=self.network_config.decimals,
        )
    
    def get_token_balance(
        self,
        wallet_address: str,
        token_address: str,
    ) -> TokenBalance:
        """
        Get ERC20 token balance.
        
        Args:
            wallet_address: Wallet address to check
            token_address: ERC20 token contract address
            
        Returns:
            TokenBalance with balance information
        """
        wallet_address = Web3.to_checksum_address(wallet_address)
        token_address = Web3.to_checksum_address(token_address)
        
        contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
        
        try:
            balance_raw = contract.functions.balanceOf(wallet_address).call()
            decimals = contract.functions.decimals().call()
            symbol = contract.functions.symbol().call()
            name = contract.functions.name().call()
        except ContractLogicError as e:
            raise ValueError(f"Invalid token contract: {token_address}") from e
        
        balance = Decimal(balance_raw) / Decimal(10 ** decimals)
        
        return TokenBalance(
            address=token_address,
            symbol=symbol,
            name=name,
            balance_raw=balance_raw,
            decimals=decimals,
            balance=balance,
        )
    
    def get_multiple_token_balances(
        self,
        wallet_address: str,
        token_addresses: List[str],
    ) -> Dict[str, TokenBalance]:
        """
        Get balances for multiple ERC20 tokens.
        
        Args:
            wallet_address: Wallet address to check
            token_addresses: List of ERC20 token contract addresses
            
        Returns:
            Dict mapping token address to TokenBalance
        """
        results = {}
        for token_addr in token_addresses:
            try:
                balance = self.get_token_balance(wallet_address, token_addr)
                results[token_addr.lower()] = balance
            except Exception as e:
                # Skip invalid tokens, log error
                print(f"Warning: Failed to get balance for {token_addr}: {e}")
        
        return results
    
    def get_full_balance(
        self,
        wallet_address: str,
        token_addresses: Optional[List[str]] = None,
    ) -> Dict:
        """
        Get complete balance including native and tokens.
        
        Args:
            wallet_address: Wallet address to check
            token_addresses: Optional list of ERC20 token addresses
            
        Returns:
            Dict with 'native' and 'tokens' keys
        """
        result = {
            "network": self.network_config.name,
            "address": wallet_address,
            "native": self.get_native_balance(wallet_address),
            "tokens": {},
        }
        
        if token_addresses:
            result["tokens"] = self.get_multiple_token_balances(
                wallet_address, token_addresses
            )
        
        return result


# Popular token addresses by network
POPULAR_TOKENS = {
    "ethereum": {
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "DAI": "0x6B175474E89094C44Da98b954EescdeCB5BE3830",
    },
    "bsc": {
        "USDT": "0x55d398326f99059fF775485246999027B3197955",
        "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
    },
    "base": {
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "WETH": "0x4200000000000000000000000000000000000006",
        "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    },
    "arbitrum": {
        "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "ARB": "0x912CE59144191C1204E64559FE8253a0e49E6548",
    },
}


# Convenience functions
def get_balance(
    address: str,
    network: str = "ethereum",
    custom_rpc: Optional[str] = None,
) -> NativeBalance:
    """Get native token balance for an address."""
    checker = BalanceChecker(network, custom_rpc)
    return checker.get_native_balance(address)


def get_token_balance(
    wallet_address: str,
    token_address: str,
    network: str = "ethereum",
    custom_rpc: Optional[str] = None,
) -> TokenBalance:
    """Get ERC20 token balance."""
    checker = BalanceChecker(network, custom_rpc)
    return checker.get_token_balance(wallet_address, token_address)


def get_all_balances(
    address: str,
    network: str = "ethereum",
    include_popular_tokens: bool = True,
    custom_rpc: Optional[str] = None,
) -> Dict:
    """
    Get all balances including popular tokens.
    
    Args:
        address: Wallet address
        network: Network name
        include_popular_tokens: Whether to include popular tokens for the network
        custom_rpc: Optional custom RPC URL
        
    Returns:
        Dict with native and token balances
    """
    checker = BalanceChecker(network, custom_rpc)
    
    tokens = None
    if include_popular_tokens and network in POPULAR_TOKENS:
        tokens = list(POPULAR_TOKENS[network].values())
    
    return checker.get_full_balance(address, tokens)
