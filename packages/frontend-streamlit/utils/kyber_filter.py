"""
Filter tokens tradable via KyberSwap
"""
import requests
from typing import List, Dict

KYBER_API = "https://aggregator-api.kyberswap.com/base/api/v1"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


def check_kyber_tradable(token_address: str, amount_usd: float = 5.0) -> bool:
    """Check if a token can be traded via KyberSwap"""
    try:
        url = f"{KYBER_API}/routes"
        params = {
            "tokenIn": USDC_BASE,
            "tokenOut": token_address,
            "amountIn": str(int(amount_usd * 1e6)),
        }
        
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data") and data["data"].get("routeSummary"):
                amount_out = int(data["data"]["routeSummary"].get("amountOut", 0))
                return amount_out > 0
        return False
    except:
        return False


def filter_kyber_tradable(tokens: List[Dict]) -> List[Dict]:
    """
    Filter a list of tokens to only those tradable via KyberSwap
    
    Args:
        tokens: List of token dicts with 'symbol' and 'dex_pair' containing 'base_token_address'
    
    Returns:
        Filtered list of tradable tokens
    """
    tradable = []
    
    for token in tokens:
        # Get token address from dex_pair
        dex_pair = token.get('dex_pair', {})
        if not dex_pair:
            continue
        
        # Try different address fields
        token_address = (
            dex_pair.get('base_token_address') or 
            dex_pair.get('baseToken', {}).get('address') or
            token.get('token_address')
        )
        
        if not token_address:
            continue
        
        symbol = token.get('symbol', 'UNKNOWN')
        
        if check_kyber_tradable(token_address):
            token['kyber_tradable'] = True
            tradable.append(token)
            print(f"  ✅ {symbol}: tradable via KyberSwap")
        else:
            print(f"  ❌ {symbol}: not tradable via KyberSwap")
    
    return tradable


if __name__ == "__main__":
    # Test
    test_tokens = [
        {"symbol": "BRETT", "dex_pair": {"base_token_address": "0x532f27101965dd16442E59d40670FaF5eBB142E4"}},
        {"symbol": "DEGEN", "dex_pair": {"base_token_address": "0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed"}},
        {"symbol": "AERO", "dex_pair": {"base_token_address": "0x940181a94A35A4569E4529A3CDfB74e38FD98631"}},
    ]
    
    print("Testing KyberSwap tradability...")
    tradable = filter_kyber_tradable(test_tokens)
    print(f"\n{len(tradable)}/{len(test_tokens)} tokens tradable")
