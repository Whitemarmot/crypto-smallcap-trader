"""
Aerodrome DEX Swap Module for Base
Direct swaps via Aerodrome Router
"""
import os
from web3 import Web3
from eth_account import Account
from typing import Optional, Tuple
import time

# Aerodrome Router on Base
AERODROME_ROUTER = "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43"

# WETH on Base (for ETH swaps)
WETH_BASE = "0x4200000000000000000000000000000000000006"

# Router ABI (minimal for swaps)
ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "tuple[]", "name": "routes", "type": "tuple[]", "components": [
                {"internalType": "address", "name": "from", "type": "address"},
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "bool", "name": "stable", "type": "bool"},
                {"internalType": "address", "name": "factory", "type": "address"}
            ]},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "tuple[]", "name": "routes", "type": "tuple[]", "components": [
                {"internalType": "address", "name": "from", "type": "address"},
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "bool", "name": "stable", "type": "bool"},
                {"internalType": "address", "name": "factory", "type": "address"}
            ]},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "tuple[]", "name": "routes", "type": "tuple[]", "components": [
                {"internalType": "address", "name": "from", "type": "address"},
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "bool", "name": "stable", "type": "bool"},
                {"internalType": "address", "name": "factory", "type": "address"}
            ]}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# ERC20 ABI for approvals
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"}
]

# Default factory (Aerodrome)
AERODROME_FACTORY = "0x420DD381b31aEf6683db6B902084cB0FFECe40Da"


class AerodromeSwap:
    def __init__(self, private_key: str):
        self.w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))
        self.account = Account.from_key(private_key)
        self.address = self.account.address
        self.router = self.w3.eth.contract(
            address=Web3.to_checksum_address(AERODROME_ROUTER),
            abi=ROUTER_ABI
        )
    
    def get_quote(self, token_in: str, token_out: str, amount_in: int, stable: bool = False) -> Optional[int]:
        """Get quote for swap"""
        try:
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            
            routes = [(token_in, token_out, stable, AERODROME_FACTORY)]
            amounts = self.router.functions.getAmountsOut(amount_in, routes).call()
            return amounts[-1]
        except Exception as e:
            print(f"Quote error: {e}")
            return None
    
    def approve_token(self, token: str, amount: int) -> Optional[str]:
        """Approve token for router"""
        token = Web3.to_checksum_address(token)
        contract = self.w3.eth.contract(address=token, abi=ERC20_ABI)
        
        # Check current allowance
        allowance = contract.functions.allowance(self.address, AERODROME_ROUTER).call()
        if allowance >= amount:
            return "already_approved"
        
        # Approve
        tx = contract.functions.approve(AERODROME_ROUTER, 2**256 - 1).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 100000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': 8453
        })
        
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        return tx_hash.hex()
    
    def swap_eth_for_tokens(self, token_out: str, amount_eth: float, slippage: float = 2.0) -> Tuple[bool, str, Optional[str]]:
        """Swap ETH for tokens"""
        try:
            token_out = Web3.to_checksum_address(token_out)
            amount_wei = self.w3.to_wei(amount_eth, 'ether')
            
            # Get quote via WETH
            routes = [(WETH_BASE, token_out, False, AERODROME_FACTORY)]
            amounts = self.router.functions.getAmountsOut(amount_wei, routes).call()
            amount_out_min = int(amounts[-1] * (1 - slippage / 100))
            
            deadline = int(time.time()) + 300  # 5 minutes
            
            tx = self.router.functions.swapExactETHForTokens(
                amount_out_min,
                routes,
                self.address,
                deadline
            ).build_transaction({
                'from': self.address,
                'value': amount_wei,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                'gas': 300000,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': 8453
            })
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            
            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt['status'] == 1:
                return True, f"Swapped {amount_eth} ETH", tx_hash.hex()
            else:
                return False, "Transaction failed", tx_hash.hex()
                
        except Exception as e:
            return False, str(e), None
    
    def swap_tokens(self, token_in: str, token_out: str, amount_in: int, 
                    slippage: float = 2.0, stable: bool = False) -> Tuple[bool, str, Optional[str]]:
        """Swap tokens for tokens"""
        try:
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            
            # Approve first
            approval = self.approve_token(token_in, amount_in)
            if approval and approval != "already_approved":
                self.w3.eth.wait_for_transaction_receipt(approval, timeout=60)
                time.sleep(2)
            
            # Get quote
            routes = [(token_in, token_out, stable, AERODROME_FACTORY)]
            amounts = self.router.functions.getAmountsOut(amount_in, routes).call()
            amount_out_min = int(amounts[-1] * (1 - slippage / 100))
            
            deadline = int(time.time()) + 300
            
            tx = self.router.functions.swapExactTokensForTokens(
                amount_in,
                amount_out_min,
                routes,
                self.address,
                deadline
            ).build_transaction({
                'from': self.address,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                'gas': 300000,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': 8453
            })
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt['status'] == 1:
                return True, "Swap successful", tx_hash.hex()
            else:
                return False, "Transaction failed", tx_hash.hex()
                
        except Exception as e:
            return False, str(e), None


def buy_token_aerodrome(wallet_address: str, token_address: str, amount_usd: float, 
                        use_usdc: bool = True) -> Tuple[bool, str, Optional[str]]:
    """
    Buy a token using Aerodrome DEX
    
    Args:
        wallet_address: Wallet address
        token_address: Token to buy
        amount_usd: Amount in USD
        use_usdc: If True, swap USDC->Token. If False, swap ETH->Token
    
    Returns:
        (success, message, tx_hash)
    """
    from utils.wallet_keys import get_private_key
    
    private_key = get_private_key(wallet_address)
    if not private_key:
        return False, "Private key not found", None
    
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key
    
    swap = AerodromeSwap(private_key)
    
    if use_usdc:
        # USDC -> Token
        usdc_address = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
        amount_wei = int(amount_usd * 1e6)  # USDC has 6 decimals
        
        return swap.swap_tokens(usdc_address, token_address, amount_wei)
    else:
        # ETH -> Token (need ETH price)
        import requests
        try:
            resp = requests.get(
                'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest',
                headers={'X-CMC_PRO_API_KEY': os.environ.get('CMC_API_KEY', '849ddcc694a049708d0b5392486d6eaa')},
                params={'symbol': 'ETH'}, timeout=10
            )
            eth_price = resp.json()['data']['ETH']['quote']['USD']['price']
        except:
            eth_price = 2400
        
        amount_eth = amount_usd / eth_price
        return swap.swap_eth_for_tokens(token_address, amount_eth)


if __name__ == "__main__":
    # Test
    print("Aerodrome Swap Module loaded")
    swap = AerodromeSwap("0x" + "0" * 64)  # Dummy key for testing
    print(f"Router: {AERODROME_ROUTER}")
