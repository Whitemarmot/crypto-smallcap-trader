"""
KyberSwap Aggregator for Base
Routes through all DEXs for best price
"""
import os
import time
import requests
from web3 import Web3
from eth_account import Account
from typing import Optional, Tuple, Dict, Any

KYBER_API = "https://aggregator-api.kyberswap.com/base/api/v1"
RPC_URL = "https://mainnet.base.org"
CHAIN_ID = 8453

# Common tokens
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH_BASE = "0x4200000000000000000000000000000000000006"


class KyberSwap:
    def __init__(self, private_key: Optional[str] = None):
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.account = None
        self.address = None
        
        if private_key:
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
            self.account = Account.from_key(private_key)
            self.address = self.account.address
    
    def get_quote(self, token_in: str, token_out: str, amount_in: int) -> Optional[Dict]:
        """
        Get swap quote from KyberSwap
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount in smallest unit
        
        Returns:
            Quote data or None
        """
        url = f"{KYBER_API}/routes"
        params = {
            "tokenIn": token_in,
            "tokenOut": token_out,
            "amountIn": str(amount_in),
            "saveGas": "false",
            "gasInclude": "true",
        }
        
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data") and data["data"].get("routeSummary"):
                    return data["data"]
            return None
        except Exception as e:
            print(f"Quote error: {e}")
            return None
    
    def build_swap(self, route_summary: Dict, slippage: float = 2.0) -> Optional[Dict]:
        """
        Build swap transaction from route
        
        Args:
            route_summary: Route summary from get_quote
            slippage: Slippage tolerance in percent
        
        Returns:
            Transaction data or None
        """
        if not self.address:
            return None
        
        url = f"{KYBER_API}/route/build"
        body = {
            "routeSummary": route_summary,
            "sender": self.address,
            "recipient": self.address,
            "slippageTolerance": int(slippage * 100),  # basis points
            "deadline": int(time.time()) + 300,
            "source": "openclaw",
        }
        
        try:
            resp = requests.post(url, json=body, timeout=15)
            if resp.status_code == 200:
                return resp.json().get("data")
            else:
                print(f"Build error: {resp.status_code} - {resp.text[:200]}")
            return None
        except Exception as e:
            print(f"Build error: {e}")
            return None
    
    def approve_token(self, token: str, spender: str, amount: int) -> Optional[str]:
        """Approve token for spending"""
        if not self.account:
            return None
        
        token = Web3.to_checksum_address(token)
        spender = Web3.to_checksum_address(spender)
        
        # Check current allowance
        allowance_abi = [
            {"constant": True, "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
            {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
        ]
        
        contract = self.w3.eth.contract(address=token, abi=allowance_abi)
        allowance = contract.functions.allowance(self.address, spender).call()
        
        if allowance >= amount:
            return "already_approved"
        
        # Approve max
        tx = contract.functions.approve(spender, 2**256 - 1).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 100000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': CHAIN_ID
        })
        
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        return tx_hash.hex()
    
    def execute_swap(self, token_in: str, token_out: str, amount_in: int,
                     slippage: float = 2.0) -> Dict[str, Any]:
        """
        Execute a swap via KyberSwap
        
        Returns:
            Result dict with success, tx_hash, amount_out, error
        """
        result = {
            "success": False,
            "tx_hash": None,
            "amount_out": None,
            "error": None,
        }
        
        if not self.account:
            result["error"] = "No private key"
            return result
        
        # Get quote
        quote = self.get_quote(token_in, token_out, amount_in)
        if not quote:
            result["error"] = "Failed to get quote"
            return result
        
        route_summary = quote.get("routeSummary", {})
        result["amount_out"] = route_summary.get("amountOut", "0")
        
        # Build swap tx
        swap_data = self.build_swap(route_summary, slippage)
        if not swap_data:
            result["error"] = "Failed to build swap"
            return result
        
        router = swap_data.get("routerAddress")
        tx_data = swap_data.get("data")
        
        if not router or not tx_data:
            result["error"] = "Invalid swap data"
            return result
        
        # Approve if needed (for non-ETH tokens)
        if token_in.lower() != "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
            approval = self.approve_token(token_in, router, amount_in)
            if approval and approval != "already_approved":
                self.w3.eth.wait_for_transaction_receipt(approval, timeout=60)
                time.sleep(2)
        
        try:
            # Build and send tx
            tx = {
                'from': self.address,
                'to': Web3.to_checksum_address(router),
                'data': tx_data,
                'value': int(swap_data.get("value", 0), 16) if isinstance(swap_data.get("value"), str) else int(swap_data.get("value", 0)),
                'nonce': self.w3.eth.get_transaction_count(self.address),
                'gas': int(swap_data.get("gas", 500000)),
                'gasPrice': self.w3.eth.gas_price,
                'chainId': CHAIN_ID
            }
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            result["tx_hash"] = tx_hash.hex()
            
            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
            result["success"] = receipt['status'] == 1
            result["gas_used"] = receipt['gasUsed']
            
        except Exception as e:
            result["error"] = str(e)
        
        return result


def buy_token_kyber(wallet_address: str, token_address: str, amount_usd: float,
                    use_usdc: bool = True) -> Tuple[bool, str, Optional[str], float]:
    """
    Buy a token using KyberSwap
    
    Args:
        wallet_address: Wallet address
        token_address: Token to buy
        amount_usd: Amount in USD
        use_usdc: If True, swap USDC. If False, swap ETH
    
    Returns:
        (success, message, tx_hash, amount_out)
    """
    from utils.wallet_keys import get_private_key
    
    private_key = get_private_key(wallet_address)
    if not private_key:
        return False, "Private key not found", None, 0
    
    kyber = KyberSwap(private_key)
    
    if use_usdc:
        token_in = USDC_BASE
        amount_in = int(amount_usd * 1e6)  # 6 decimals
    else:
        # ETH - get price first
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
        
        token_in = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        amount_in = int(amount_usd / eth_price * 1e18)
    
    # Execute swap
    result = kyber.execute_swap(token_in, token_address, amount_in)
    
    if result["success"]:
        amount_out = int(result.get("amount_out", 0)) / 1e18
        return True, f"Bought for ${amount_usd}", result["tx_hash"], amount_out
    else:
        return False, result.get("error", "Swap failed"), result.get("tx_hash"), 0


if __name__ == "__main__":
    print("KyberSwap module loaded")
    kyber = KyberSwap()
    
    # Test quote
    quote = kyber.get_quote(USDC_BASE, "0x940181a94A35A4569E4529A3CDfB74e38FD98631", 5000000)
    if quote:
        out = int(quote["routeSummary"]["amountOut"]) / 1e18
        print(f"5 USDC -> {out:.2f} AERO")
