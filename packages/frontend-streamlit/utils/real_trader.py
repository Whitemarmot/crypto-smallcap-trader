"""
🔄 Real Trader - Execute real trades via 1inch API on EVM chains
"""

import os
import json
import requests
import time
from typing import Dict, Optional, Tuple
from decimal import Decimal
from web3 import Web3
from web3.middleware import geth_poa_middleware

from .wallet_keys import get_private_key, has_private_key

# Chain configs
CHAINS = {
    'ethereum': {
        'chain_id': 1,
        'rpc': 'https://eth.llamarpc.com',
        'native': 'ETH',
        'wrapped': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
        'usdc': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        '1inch_api': 'https://api.1inch.dev/swap/v6.0/1',
    },
    'base': {
        'chain_id': 8453,
        'rpc': 'https://mainnet.base.org',
        'native': 'ETH',
        'wrapped': '0x4200000000000000000000000000000000000006',  # WETH on Base
        'usdc': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',  # USDC on Base
        '1inch_api': 'https://api.1inch.dev/swap/v6.0/8453',
    },
    'arbitrum': {
        'chain_id': 42161,
        'rpc': 'https://arb1.arbitrum.io/rpc',
        'native': 'ETH',
        'wrapped': '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',
        'usdc': '0xaf88d065e77c8cC2239327C5EDb3A432268e5831',
        '1inch_api': 'https://api.1inch.dev/swap/v6.0/42161',
    },
    'bsc': {
        'chain_id': 56,
        'rpc': 'https://bsc-dataseed.binance.org',
        'native': 'BNB',
        'wrapped': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c',  # WBNB
        'usdc': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d',  # USDC on BSC
        '1inch_api': 'https://api.1inch.dev/swap/v6.0/56',
    },
}

# 1inch API key (free tier)
ONEINCH_API_KEY = os.environ.get('ONEINCH_API_KEY', '')

# Slippage tolerance (1% default)
DEFAULT_SLIPPAGE = 1

# Gas reserve - always keep this amount of native token for gas
GAS_RESERVE_ETH = 0.005  # ~$15-20 at current prices
GAS_RESERVE_WEI = int(GAS_RESERVE_ETH * 1e18)


def get_gas_balance(chain: str, wallet_address: str) -> Tuple[float, bool]:
    """
    Get gas balance and check if sufficient
    
    Returns:
        (balance_eth, has_enough_gas)
    """
    try:
        w3 = get_web3(chain)
        balance = w3.eth.get_balance(wallet_address)
        balance_eth = balance / 1e18
        has_enough = balance >= GAS_RESERVE_WEI
        return balance_eth, has_enough
    except Exception as e:
        print(f"❌ Error checking gas balance: {e}")
        return 0, False


def get_web3(chain: str) -> Web3:
    """Get Web3 instance for a chain"""
    config = CHAINS.get(chain)
    if not config:
        raise ValueError(f"Unknown chain: {chain}")
    
    w3 = Web3(Web3.HTTPProvider(config['rpc']))
    
    # Add PoA middleware for chains that need it
    if chain in ['bsc', 'polygon']:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    
    return w3


def get_token_address(symbol: str, chain: str) -> Optional[str]:
    """Get token contract address from symbol"""
    config = CHAINS.get(chain)
    if not config:
        return None
    
    # Common tokens
    symbol = symbol.upper()
    
    if symbol in ['ETH', 'BNB', 'MATIC']:
        return '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'  # Native token
    
    if symbol == 'WETH':
        return config['wrapped']
    
    if symbol in ['USDC', 'USDC.E']:
        return config['usdc']
    
    # For other tokens, we need to look up via API or have a mapping
    # TODO: Add token lookup via DexScreener or 1inch token list
    return None


def get_quote(
    chain: str,
    from_token: str,
    to_token: str,
    amount: int,  # In wei/smallest unit
) -> Optional[Dict]:
    """
    Get swap quote from 1inch
    
    Args:
        chain: Chain name (base, ethereum, etc.)
        from_token: Source token address
        to_token: Destination token address  
        amount: Amount in smallest unit (wei)
    
    Returns:
        Quote data or None
    """
    config = CHAINS.get(chain)
    if not config:
        return None
    
    headers = {}
    if ONEINCH_API_KEY:
        headers['Authorization'] = f'Bearer {ONEINCH_API_KEY}'
    
    try:
        resp = requests.get(
            f"{config['1inch_api']}/quote",
            params={
                'src': from_token,
                'dst': to_token,
                'amount': str(amount),
            },
            headers=headers,
            timeout=30
        )
        
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"❌ 1inch quote error: {resp.status_code} - {resp.text}")
            return None
            
    except Exception as e:
        print(f"❌ Quote error: {e}")
        return None


def get_swap_tx(
    chain: str,
    from_token: str,
    to_token: str,
    amount: int,
    from_address: str,
    slippage: float = DEFAULT_SLIPPAGE,
) -> Optional[Dict]:
    """
    Get swap transaction from 1inch
    
    Returns transaction data ready to sign
    """
    config = CHAINS.get(chain)
    if not config:
        return None
    
    headers = {}
    if ONEINCH_API_KEY:
        headers['Authorization'] = f'Bearer {ONEINCH_API_KEY}'
    
    try:
        resp = requests.get(
            f"{config['1inch_api']}/swap",
            params={
                'src': from_token,
                'dst': to_token,
                'amount': str(amount),
                'from': from_address,
                'slippage': slippage,
                'disableEstimate': 'true',  # We'll estimate ourselves
            },
            headers=headers,
            timeout=30
        )
        
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"❌ 1inch swap error: {resp.status_code} - {resp.text}")
            return None
            
    except Exception as e:
        print(f"❌ Swap error: {e}")
        return None


def execute_swap(
    chain: str,
    wallet_address: str,
    from_token: str,
    to_token: str,
    amount_wei: int,
    slippage: float = DEFAULT_SLIPPAGE,
) -> Tuple[bool, str, Optional[str]]:
    """
    Execute a real swap
    
    Args:
        chain: Chain name
        wallet_address: Wallet address
        from_token: Source token address
        to_token: Destination token address
        amount_wei: Amount in wei
        slippage: Slippage tolerance %
    
    Returns:
        (success, message, tx_hash)
    """
    # Check we have the private key
    if not has_private_key(wallet_address):
        return False, "❌ No private key stored for this wallet", None
    
    private_key = get_private_key(wallet_address)
    if not private_key:
        return False, "❌ Failed to decrypt private key", None
    
    # Get Web3
    try:
        w3 = get_web3(chain)
    except Exception as e:
        return False, f"❌ Failed to connect to {chain}: {e}", None
    
    # Check gas balance
    balance = w3.eth.get_balance(wallet_address)
    if balance == 0:
        return False, "❌ Wallet has no ETH for gas", None
    
    if balance < GAS_RESERVE_WEI:
        return False, f"❌ Insufficient gas reserve. Have {balance/1e18:.4f} ETH, need {GAS_RESERVE_ETH} ETH minimum", None
    
    # Estimate gas cost
    gas_price = w3.eth.gas_price
    estimated_gas_cost = gas_price * 500000  # ~500k gas for swap
    
    if balance - estimated_gas_cost < GAS_RESERVE_WEI:
        return False, f"❌ Gas reserve too low after tx. Have {balance/1e18:.4f} ETH, need ~{(estimated_gas_cost + GAS_RESERVE_WEI)/1e18:.4f} ETH", None
    
    # Get swap transaction
    swap_data = get_swap_tx(chain, from_token, to_token, amount_wei, wallet_address, slippage)
    if not swap_data or 'tx' not in swap_data:
        return False, "❌ Failed to get swap transaction from 1inch", None
    
    tx_data = swap_data['tx']
    
    # Build transaction
    tx = {
        'from': wallet_address,
        'to': Web3.to_checksum_address(tx_data['to']),
        'data': tx_data['data'],
        'value': int(tx_data.get('value', 0)),
        'gas': int(tx_data.get('gas', 500000)),
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(wallet_address),
        'chainId': CHAINS[chain]['chain_id'],
    }
    
    # Estimate gas (safer)
    try:
        estimated_gas = w3.eth.estimate_gas(tx)
        tx['gas'] = int(estimated_gas * 1.2)  # 20% buffer
    except Exception as e:
        print(f"⚠️ Gas estimation failed, using default: {e}")
    
    # Sign transaction
    try:
        signed = w3.eth.account.sign_transaction(tx, private_key)
    except Exception as e:
        return False, f"❌ Failed to sign transaction: {e}", None
    
    # Send transaction
    try:
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        print(f"📤 Transaction sent: {tx_hash_hex}")
        
        # Wait for confirmation (max 60 seconds)
        print("⏳ Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        
        if receipt['status'] == 1:
            return True, f"✅ Swap successful!", tx_hash_hex
        else:
            return False, f"❌ Transaction failed", tx_hash_hex
            
    except Exception as e:
        return False, f"❌ Transaction error: {e}", None


def buy_token(
    chain: str,
    wallet_address: str,
    token_symbol: str,
    token_address: str,
    amount_usd: float,
    slippage: float = DEFAULT_SLIPPAGE,
) -> Tuple[bool, str, Optional[str]]:
    """
    Buy a token with USDC
    
    Args:
        chain: Chain name
        wallet_address: Wallet address
        token_symbol: Token symbol (for logging)
        token_address: Token contract address
        amount_usd: Amount in USD to spend
        slippage: Slippage tolerance
    
    Returns:
        (success, message, tx_hash)
    """
    config = CHAINS.get(chain)
    if not config:
        return False, f"❌ Unknown chain: {chain}", None
    
    usdc_address = config['usdc']
    
    # USDC has 6 decimals
    amount_wei = int(amount_usd * 1_000_000)
    
    print(f"🔄 Buying {token_symbol} with ${amount_usd} USDC on {chain}...")
    
    return execute_swap(
        chain=chain,
        wallet_address=wallet_address,
        from_token=usdc_address,
        to_token=token_address,
        amount_wei=amount_wei,
        slippage=slippage,
    )


def sell_token(
    chain: str,
    wallet_address: str,
    token_symbol: str,
    token_address: str,
    amount: float,
    decimals: int = 18,
    slippage: float = DEFAULT_SLIPPAGE,
) -> Tuple[bool, str, Optional[str]]:
    """
    Sell a token for USDC
    
    Args:
        chain: Chain name
        wallet_address: Wallet address
        token_symbol: Token symbol
        token_address: Token contract address
        amount: Amount of tokens to sell
        decimals: Token decimals
        slippage: Slippage tolerance
    
    Returns:
        (success, message, tx_hash)
    """
    config = CHAINS.get(chain)
    if not config:
        return False, f"❌ Unknown chain: {chain}", None
    
    usdc_address = config['usdc']
    amount_wei = int(amount * (10 ** decimals))
    
    print(f"🔄 Selling {amount} {token_symbol} for USDC on {chain}...")
    
    return execute_swap(
        chain=chain,
        wallet_address=wallet_address,
        from_token=token_address,
        to_token=usdc_address,
        amount_wei=amount_wei,
        slippage=slippage,
    )


if __name__ == '__main__':
    # Test
    print("🔄 Real Trader Test")
    
    # Test quote
    quote = get_quote(
        chain='base',
        from_token='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',  # USDC
        to_token='0x4200000000000000000000000000000000000006',   # WETH
        amount=1000000,  # 1 USDC
    )
    
    if quote:
        print(f"✅ Quote: {quote.get('toAmount')} WETH for 1 USDC")
    else:
        print("❌ Quote failed (may need API key)")
