"""
🔄 DEX Pairs - Get tradable tokens by chain using DexScreener API
"""

import requests
from typing import Dict, List, Optional
import time

# Chain ID mapping
CHAIN_IDS = {
    'ethereum': 'ethereum',
    'base': 'base',
    'arbitrum': 'arbitrum',
    'bsc': 'bsc',
    'solana': 'solana',
    'polygon': 'polygon',
    'optimism': 'optimism',
    'avalanche': 'avalanche',
}

# Minimum liquidity to consider a pair tradable
MIN_LIQUIDITY_USD = 10000  # $10k minimum


def get_token_pairs(symbol: str, chain: str = None) -> List[Dict]:
    """
    Get trading pairs for a token symbol
    Returns pairs with liquidity info
    """
    try:
        resp = requests.get(
            f'https://api.dexscreener.com/latest/dex/search',
            params={'q': symbol},
            timeout=10
        )
        
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        pairs = data.get('pairs', [])
        
        # Filter by chain if specified
        if chain:
            chain_id = CHAIN_IDS.get(chain, chain)
            pairs = [p for p in pairs if p.get('chainId') == chain_id]
        
        # Filter by minimum liquidity
        pairs = [p for p in pairs if (p.get('liquidity', {}).get('usd') or 0) >= MIN_LIQUIDITY_USD]
        
        return pairs
    
    except Exception as e:
        print(f"Error fetching pairs for {symbol}: {e}")
        return []


def is_tradable_on_chain(symbol: str, chain: str) -> bool:
    """
    Check if a token has a liquid trading pair on a specific chain
    """
    pairs = get_token_pairs(symbol, chain)
    return len(pairs) > 0


def get_best_pair(symbol: str, chain: str) -> Optional[Dict]:
    """
    Get the best (most liquid) trading pair for a token on a chain
    """
    pairs = get_token_pairs(symbol, chain)
    
    if not pairs:
        return None
    
    # Sort by liquidity
    pairs.sort(key=lambda x: x.get('liquidity', {}).get('usd', 0) or 0, reverse=True)
    
    return pairs[0]


def filter_tradable_tokens(tokens: List[Dict], chain: str, max_tokens: int = 50) -> List[Dict]:
    """
    Filter a list of tokens to only include those tradable on a specific chain
    Adds pair info to each token
    
    Args:
        tokens: List of token dicts with 'symbol' key
        chain: Chain to check (ethereum, base, etc.)
        max_tokens: Maximum number of tokens to check (API rate limiting)
    
    Returns:
        List of tokens with added 'pair' info for tradable ones
    """
    tradable = []
    chain_id = CHAIN_IDS.get(chain, chain)
    
    for i, token in enumerate(tokens[:max_tokens]):
        symbol = token.get('symbol', '')
        
        # Rate limiting - DexScreener allows ~300 req/min
        if i > 0 and i % 10 == 0:
            time.sleep(0.5)
        
        pair = get_best_pair(symbol, chain)
        
        if pair:
            token['pair'] = {
                'dex': pair.get('dexId'),
                'pair_address': pair.get('pairAddress'),
                'quote_token': pair.get('quoteToken', {}).get('symbol'),
                'liquidity_usd': pair.get('liquidity', {}).get('usd', 0),
                'price_usd': pair.get('priceUsd'),
                'volume_24h': pair.get('volume', {}).get('h24', 0),
                'price_change_24h': pair.get('priceChange', {}).get('h24', 0),
            }
            tradable.append(token)
            print(f"  ✅ {symbol}: ${pair.get('liquidity', {}).get('usd', 0):,.0f} liq on {pair.get('dexId')}")
        else:
            print(f"  ❌ {symbol}: No liquid pair on {chain}")
    
    return tradable


def get_top_pairs_on_chain(chain: str, limit: int = 50) -> List[Dict]:
    """
    Get top trading pairs on a specific chain by volume
    Uses DexScreener's chain endpoint
    """
    chain_id = CHAIN_IDS.get(chain, chain)
    
    try:
        # DexScreener doesn't have a direct "top pairs by chain" endpoint
        # But we can use their token profiles or boosted tokens
        resp = requests.get(
            f'https://api.dexscreener.com/latest/dex/pairs/{chain_id}',
            timeout=15
        )
        
        # This endpoint requires specific pair addresses
        # Alternative: use their trending/boosted endpoints
        
        return []
    
    except Exception as e:
        print(f"Error fetching top pairs: {e}")
        return []


if __name__ == '__main__':
    # Test
    print("Testing DEX pairs API...")
    
    test_tokens = ['BRETT', 'PEPE', 'UAI', 'XVG', 'DOGE']
    chain = 'base'
    
    print(f"\nChecking pairs on {chain}:")
    for symbol in test_tokens:
        pair = get_best_pair(symbol, chain)
        if pair:
            liq = pair.get('liquidity', {}).get('usd', 0)
            dex = pair.get('dexId')
            print(f"  ✅ {symbol}: ${liq:,.0f} on {dex}")
        else:
            print(f"  ❌ {symbol}: Not found on {chain}")
