"""
Real Trading Module - Execute actual trades on DEX via 1inch API
"""
import os
import json
import time
import requests
from web3 import Web3
from eth_account import Account
from typing import Optional, Dict, Any
from pathlib import Path

# Paraswap API (free, works on Base)
PARASWAP_API = "https://apiv5.paraswap.io"

# Aerodrome Router on Base (Uniswap V2 style)
AERODROME_ROUTER = "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43"
AERODROME_FACTORY = "0x420DD381b31aEf6683db6B902084cB0FFECe40Da"

# Aerodrome Slipstream (CL/Concentrated Liquidity) - Uniswap V3 style
SLIPSTREAM_ROUTER = "0xBE6D8f0d05cC4be24d5167a3eF062215bE6D18a5"
SLIPSTREAM_QUOTER = "0x254cF9E1E6e233aa1AC962CB9B05b2cfeAaE15b0"

# Chain IDs
CHAIN_IDS = {
    "ethereum": 1,
    "base": 8453,
    "arbitrum": 42161,
    "polygon": 137,
    "optimism": 10,
}

# RPC endpoints (public)
RPC_ENDPOINTS = {
    "ethereum": "https://eth.llamarpc.com",
    "base": "https://mainnet.base.org",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "polygon": "https://polygon-rpc.com",
    "optimism": "https://mainnet.optimism.io",
}

# Native token addresses (ETH represented as this address in 1inch)
NATIVE_TOKEN = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

# Common token addresses by chain
TOKEN_ADDRESSES = {
    "base": {
        "ETH": NATIVE_TOKEN,
        "WETH": "0x4200000000000000000000000000000000000006",
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "BRETT": "0x532f27101965dd16442E59d40670FaF5eBB142E4",
    },
    "ethereum": {
        "ETH": NATIVE_TOKEN,
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    },
}

# Aerodrome Router ABI (minimal)
AERODROME_ROUTER_ABI = [
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "routes", "type": "tuple[]", "components": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "stable", "type": "bool"},
                {"name": "factory", "type": "address"}
            ]},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "routes", "type": "tuple[]", "components": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "stable", "type": "bool"},
                {"name": "factory", "type": "address"}
            ]},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "routes", "type": "tuple[]", "components": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "stable", "type": "bool"},
                {"name": "factory", "type": "address"}
            ]},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForETH",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "routes", "type": "tuple[]", "components": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "stable", "type": "bool"},
                {"name": "factory", "type": "address"}
            ]}
        ],
        "name": "getAmountsOut",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Slipstream Quoter ABI (for CL pools) - uses tuple params
SLIPSTREAM_QUOTER_ABI = [
    {
        "inputs": [{
            "components": [
                {"name": "tokenIn", "type": "address"},
                {"name": "tokenOut", "type": "address"},
                {"name": "amountIn", "type": "uint256"},
                {"name": "tickSpacing", "type": "int24"},
                {"name": "sqrtPriceLimitX96", "type": "uint160"}
            ],
            "name": "params",
            "type": "tuple"
        }],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "sqrtPriceX96After", "type": "uint160"},
            {"name": "initializedTicksCrossed", "type": "uint32"},
            {"name": "gasEstimate", "type": "uint256"}
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# Slipstream Router ABI (for CL swaps)
SLIPSTREAM_ROUTER_ABI = [
    {
        "inputs": [{
            "components": [
                {"name": "tokenIn", "type": "address"},
                {"name": "tokenOut", "type": "address"},
                {"name": "tickSpacing", "type": "int24"},
                {"name": "recipient", "type": "address"},
                {"name": "deadline", "type": "uint256"},
                {"name": "amountIn", "type": "uint256"},
                {"name": "amountOutMinimum", "type": "uint256"},
                {"name": "sqrtPriceLimitX96", "type": "uint160"}
            ],
            "name": "params",
            "type": "tuple"
        }],
        "name": "exactInputSingle",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "amountMinimum", "type": "uint256"}],
        "name": "unwrapWETH9",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    }
]


class RealTrader:
    """Execute real trades on DEX via Paraswap aggregator"""
    
    def __init__(self, chain: str = "base", private_key: Optional[str] = None):
        self.chain = chain.lower()
        self.chain_id = CHAIN_IDS.get(self.chain)
        self.rpc_url = RPC_ENDPOINTS.get(self.chain)
        
        if not self.chain_id:
            raise ValueError(f"Chain {chain} not supported. Available: {list(CHAIN_IDS.keys())}")
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        # Load private key
        self.private_key = private_key
        self.account = None
        self.address = None
        if private_key:
            self.account = Account.from_key(private_key)
            self.address = self.account.address
        
    def get_headers(self) -> Dict[str, str]:
        """Get headers for Paraswap API requests"""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    
    def get_token_address(self, symbol: str) -> Optional[str]:
        """Get token contract address from symbol"""
        chain_tokens = TOKEN_ADDRESSES.get(self.chain, {})
        
        # Check known tokens
        if symbol.upper() in chain_tokens:
            return chain_tokens[symbol.upper()]
        
        # For unknown tokens, we need to look up the address
        # This would require a token registry or API call
        return None
    
    def get_quote(self, from_token: str, to_token: str, amount_wei: int, 
                  src_decimals: int = 18, dst_decimals: int = 18) -> Optional[Dict]:
        """
        Get a swap quote from Paraswap
        
        Args:
            from_token: Token address to sell
            to_token: Token address to buy
            amount_wei: Amount in smallest unit
            src_decimals: Source token decimals
            dst_decimals: Destination token decimals
        
        Returns:
            Quote data or None if failed
        """
        url = f"{PARASWAP_API}/prices"
        params = {
            "srcToken": from_token,
            "destToken": to_token,
            "amount": str(amount_wei),
            "srcDecimals": src_decimals,
            "destDecimals": dst_decimals,
            "network": self.chain_id,
            "side": "SELL",
        }
        
        try:
            resp = requests.get(url, params=params, headers=self.get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                price_route = data.get('priceRoute', {})
                return {
                    'dstAmount': price_route.get('destAmount', '0'),
                    'srcAmount': price_route.get('srcAmount', str(amount_wei)),
                    'gasCost': price_route.get('gasCost', '0'),
                    'priceRoute': price_route,
                    'raw': data,
                }
            else:
                print(f"Quote error: {resp.status_code} - {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"Quote request failed: {e}")
            return None
    
    def get_swap_data(self, from_token: str, to_token: str, amount_wei: int, 
                      slippage: float = 1.0, src_decimals: int = 18, 
                      dst_decimals: int = 18) -> Optional[Dict]:
        """
        Get swap transaction data from Paraswap
        
        Args:
            from_token: Token address to sell
            to_token: Token address to buy
            amount_wei: Amount in smallest unit
            slippage: Slippage tolerance in percent (default 1%)
        
        Returns:
            Swap transaction data or None
        """
        if not self.account:
            raise ValueError("Private key required for swap")
        
        # First get price quote
        quote = self.get_quote(from_token, to_token, amount_wei, src_decimals, dst_decimals)
        if not quote or 'priceRoute' not in quote:
            return None
        
        price_route = quote['priceRoute']
        
        # Build transaction via Paraswap
        url = f"{PARASWAP_API}/transactions/{self.chain_id}"
        
        # Calculate minimum dest amount with slippage
        dest_amount = int(price_route.get('destAmount', 0))
        min_dest = int(dest_amount * (1 - slippage / 100))
        
        body = {
            "srcToken": from_token,
            "destToken": to_token,
            "srcAmount": str(amount_wei),
            "destAmount": str(min_dest),
            "priceRoute": price_route,
            "userAddress": self.address,
            "partner": "openclaw",
            "srcDecimals": src_decimals,
            "destDecimals": dst_decimals,
        }
        
        try:
            resp = requests.post(url, json=body, headers=self.get_headers(), timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'tx': {
                        'to': data.get('to'),
                        'data': data.get('data'),
                        'value': data.get('value', '0'),
                        'gas': data.get('gas'),
                        'gasPrice': data.get('gasPrice'),
                    },
                    'dstAmount': str(dest_amount),
                    'minDstAmount': str(min_dest),
                    'allowanceTarget': price_route.get('tokenTransferProxy'),
                    'raw': data,
                }
            else:
                print(f"Swap data error: {resp.status_code} - {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"Swap request failed: {e}")
            return None
    
    def approve_token(self, token_address: str, spender: str, amount: int) -> Optional[str]:
        """
        Approve token spending (required before swap for ERC20 tokens)
        
        Returns:
            Transaction hash or None
        """
        if not self.account:
            raise ValueError("Private key required")
        
        if token_address.lower() == NATIVE_TOKEN.lower():
            # Native ETH doesn't need approval
            return "native_no_approval_needed"
        
        # ERC20 approve ABI
        approve_abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "spender", "type": "address"},
                    {"name": "amount", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]
        
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=approve_abi
        )
        
        # Build transaction
        nonce = self.w3.eth.get_transaction_count(self.address)
        gas_price = self.w3.eth.gas_price
        
        tx = contract.functions.approve(
            Web3.to_checksum_address(spender),
            amount
        ).build_transaction({
            'from': self.address,
            'nonce': nonce,
            'gasPrice': gas_price,
            'chainId': self.chain_id,
        })
        
        # Estimate gas
        tx['gas'] = self.w3.eth.estimate_gas(tx)
        
        # Sign and send
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        
        return tx_hash.hex()
    
    def execute_swap(self, from_token: str, to_token: str, amount_wei: int,
                     slippage: float = 1.0, wait_for_receipt: bool = True,
                     src_decimals: int = 18, dst_decimals: int = 18) -> Dict[str, Any]:
        """
        Execute a token swap via Paraswap
        
        Args:
            from_token: Token address to sell
            to_token: Token address to buy  
            amount_wei: Amount in smallest unit
            slippage: Slippage tolerance percent
            wait_for_receipt: Wait for transaction confirmation
            src_decimals: Source token decimals
            dst_decimals: Destination token decimals
        
        Returns:
            Result dict with status, tx_hash, etc.
        """
        result = {
            "success": False,
            "tx_hash": None,
            "error": None,
            "amount_out": None,
            "allowance_target": None,
        }
        
        if not self.account:
            result["error"] = "Private key not configured"
            return result
        
        # Get swap data from Paraswap
        swap_data = self.get_swap_data(from_token, to_token, amount_wei, slippage, 
                                        src_decimals, dst_decimals)
        if not swap_data or "tx" not in swap_data:
            result["error"] = "Failed to get swap data from Paraswap"
            return result
        
        tx_data = swap_data["tx"]
        result["allowance_target"] = swap_data.get("allowanceTarget")
        
        # Handle approval for ERC20 tokens (not ETH)
        if from_token.lower() != NATIVE_TOKEN.lower() and swap_data.get("allowanceTarget"):
            try:
                # Approve max amount to avoid repeated approvals
                max_approval = 2**256 - 1
                approval_tx = self.approve_token(from_token, swap_data["allowanceTarget"], max_approval)
                if approval_tx and approval_tx != "native_no_approval_needed":
                    print(f"Approval tx: {approval_tx}")
                    # Wait for approval to confirm
                    self.w3.eth.wait_for_transaction_receipt(approval_tx, timeout=60)
                    time.sleep(2)  # Extra buffer
            except Exception as e:
                print(f"Approval warning: {e}")
        
        try:
            # Build transaction
            tx = {
                'from': self.address,
                'to': Web3.to_checksum_address(tx_data['to']),
                'data': tx_data['data'],
                'value': int(tx_data.get('value', 0)),
                'nonce': self.w3.eth.get_transaction_count(self.address),
                'gasPrice': int(tx_data.get('gasPrice') or self.w3.eth.gas_price),
                'chainId': self.chain_id,
            }
            
            # Use gas from Paraswap or estimate
            if tx_data.get('gas'):
                tx['gas'] = int(int(tx_data['gas']) * 1.3)  # 30% buffer for safety
            else:
                tx['gas'] = int(self.w3.eth.estimate_gas(tx) * 1.3)
            
            # Sign and send
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            result["tx_hash"] = tx_hash.hex()
            
            if wait_for_receipt:
                # Wait for confirmation (max 90 seconds)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
                result["success"] = receipt['status'] == 1
                result["gas_used"] = receipt['gasUsed']
                result["block_number"] = receipt['blockNumber']
            else:
                result["success"] = True  # Assume success, actual status unknown
            
            # Get estimated output from swap data
            if "dstAmount" in swap_data:
                result["amount_out"] = swap_data["dstAmount"]
                
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def get_eth_balance(self) -> float:
        """Get ETH balance in ether"""
        if not self.address:
            return 0.0
        balance_wei = self.w3.eth.get_balance(self.address)
        return float(self.w3.from_wei(balance_wei, 'ether'))
    
    def get_token_balance(self, token_address: str, decimals: int = 18) -> float:
        """Get ERC20 token balance"""
        if not self.address:
            return 0.0
        
        if token_address.lower() == NATIVE_TOKEN.lower():
            return self.get_eth_balance()
        
        # ERC20 balanceOf ABI
        balance_abi = [
            {
                "constant": True,
                "inputs": [{"name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }
        ]
        
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=balance_abi
        )
        
        balance = contract.functions.balanceOf(self.address).call()
        return balance / (10 ** decimals)


class AerodromeTrader:
    """Execute trades on Aerodrome DEX (Base chain native AMM)"""
    
    def __init__(self, private_key: Optional[str] = None):
        self.chain = "base"
        self.chain_id = 8453
        self.rpc_url = RPC_ENDPOINTS["base"]
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        self.private_key = private_key
        self.account = None
        self.address = None
        if private_key:
            self.account = Account.from_key(private_key)
            self.address = self.account.address
        
        # Router contract
        self.router = self.w3.eth.contract(
            address=Web3.to_checksum_address(AERODROME_ROUTER),
            abi=AERODROME_ROUTER_ABI
        )
        
        self.weth = TOKEN_ADDRESSES["base"]["WETH"]
        self.usdc = TOKEN_ADDRESSES["base"]["USDC"]
        self.factory = AERODROME_FACTORY
        
        # Slipstream (CL) contracts
        self.cl_router = self.w3.eth.contract(
            address=Web3.to_checksum_address(SLIPSTREAM_ROUTER),
            abi=SLIPSTREAM_ROUTER_ABI
        )
        self.cl_quoter = self.w3.eth.contract(
            address=Web3.to_checksum_address(SLIPSTREAM_QUOTER),
            abi=SLIPSTREAM_QUOTER_ABI
        )
    
    def get_token_decimals(self, token_address: str) -> int:
        """Get token decimals"""
        if token_address.lower() == NATIVE_TOKEN.lower():
            return 18
        try:
            abi = [{"inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"}]
            contract = self.w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=abi)
            return contract.functions.decimals().call()
        except:
            return 18
    
    def get_cl_quote(self, amount_in: int, from_token: str, to_token: str, 
                     tick_spacing: int = 200) -> Optional[int]:
        """Get quote from Slipstream (CL) pools"""
        try:
            # Try to call quoteExactInputSingle
            # We use call() but catch any revert to try different tick spacings
            result = self.cl_quoter.functions.quoteExactInputSingle(
                Web3.to_checksum_address(from_token),
                Web3.to_checksum_address(to_token),
                tick_spacing,
                amount_in,
                0  # sqrtPriceLimitX96 = 0 means no limit
            ).call()
            return result[0] if result else None
        except Exception as e:
            # Try other common tick spacings (1, 50, 100, 200)
            if tick_spacing == 200:
                for ts in [100, 50, 1]:
                    try:
                        result = self.cl_quoter.functions.quoteExactInputSingle(
                            Web3.to_checksum_address(from_token),
                            Web3.to_checksum_address(to_token),
                            ts,
                            amount_in,
                            0
                        ).call()
                        if result and result[0] > 0:
                            return result[0]
                    except:
                        continue
            print(f"CL quote failed: {e}")
            return None
    
    def swap_eth_for_tokens_cl(self, token_address: str, amount_eth_wei: int,
                                tick_spacing: int = 200, slippage: float = 3.0) -> Dict[str, Any]:
        """Swap ETH for tokens on Slipstream (CL) pools"""
        result = {"success": False, "tx_hash": None, "error": None, "amount_out": None}
        
        if not self.account:
            result["error"] = "Private key required"
            return result
        
        try:
            # Get quote first
            expected_out = self.get_cl_quote(amount_eth_wei, self.weth, token_address, tick_spacing)
            if not expected_out or expected_out == 0:
                result["error"] = "Could not get CL quote"
                return result
            
            min_out = int(expected_out * (1 - slippage / 100))
            deadline = int(time.time()) + 300
            
            # Build swap params
            params = (
                Web3.to_checksum_address(self.weth),
                Web3.to_checksum_address(token_address),
                tick_spacing,
                self.address,
                deadline,
                amount_eth_wei,
                min_out,
                0  # sqrtPriceLimitX96 = 0
            )
            
            nonce = self.w3.eth.get_transaction_count(self.address)
            gas_price = self.w3.eth.gas_price
            
            tx = self.cl_router.functions.exactInputSingle(params).build_transaction({
                'from': self.address,
                'value': amount_eth_wei,
                'nonce': nonce,
                'gasPrice': gas_price,
                'chainId': self.chain_id,
            })
            
            tx['gas'] = int(self.w3.eth.estimate_gas(tx) * 1.3)
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            result["tx_hash"] = tx_hash.hex()
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
            result["success"] = receipt['status'] == 1
            result["amount_out"] = str(expected_out)
            result["gas_used"] = receipt['gasUsed']
            result["pool_type"] = "CL"
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def get_amounts_out(self, amount_in: int, from_token: str, to_token: str, 
                        via_usdc: bool = False) -> Optional[int]:
        """Get expected output amount for a swap"""
        try:
            from_addr = Web3.to_checksum_address(from_token)
            to_addr = Web3.to_checksum_address(to_token)
            
            if via_usdc:
                # Multi-hop: from -> USDC -> to
                route = [
                    (from_addr, Web3.to_checksum_address(self.usdc), False, Web3.to_checksum_address(self.factory)),
                    (Web3.to_checksum_address(self.usdc), to_addr, False, Web3.to_checksum_address(self.factory)),
                ]
            else:
                # Direct route
                route = [(from_addr, to_addr, False, Web3.to_checksum_address(self.factory))]
            
            amounts = self.router.functions.getAmountsOut(amount_in, route).call()
            return amounts[-1] if amounts else None
        except Exception as e:
            # Try via USDC if direct failed and we haven't tried yet
            if not via_usdc:
                return self.get_amounts_out(amount_in, from_token, to_token, via_usdc=True)
            print(f"Aerodrome getAmountsOut failed: {e}")
            return None
    
    def approve_token(self, token_address: str, amount: int) -> Optional[str]:
        """Approve Aerodrome router to spend tokens"""
        if not self.account:
            raise ValueError("Private key required")
        
        approve_abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "spender", "type": "address"},
                    {"name": "amount", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]
        
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=approve_abi
        )
        
        nonce = self.w3.eth.get_transaction_count(self.address)
        gas_price = self.w3.eth.gas_price
        
        tx = contract.functions.approve(
            Web3.to_checksum_address(AERODROME_ROUTER),
            amount
        ).build_transaction({
            'from': self.address,
            'nonce': nonce,
            'gasPrice': gas_price,
            'chainId': self.chain_id,
        })
        
        tx['gas'] = self.w3.eth.estimate_gas(tx)
        
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        
        return tx_hash.hex()
    
    def swap_eth_for_tokens(self, token_address: str, amount_eth_wei: int, 
                            slippage: float = 3.0) -> Dict[str, Any]:
        """Swap ETH for tokens on Aerodrome (tries V2 pools, then CL/Slipstream)"""
        result = {"success": False, "tx_hash": None, "error": None, "amount_out": None}
        
        if not self.account:
            result["error"] = "Private key required"
            return result
        
        to_addr = Web3.to_checksum_address(token_address)
        
        # Try V2 pools first (direct, then via USDC)
        try:
            expected_out = self.get_amounts_out(amount_eth_wei, self.weth, token_address, via_usdc=False)
            use_usdc = False
            
            if not expected_out or expected_out == 0:
                expected_out = self.get_amounts_out(amount_eth_wei, self.weth, token_address, via_usdc=True)
                use_usdc = True
            
            if expected_out and expected_out > 0:
                # V2 pool found - execute swap
                min_out = int(expected_out * (1 - slippage / 100))
                deadline = int(time.time()) + 300
                
                if use_usdc:
                    route = [
                        (Web3.to_checksum_address(self.weth), Web3.to_checksum_address(self.usdc), False, Web3.to_checksum_address(self.factory)),
                        (Web3.to_checksum_address(self.usdc), to_addr, False, Web3.to_checksum_address(self.factory)),
                    ]
                    print(f"V2: WETH -> USDC -> Token route")
                else:
                    route = [(Web3.to_checksum_address(self.weth), to_addr, False, Web3.to_checksum_address(self.factory))]
                    print(f"V2: Direct WETH -> Token route")
                
                nonce = self.w3.eth.get_transaction_count(self.address)
                gas_price = self.w3.eth.gas_price
                
                tx = self.router.functions.swapExactETHForTokens(
                    min_out,
                    route,
                    self.address,
                    deadline
                ).build_transaction({
                    'from': self.address,
                    'value': amount_eth_wei,
                    'nonce': nonce,
                    'gasPrice': gas_price,
                    'chainId': self.chain_id,
                })
                
                tx['gas'] = int(self.w3.eth.estimate_gas(tx) * 1.3)
                
                signed = self.account.sign_transaction(tx)
                tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
                result["tx_hash"] = tx_hash.hex()
                
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
                result["success"] = receipt['status'] == 1
                result["amount_out"] = str(expected_out)
                result["gas_used"] = receipt['gasUsed']
                result["pool_type"] = "V2"
                result["decimals"] = self.get_token_decimals(token_address)
                return result
                
        except Exception as e:
            print(f"V2 swap failed: {e}")
        
        # Try CL/Slipstream pools
        print("Trying Slipstream (CL) pools...")
        return self.swap_eth_for_tokens_cl(token_address, amount_eth_wei, 200, slippage)
    
    def swap_tokens_for_eth(self, token_address: str, amount_tokens: int,
                            slippage: float = 3.0) -> Dict[str, Any]:
        """Swap tokens for ETH on Aerodrome (tries direct, then via USDC)"""
        result = {"success": False, "tx_hash": None, "error": None, "amount_out": None}
        
        if not self.account:
            result["error"] = "Private key required"
            return result
        
        try:
            from_addr = Web3.to_checksum_address(token_address)
            
            # Approve router first
            max_approval = 2**256 - 1
            approval_tx = self.approve_token(token_address, max_approval)
            print(f"Aerodrome approval tx: {approval_tx}")
            self.w3.eth.wait_for_transaction_receipt(approval_tx, timeout=60)
            time.sleep(2)
            
            # Try direct route first
            expected_out = self.get_amounts_out(amount_tokens, token_address, self.weth, via_usdc=False)
            use_usdc = False
            
            if not expected_out or expected_out == 0:
                expected_out = self.get_amounts_out(amount_tokens, token_address, self.weth, via_usdc=True)
                use_usdc = True
            
            if not expected_out or expected_out == 0:
                result["error"] = "Could not get quote from Aerodrome"
                return result
            
            min_out = int(expected_out * (1 - slippage / 100))
            deadline = int(time.time()) + 300
            
            # Build route
            if use_usdc:
                route = [
                    (from_addr, Web3.to_checksum_address(self.usdc), False, Web3.to_checksum_address(self.factory)),
                    (Web3.to_checksum_address(self.usdc), Web3.to_checksum_address(self.weth), False, Web3.to_checksum_address(self.factory)),
                ]
                print(f"Using Token -> USDC -> WETH route")
            else:
                route = [(from_addr, Web3.to_checksum_address(self.weth), False, Web3.to_checksum_address(self.factory))]
                print(f"Using direct Token -> WETH route")
            
            nonce = self.w3.eth.get_transaction_count(self.address)
            gas_price = self.w3.eth.gas_price
            
            tx = self.router.functions.swapExactTokensForETH(
                amount_tokens,
                min_out,
                route,
                self.address,
                deadline
            ).build_transaction({
                'from': self.address,
                'nonce': nonce,
                'gasPrice': gas_price,
                'chainId': self.chain_id,
            })
            
            tx['gas'] = int(self.w3.eth.estimate_gas(tx) * 1.3)
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            result["tx_hash"] = tx_hash.hex()
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
            result["success"] = receipt['status'] == 1
            result["amount_out"] = str(expected_out)
            result["gas_used"] = receipt['gasUsed']
            
        except Exception as e:
            result["error"] = str(e)
        
        return result


def load_private_key(wallet_id: str, password: str) -> Optional[str]:
    """
    Load encrypted private key for a wallet
    
    Keys are stored in data/wallet_keys.enc (encrypted with password)
    """
    keys_file = Path(__file__).parent.parent / "data" / "wallet_keys.enc"
    
    if not keys_file.exists():
        return None
    
    try:
        # Simple encryption using Fernet (symmetric)
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        import base64
        
        # Derive key from password
        salt = b"crypto_trader_salt_v1"  # Fixed salt (acceptable for this use case)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        fernet = Fernet(key)
        
        # Decrypt keys file
        with open(keys_file, 'rb') as f:
            encrypted = f.read()
        
        decrypted = fernet.decrypt(encrypted)
        keys_data = json.loads(decrypted.decode())
        
        return keys_data.get(wallet_id)
        
    except Exception as e:
        print(f"Failed to load private key: {e}")
        return None


def save_private_key(wallet_id: str, private_key: str, password: str):
    """
    Save encrypted private key for a wallet
    """
    keys_file = Path(__file__).parent.parent / "data" / "wallet_keys.enc"
    
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64
    
    # Derive key from password
    salt = b"crypto_trader_salt_v1"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    fernet = Fernet(key)
    
    # Load existing keys or create new
    keys_data = {}
    if keys_file.exists():
        try:
            with open(keys_file, 'rb') as f:
                encrypted = f.read()
            decrypted = fernet.decrypt(encrypted)
            keys_data = json.loads(decrypted.decode())
        except:
            pass  # Start fresh if decryption fails
    
    # Add/update key
    keys_data[wallet_id] = private_key
    
    # Encrypt and save
    encrypted = fernet.encrypt(json.dumps(keys_data).encode())
    keys_file.parent.mkdir(parents=True, exist_ok=True)
    with open(keys_file, 'wb') as f:
        f.write(encrypted)


# ============ High-level trading functions ============

def get_eth_price_usd() -> float:
    """Get ETH price in USD from CMC"""
    try:
        cmc_key = os.environ.get('CMC_API_KEY', '849ddcc694a049708d0b5392486d6eaa')
        resp = requests.get(
            'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest',
            headers={'X-CMC_PRO_API_KEY': cmc_key},
            params={'symbol': 'ETH', 'convert': 'USD'},
            timeout=10
        )
        data = resp.json()
        return data['data']['ETH']['quote']['USD']['price']
    except:
        return 2500  # Fallback


def buy_token(chain: str, wallet_address: str, token_symbol: str, 
              token_address: str, amount_usd: float, use_aerodrome: bool = False) -> tuple:
    """
    Buy a token with ETH (Paraswap first, Aerodrome fallback on Base)
    
    Args:
        chain: Chain name (base, ethereum, etc.)
        wallet_address: Wallet address (0x...)
        token_symbol: Token symbol for logging
        token_address: Token contract address
        amount_usd: Amount in USD to spend
        use_aerodrome: Force Aerodrome (skip Paraswap)
    
    Returns:
        (success: bool, message: str, tx_hash: str or None)
    """
    try:
        # Load private key from wallet_keys module
        from utils.wallet_keys import get_private_key
        private_key = get_private_key(wallet_address)
        if not private_key:
            return False, "Private key not found", None
        
        # Add 0x prefix if missing
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        # Calculate ETH amount needed
        eth_price = get_eth_price_usd()
        eth_amount = amount_usd / eth_price
        
        # Check balance first
        trader = RealTrader(chain=chain, private_key=private_key)
        amount_wei = trader.w3.to_wei(eth_amount, 'ether')
        balance = trader.w3.eth.get_balance(trader.address)
        if balance < amount_wei:
            eth_balance = float(trader.w3.from_wei(balance, 'ether'))
            return False, f"Insufficient ETH: {eth_balance:.4f} < {eth_amount:.4f}", None
        
        # Try Paraswap first (unless forced Aerodrome or not Base)
        if not use_aerodrome and chain.lower() == "base":
            result = trader.execute_swap(
                from_token=NATIVE_TOKEN,
                to_token=token_address,
                amount_wei=amount_wei,
                slippage=2.0,
            )
            
            if result['success']:
                return True, f"Bought {token_symbol} for {eth_amount:.4f} ETH (${amount_usd:.2f}) via Paraswap", result['tx_hash']
            
            # Paraswap failed - try Aerodrome
            print(f"Paraswap failed: {result.get('error')}, trying Aerodrome...")
        
        # Aerodrome fallback (Base only)
        if chain.lower() == "base":
            aero = AerodromeTrader(private_key=private_key)
            result = aero.swap_eth_for_tokens(token_address, amount_wei, slippage=3.0)
            
            if result['success']:
                return True, f"Bought {token_symbol} for {eth_amount:.4f} ETH (${amount_usd:.2f}) via Aerodrome", result['tx_hash']
            else:
                return False, f"Aerodrome failed: {result.get('error')}", result.get('tx_hash')
        
        return False, "Both Paraswap and Aerodrome failed", None
            
    except Exception as e:
        return False, f"Error: {str(e)}", None


def sell_token(chain: str, wallet_address: str, token_symbol: str,
               token_address: str, amount: float, use_aerodrome: bool = False) -> tuple:
    """
    Sell a token for ETH (Paraswap first, Aerodrome fallback on Base)
    
    Args:
        chain: Chain name
        wallet_address: Wallet address
        token_symbol: Token symbol
        token_address: Token contract address  
        amount: Amount of tokens to sell
        use_aerodrome: Force Aerodrome (skip Paraswap)
    
    Returns:
        (success: bool, message: str, tx_hash: str or None)
    """
    try:
        # Load private key from wallet_keys module
        from utils.wallet_keys import get_private_key
        private_key = get_private_key(wallet_address)
        if not private_key:
            return False, "Private key not found", None
        
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        trader = RealTrader(chain=chain, private_key=private_key)
        
        # Get token decimals (default 18)
        decimals = 18
        try:
            decimals_abi = [{"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"}]
            contract = trader.w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=decimals_abi)
            decimals = contract.functions.decimals().call()
        except:
            pass
        
        amount_wei = int(amount * (10 ** decimals))
        
        # Check token balance
        balance = trader.get_token_balance(token_address, decimals)
        if balance < amount:
            return False, f"Insufficient {token_symbol}: {balance:.4f} < {amount:.4f}", None
        
        # Try Paraswap first (unless forced Aerodrome or not Base)
        if not use_aerodrome and chain.lower() == "base":
            result = trader.execute_swap(
                from_token=token_address,
                to_token=NATIVE_TOKEN,
                amount_wei=amount_wei,
                slippage=2.0,
            )
            
            if result['success']:
                return True, f"Sold {amount:.4f} {token_symbol} via Paraswap", result['tx_hash']
            
            print(f"Paraswap sell failed: {result.get('error')}, trying Aerodrome...")
        
        # Aerodrome fallback (Base only)
        if chain.lower() == "base":
            aero = AerodromeTrader(private_key=private_key)
            result = aero.swap_tokens_for_eth(token_address, amount_wei, slippage=3.0)
            
            if result['success']:
                return True, f"Sold {amount:.4f} {token_symbol} via Aerodrome", result['tx_hash']
            else:
                return False, f"Aerodrome failed: {result.get('error')}", result.get('tx_hash')
        
        return False, "Both Paraswap and Aerodrome failed", None
            
    except Exception as e:
        return False, f"Error: {str(e)}", None


def get_quote(chain: str, from_token: str, to_token: str, amount_wei: int) -> Optional[Dict]:
    """Get a swap quote"""
    trader = RealTrader(chain=chain)
    return trader.get_quote(from_token, to_token, amount_wei)


if __name__ == "__main__":
    # Test basic functionality
    trader = RealTrader(chain="base")
    print(f"Connected to {trader.chain} via {trader.rpc_url}")
    print(f"Latest block: {trader.w3.eth.block_number}")
    
    # Test ETH price
    eth_price = get_eth_price_usd()
    print(f"ETH Price: ${eth_price:.2f}")
    
    # Test wallet balance
    test_address = "0xB99CD3209F66A76294eEdFc5068DdB258C9e2c67"
    balance = trader.w3.eth.get_balance(test_address)
    eth_balance = float(trader.w3.from_wei(balance, 'ether'))
    print(f"Balance: {eth_balance:.6f} ETH (${eth_balance * eth_price:.2f})")
