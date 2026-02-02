"""
Chain-specific token discovery via DexScreener
Only returns tokens that are actually tradable on the target chain
"""
import requests
from typing import List, Dict, Optional

DEXSCREENER_API = "https://api.dexscreener.com"

# Supported DEXes by chain
CHAIN_DEXES = {
    'base': ['aerodrome', 'uniswap', 'pancakeswap', 'baseswap', 'alien-base'],
    'ethereum': ['uniswap', 'sushiswap', 'curve'],
    'arbitrum': ['uniswap', 'camelot', 'sushiswap'],
    'solana': ['raydium', 'orca', 'meteora'],
}

# Min liquidity by chain
MIN_LIQUIDITY = {
    'base': 50000,      # $50k min for Base
    'ethereum': 100000, # $100k min for ETH (higher gas)
    'arbitrum': 50000,
    'solana': 25000,
}


def get_trending_tokens_on_chain(chain: str, min_liquidity: float = None, 
                                  max_mcap: float = 100_000_000,
                                  limit: int = 30) -> List[Dict]:
    """
    Get trending tokens directly from DexScreener for a specific chain
    Returns only tokens with sufficient liquidity on supported DEXes
    """
    if min_liquidity is None:
        min_liquidity = MIN_LIQUIDITY.get(chain, 50000)
    
    supported_dexes = CHAIN_DEXES.get(chain, [])
    
    # Search terms by mcap tier
    SEARCH_TERMS_SMALL = [
        'meme', 'ai', 'degen', 'pepe', 'dog', 'cat', 'moon', 'based', 'brett',
        'frog', 'ape', 'wojak', 'chad', 'bobo', 'apu', 'toshi', 'normie',
        'bald', 'fomo', 'wagmi', 'gm', 'ser', 'anon', 'wen', 'pump', 'flower',
    ]
    SEARCH_TERMS_MID = [
        'aero', 'virtual', 'morpho', 'seamless', 'extra', 'well', 'alien',
        'cbeth', 'cbbtc', 'usdc', 'dai', 'weth', 'comp', 'uni', 'link',
        'render', 'ondo', 'friend', 'higher', 'lower', 'zora', 'farcaster',
    ]
    
    # Use appropriate search terms based on max_mcap
    if max_mcap >= 100_000_000:  # Mid cap or higher
        search_terms = SEARCH_TERMS_MID + SEARCH_TERMS_SMALL[:5]
    else:
        search_terms = SEARCH_TERMS_SMALL
    
    all_tokens = []
    seen_addresses = set()
    
    try:
        # Search for tokens using various terms
        for term in search_terms:
            try:
                url = f"{DEXSCREENER_API}/latest/dex/search?q={term}"
                resp = requests.get(url, timeout=10)
                
                if resp.status_code != 200:
                    continue
                
                pairs = resp.json().get('pairs', [])
                
                for pair in pairs:
                    # Filter by chain
                    if pair.get('chainId') != chain:
                        continue
                    
                    # Filter by DEX
                    if pair.get('dexId') not in supported_dexes:
                        continue
                    
                    liq = float(pair.get('liquidity', {}).get('usd', 0) or 0)
                    if liq < min_liquidity:
                        continue
                    
                    # Get market cap from FDV
                    mcap = float(pair.get('fdv', 0) or 0)
                    if mcap > max_mcap or mcap < 1000000:  # Skip if >max or <$1M
                        continue
                    
                    base_token = pair.get('baseToken', {})
                    addr = base_token.get('address', '').lower()
                    
                    if addr in seen_addresses:
                        continue
                    seen_addresses.add(addr)
                    
                    # Get price change
                    price_change = float(pair.get('priceChange', {}).get('h24', 0) or 0)
                    
                    all_tokens.append({
                        'symbol': base_token.get('symbol', ''),
                        'name': base_token.get('name', ''),
                        'address': base_token.get('address', ''),
                        'price': float(pair.get('priceUsd', 0) or 0),
                        'price_change_24h': price_change,
                        'market_cap': mcap,
                        'liquidity': liq,
                        'dex': pair.get('dexId'),
                        'pair_address': pair.get('pairAddress'),
                        'chain': chain,
                    })
            except Exception as e:
                continue
        
        # Also get tokens from CoinGecko trending on the chain
        try:
            # Get trending via boosted tokens
            url = f"{DEXSCREENER_API}/token-boosts/top/v1"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                for item in resp.json()[:50]:
                    if item.get('chainId') != chain:
                        continue
                    
                    token_addr = item.get('tokenAddress')
                    if not token_addr or token_addr.lower() in seen_addresses:
                        continue
                    
                    # Get token details
                    detail_url = f"{DEXSCREENER_API}/latest/dex/tokens/{token_addr}"
                    detail_resp = requests.get(detail_url, timeout=5)
                    if detail_resp.status_code == 200:
                        pairs = detail_resp.json().get('pairs', [])
                        if pairs:
                            pair = pairs[0]
                            liq = float(pair.get('liquidity', {}).get('usd', 0) or 0)
                            mcap = float(pair.get('fdv', 0) or 0)
                            
                            if liq >= min_liquidity and 1000000 <= mcap <= max_mcap:
                                base_token = pair.get('baseToken', {})
                                seen_addresses.add(token_addr.lower())
                                
                                all_tokens.append({
                                    'symbol': base_token.get('symbol', ''),
                                    'name': base_token.get('name', ''),
                                    'address': base_token.get('address', ''),
                                    'price': float(pair.get('priceUsd', 0) or 0),
                                    'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0) or 0),
                                    'market_cap': mcap,
                                    'liquidity': liq,
                                    'dex': pair.get('dexId'),
                                    'pair_address': pair.get('pairAddress'),
                                    'chain': chain,
                                })
        except:
            pass
        
        # Sort by 24h price change (gainers first)
        all_tokens.sort(key=lambda x: x.get('price_change_24h', 0), reverse=True)
        
        return all_tokens[:limit]
        
    except Exception as e:
        print(f"Error fetching chain tokens: {e}")
        return []


def get_top_gainers_on_chain(chain: str, min_liquidity: float = 50000,
                              min_change: float = 3.0, limit: int = 20) -> List[Dict]:
    """
    Get top gaining tokens on a specific chain
    Only includes tokens with positive momentum and good liquidity
    """
    tokens = get_trending_tokens_on_chain(chain, min_liquidity, limit=100)
    
    # Filter for gainers only
    gainers = [t for t in tokens if t.get('price_change_24h', 0) >= min_change]
    
    return gainers[:limit]


if __name__ == "__main__":
    print("Testing Base chain token discovery...")
    tokens = get_top_gainers_on_chain('base', min_liquidity=50000, min_change=1.0)
    
    print(f"\n✅ Found {len(tokens)} gainers on Base:\n")
    for t in tokens[:10]:
        print(f"  {t['symbol']:10} | ${t['price']:.6f} | +{t['price_change_24h']:.1f}% | MCap ${t['market_cap']/1e6:.1f}M | Liq ${t['liquidity']/1e3:.0f}k | {t['dex']}")
