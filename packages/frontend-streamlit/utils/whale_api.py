"""
🐋 Whale API - Track whale wallets using Etherscan/Basescan
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional

# API Keys (free tier = 5 req/sec)
ETHERSCAN_API_KEY = os.environ.get('ETHERSCAN_API_KEY', 'YourApiKeyToken')  # Free tier works without key
BASESCAN_API_KEY = os.environ.get('BASESCAN_API_KEY', '')

# API Endpoints
APIS = {
    'ethereum': {
        'url': 'https://api.etherscan.io/api',
        'key': ETHERSCAN_API_KEY,
        'explorer': 'https://etherscan.io'
    },
    'base': {
        'url': 'https://api.basescan.org/api',
        'key': BASESCAN_API_KEY,
        'explorer': 'https://basescan.org'
    }
}

# Data storage
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'whales')
TRACKED_FILE = os.path.join(DATA_DIR, 'tracked.json')
TRANSACTIONS_FILE = os.path.join(DATA_DIR, 'transactions.json')

# Known whale addresses (curated list)
KNOWN_WHALES_ETHEREUM = {
    "0x28c6c06298d514db089934071355e5743bf21d60": {
        "name": "Binance 14",
        "type": "exchange",
        "importance": "high",
        "description": "Major Binance hot wallet"
    },
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": {
        "name": "Binance 15",
        "type": "exchange",
        "importance": "high",
        "description": "Binance hot wallet"
    },
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": {
        "name": "Binance 16",
        "type": "exchange",
        "importance": "high",
        "description": "Binance deposit wallet"
    },
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": {
        "name": "Coinbase 4",
        "type": "exchange",
        "importance": "high",
        "description": "Coinbase custody"
    },
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": {
        "name": "Coinbase 10",
        "type": "exchange",
        "importance": "high",
        "description": "Coinbase hot wallet"
    },
    "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503": {
        "name": "Justin Sun / Binance 8",
        "type": "whale",
        "importance": "high",
        "description": "Large accumulator"
    },
    "0x8103683202aa8da10536036edef04cdd865c225e": {
        "name": "Wintermute",
        "type": "market_maker",
        "importance": "medium",
        "description": "Major market maker"
    },
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe": {
        "name": "GSR Markets",
        "type": "market_maker",
        "importance": "medium",
        "description": "Market maker"
    },
    "0x40ec5b33f54e0e8a33a975908c5ba1c14e5bbbdf": {
        "name": "Polygon Bridge",
        "type": "bridge",
        "importance": "medium",
        "description": "Polygon POS Bridge"
    },
    "0x00000000219ab540356cbb839cbe05303d7705fa": {
        "name": "ETH2 Deposit Contract",
        "type": "foundation",
        "importance": "high",
        "description": "Ethereum 2.0 staking"
    }
}

KNOWN_WHALES_BASE = {
    "0x3304e22ddaa22bcdc5fca2269b418046ae7b566a": {
        "name": "Coinbase Base Bridge",
        "type": "bridge",
        "importance": "high",
        "description": "Official Coinbase Base bridge"
    },
    "0x4200000000000000000000000000000000000010": {
        "name": "Base L2 Bridge",
        "type": "bridge",
        "importance": "high",
        "description": "L2 standard bridge"
    }
}


def ensure_data_dir():
    """Create data directory if needed"""
    os.makedirs(DATA_DIR, exist_ok=True)


def get_known_whales(network: str = 'ethereum') -> Dict:
    """Get list of known whale addresses for a network"""
    if network == 'base':
        return KNOWN_WHALES_BASE
    return KNOWN_WHALES_ETHEREUM


def load_tracked_whales() -> List[Dict]:
    """Load tracked whales from file"""
    ensure_data_dir()
    try:
        if os.path.exists(TRACKED_FILE):
            with open(TRACKED_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return []


def save_tracked_whales(whales: List[Dict]):
    """Save tracked whales to file"""
    ensure_data_dir()
    with open(TRACKED_FILE, 'w') as f:
        json.dump(whales, f, indent=2)


def load_transactions() -> Dict:
    """Load cached transactions"""
    ensure_data_dir()
    try:
        if os.path.exists(TRANSACTIONS_FILE):
            with open(TRANSACTIONS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}


def save_transactions(txs: Dict):
    """Save transactions to file"""
    ensure_data_dir()
    with open(TRANSACTIONS_FILE, 'w') as f:
        json.dump(txs, f, indent=2, default=str)


def get_whale_transactions_sync(
    address: str,
    network: str = 'ethereum',
    limit: int = 20,
    api_key: str = None
) -> List[Dict]:
    """
    Fetch recent transactions for a whale address
    Uses Etherscan/Basescan API
    """
    api_config = APIS.get(network, APIS['ethereum'])
    key = api_key or api_config['key']
    
    # Get normal transactions
    params = {
        'module': 'account',
        'action': 'txlist',
        'address': address,
        'startblock': 0,
        'endblock': 99999999,
        'page': 1,
        'offset': limit,
        'sort': 'desc',
        'apikey': key
    }
    
    try:
        resp = requests.get(api_config['url'], params=params, timeout=15)
        data = resp.json()
        
        if data.get('status') != '1':
            return []
        
        transactions = []
        for tx in data.get('result', []):
            # Parse transaction
            value_eth = int(tx.get('value', 0)) / 1e18
            is_outgoing = tx.get('from', '').lower() == address.lower()
            
            # Determine if it's a swap (interaction with contract)
            is_swap = tx.get('to', '').lower() != address.lower() and len(tx.get('input', '')) > 10
            
            # Try to decode method
            method_id = tx.get('input', '')[:10] if tx.get('input') else ''
            method_name = decode_method(method_id)
            
            # Determine direction for swaps
            swap_direction = None
            if is_swap:
                # Heuristic: if sending ETH to a DEX, likely a buy
                # If receiving tokens (no ETH sent), likely a sell
                swap_direction = 'buy' if value_eth > 0 else 'sell'
            
            transactions.append({
                'hash': tx.get('hash'),
                'timestamp': datetime.fromtimestamp(int(tx.get('timeStamp', 0))).isoformat(),
                'from': tx.get('from'),
                'to': tx.get('to'),
                'value': value_eth,
                'token_symbol': 'ETH',
                'is_outgoing': is_outgoing,
                'is_swap': is_swap,
                'swap_direction': swap_direction,
                'method_name': method_name,
                'gas_used': int(tx.get('gasUsed', 0)),
                'status': 'success' if tx.get('isError') == '0' else 'failed'
            })
        
        return transactions
    
    except Exception as e:
        print(f"Error fetching transactions: {e}")
        return []


def get_token_transfers(
    address: str,
    network: str = 'ethereum',
    limit: int = 20,
    api_key: str = None
) -> List[Dict]:
    """
    Fetch ERC20 token transfers for an address
    """
    api_config = APIS.get(network, APIS['ethereum'])
    key = api_key or api_config['key']
    
    params = {
        'module': 'account',
        'action': 'tokentx',
        'address': address,
        'page': 1,
        'offset': limit,
        'sort': 'desc',
        'apikey': key
    }
    
    try:
        resp = requests.get(api_config['url'], params=params, timeout=15)
        data = resp.json()
        
        if data.get('status') != '1':
            return []
        
        transfers = []
        for tx in data.get('result', []):
            decimals = int(tx.get('tokenDecimal', 18))
            value = int(tx.get('value', 0)) / (10 ** decimals)
            is_outgoing = tx.get('from', '').lower() == address.lower()
            
            transfers.append({
                'hash': tx.get('hash'),
                'timestamp': datetime.fromtimestamp(int(tx.get('timeStamp', 0))).isoformat(),
                'from': tx.get('from'),
                'to': tx.get('to'),
                'value': value,
                'token_symbol': tx.get('tokenSymbol', '???'),
                'token_name': tx.get('tokenName', ''),
                'token_address': tx.get('contractAddress'),
                'is_outgoing': is_outgoing,
                'is_swap': True,  # Token transfers are usually swaps
                'swap_direction': 'sell' if is_outgoing else 'buy'
            })
        
        return transfers
    
    except Exception as e:
        print(f"Error fetching token transfers: {e}")
        return []


def analyze_whale_portfolio_sync(
    address: str,
    network: str = 'ethereum',
    api_key: str = None
) -> Dict:
    """
    Analyze a whale's current portfolio
    """
    api_config = APIS.get(network, APIS['ethereum'])
    key = api_key or api_config['key']
    
    portfolio = {
        'address': address,
        'network': network,
        'native_balance': 0,
        'holdings': [],
        'last_activity': None
    }
    
    # Get ETH balance
    try:
        params = {
            'module': 'account',
            'action': 'balance',
            'address': address,
            'tag': 'latest',
            'apikey': key
        }
        resp = requests.get(api_config['url'], params=params, timeout=10)
        data = resp.json()
        if data.get('status') == '1':
            portfolio['native_balance'] = int(data.get('result', 0)) / 1e18
    except:
        pass
    
    # Get token balances (requires API key for full list)
    transfers = get_token_transfers(address, network, limit=50, api_key=key)
    
    # Aggregate holdings from recent transfers
    holdings = {}
    for tx in transfers:
        symbol = tx.get('token_symbol', '???')
        if symbol not in holdings:
            holdings[symbol] = {
                'symbol': symbol,
                'name': tx.get('token_name', ''),
                'address': tx.get('token_address', ''),
                'balance': 0,
                'last_activity': tx.get('timestamp')
            }
        
        # Update balance (rough estimate from transfers)
        if tx.get('is_outgoing'):
            holdings[symbol]['balance'] -= tx.get('value', 0)
        else:
            holdings[symbol]['balance'] += tx.get('value', 0)
    
    # Filter positive balances
    portfolio['holdings'] = [h for h in holdings.values() if h['balance'] > 0]
    
    # Get last activity
    if transfers:
        portfolio['last_activity'] = transfers[0].get('timestamp')
    
    return portfolio


def check_for_alerts_sync(
    address: str,
    network: str = 'ethereum',
    min_amount_usd: float = 10000,
    lookback_minutes: int = 60,
    api_key: str = None
) -> List[Dict]:
    """
    Check for significant whale activity
    """
    alerts = []
    
    # Get recent transfers
    transfers = get_token_transfers(address, network, limit=30, api_key=api_key)
    
    # Check each transfer
    cutoff = datetime.now().timestamp() - (lookback_minutes * 60)
    
    for tx in transfers:
        try:
            tx_time = datetime.fromisoformat(tx['timestamp'].replace('Z', '+00:00'))
            if tx_time.timestamp() < cutoff:
                continue
            
            # Estimate USD value (rough)
            # TODO: Get actual token prices
            value = tx.get('value', 0)
            estimated_usd = value * 2000  # Rough estimate
            
            if estimated_usd >= min_amount_usd:
                alerts.append({
                    'address': address,
                    'network': network,
                    'tx_hash': tx.get('hash'),
                    'timestamp': tx.get('timestamp'),
                    'token_symbol': tx.get('token_symbol'),
                    'amount': value,
                    'direction': tx.get('swap_direction'),
                    'importance': 'high' if estimated_usd > 50000 else 'medium',
                    'message': f"🐋 {tx.get('swap_direction', 'transfer').upper()} {value:.2f} {tx.get('token_symbol')}"
                })
        except:
            continue
    
    return alerts


def decode_method(method_id: str) -> str:
    """Decode common method signatures"""
    methods = {
        '0xa9059cbb': 'transfer',
        '0x23b872dd': 'transferFrom',
        '0x095ea7b3': 'approve',
        '0x7ff36ab5': 'swapExactETHForTokens',
        '0x38ed1739': 'swapExactTokensForTokens',
        '0x18cbafe5': 'swapExactTokensForETH',
        '0xfb3bdb41': 'swapETHForExactTokens',
        '0x5c11d795': 'swapExactTokensForTokensSupportingFeeOnTransferTokens',
        '0x791ac947': 'swapExactTokensForETHSupportingFeeOnTransferTokens',
        '0xb6f9de95': 'swapExactETHForTokensSupportingFeeOnTransferTokens',
        '0x3593564c': 'execute (Uniswap Universal Router)',
        '0x04e45aaf': 'exactInputSingle (Uniswap V3)',
        '0xc04b8d59': 'exactInput (Uniswap V3)',
        '0xdb3e2198': 'exactOutputSingle (Uniswap V3)',
    }
    return methods.get(method_id, method_id[:10] if method_id else 'unknown')


# Convenience function for checking whales periodically
def check_all_whales(api_key: str = None) -> Dict:
    """
    Check all tracked whales for new activity
    Returns summary of findings
    """
    tracked = load_tracked_whales()
    cached_txs = load_transactions()
    
    results = {
        'checked_at': datetime.now().isoformat(),
        'whales_checked': len(tracked),
        'new_transactions': [],
        'alerts': []
    }
    
    for whale in tracked:
        address = whale.get('address')
        network = whale.get('network', 'ethereum')
        
        # Get latest transactions
        txs = get_whale_transactions_sync(address, network, limit=10, api_key=api_key)
        token_txs = get_token_transfers(address, network, limit=20, api_key=api_key)
        
        # Combine
        all_txs = txs + token_txs
        all_txs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Check for new ones
        cached_hashes = set(tx.get('hash') for tx in cached_txs.get(address, []))
        new_txs = [tx for tx in all_txs if tx.get('hash') not in cached_hashes]
        
        if new_txs:
            results['new_transactions'].append({
                'whale': whale.get('name', address[:10]),
                'address': address,
                'count': len(new_txs),
                'transactions': new_txs[:5]  # Top 5 newest
            })
        
        # Check for alerts
        alerts = check_for_alerts_sync(address, network, api_key=api_key)
        results['alerts'].extend(alerts)
        
        # Update cache
        cached_txs[address] = all_txs[:50]  # Keep last 50
    
    # Save updated cache
    save_transactions(cached_txs)
    
    return results


if __name__ == '__main__':
    # Test
    print("Testing whale API...")
    
    # Test known whales
    whales = get_known_whales('ethereum')
    print(f"Known Ethereum whales: {len(whales)}")
    
    # Test transaction fetch
    test_address = "0x28c6c06298d514db089934071355e5743bf21d60"  # Binance 14
    print(f"\nFetching transactions for Binance 14...")
    txs = get_whale_transactions_sync(test_address, limit=5)
    print(f"Found {len(txs)} transactions")
    for tx in txs[:3]:
        print(f"  - {tx['timestamp']}: {tx['value']:.4f} ETH ({tx.get('method_name', 'transfer')})")
