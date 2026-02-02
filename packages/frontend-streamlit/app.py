"""
Crypto SmallCap Trader - Dashboard Principal
"""

import streamlit as st
from datetime import datetime
import json
import os

st.set_page_config(
    page_title="🚀 SmallCap Trader",
    page_icon="🚀",
    layout="wide"
)

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
WALLETS_DIR = os.path.join(DATA_DIR, 'wallets')
WALLETS_CONFIG = os.path.join(WALLETS_DIR, 'config.json')
BOT_CONFIG = os.path.join(DATA_DIR, 'bot_config.json')

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default


@st.cache_data(ttl=120)
def get_real_wallet_balance(address: str, chain: str) -> dict:
    """Get on-chain balance for real wallets"""
    try:
        from web3 import Web3
        
        # RPC endpoints
        rpc_urls = {
            'base': 'https://mainnet.base.org',
            'ethereum': 'https://eth.llamarpc.com',
            'arbitrum': 'https://arb1.arbitrum.io/rpc',
        }
        
        # Stablecoin addresses
        stables = {
            'base': {'USDC': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'},
            'ethereum': {'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'},
        }
        
        w3 = Web3(Web3.HTTPProvider(rpc_urls.get(chain, rpc_urls['base'])))
        address = Web3.to_checksum_address(address)
        
        # ETH balance
        eth_balance = w3.eth.get_balance(address)
        eth_amount = float(w3.from_wei(eth_balance, 'ether'))
        
        # Get ETH price
        import requests
        resp = requests.get(
            'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest',
            headers={'X-CMC_PRO_API_KEY': '849ddcc694a049708d0b5392486d6eaa'},
            params={'symbol': 'ETH'}, timeout=10
        )
        eth_price = resp.json()['data']['ETH']['quote']['USD']['price']
        eth_usd = eth_amount * eth_price
        
        # Stablecoin balance
        stable_usd = 0
        chain_stables = stables.get(chain, {})
        balance_abi = [{"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}]
        
        for symbol, token_addr in chain_stables.items():
            try:
                contract = w3.eth.contract(address=Web3.to_checksum_address(token_addr), abi=balance_abi)
                bal = contract.functions.balanceOf(address).call()
                stable_usd += bal / 1e6  # USDC has 6 decimals
            except:
                pass
        
        return {'eth': eth_amount, 'eth_usd': eth_usd, 'stable_usd': stable_usd, 'total_usd': eth_usd + stable_usd}
    except Exception as e:
        return {'eth': 0, 'eth_usd': 0, 'stable_usd': 0, 'total_usd': 0, 'error': str(e)}

# Load data
wallets_config = load_json(WALLETS_CONFIG, {'wallets': []})
bot_config = load_json(BOT_CONFIG, {})
wallets = wallets_config.get('wallets', [])

# Calculate totals from all wallets
total_value = 0
total_positions = 0
total_cash = 0
win_count = 0
total_trades = 0

for w in wallets:
    wallet_path = os.path.join(WALLETS_DIR, f"{w['id']}.json")
    data = load_json(wallet_path, {'portfolio': {'USDC': 0}, 'positions': {}, 'closed_positions': []})
    
    positions = data.get('positions', {})
    closed = data.get('closed_positions', [])
    
    # Get cash based on wallet type
    if w.get('type') == 'real' and w.get('address'):
        # Real wallet: get on-chain balance
        balance = get_real_wallet_balance(w['address'], w.get('chain', 'base'))
        cash = balance.get('total_usd', 0)
    else:
        # Paper wallet: use JSON data
        cash = data.get('portfolio', {}).get('USDC', 0)
    
    # Calculate position value
    pos_value = 0
    for sym, pos in positions.items():
        pos_value += pos.get('amount', 0) * pos.get('avg_price', 0)
    
    total_value += cash + pos_value
    total_cash += cash
    total_positions += len(positions)
    
    # Win rate stats
    win_count += sum(1 for p in closed if p.get('pnl_usd', 0) > 0)
    total_trades += len(closed)

win_rate = round(win_count / total_trades * 100) if total_trades > 0 else 0

# Sidebar
with st.sidebar:
    st.title("🚀 SmallCap Trader")
    st.markdown("---")
    
    st.page_link("pages/1_wallet.py", label="👛 Wallets", icon="👛")
    st.page_link("pages/9_positions.py", label="📊 Positions", icon="📊")
    st.page_link("pages/2_trades.py", label="📈 Trades", icon="📈")
    st.page_link("pages/9_logs_ia.py", label="🤖 Logs IA", icon="🤖")
    
    st.markdown("---")
    st.caption("v0.2.0 | " + datetime.now().strftime("%d/%m/%Y %H:%M"))

# Header
st.title("🚀 Crypto SmallCap Trader")

# Métriques principales
col1, col2, col3, col4 = st.columns(4)

col1.metric("💰 Valeur Portfolio", f"${total_value:,.2f}")
col2.metric("📊 Positions", f"{total_positions}")
col3.metric("💵 Cash", f"${total_cash:,.2f}")
col4.metric("🎯 Win Rate", f"{win_rate}%" if total_trades > 0 else "--", 
            delta=f"{total_trades} trades" if total_trades > 0 else None)

st.divider()

# Status
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📊 Wallets")
    
    if wallets:
        for w in wallets:
            wallet_path = os.path.join(WALLETS_DIR, f"{w['id']}.json")
            data = load_json(wallet_path, {'portfolio': {'USDC': 0}, 'positions': {}})
            positions = data.get('positions', {})
            
            # Get cash based on wallet type
            if w.get('type') == 'real' and w.get('address'):
                balance = get_real_wallet_balance(w['address'], w.get('chain', 'base'))
                cash = balance.get('total_usd', 0)
            else:
                cash = data.get('portfolio', {}).get('USDC', 0)
            
            pos_value = sum(p.get('amount', 0) * p.get('avg_price', 0) for p in positions.values())
            total = cash + pos_value
            
            type_badge = "🎮" if w.get('type') == 'paper' else "💳"
            status = "🟢" if w.get('enabled') else "⚪"
            
            st.markdown(f"{status} {type_badge} **{w['name']}** — ${total:,.2f} | {len(positions)} pos | {w.get('chain', 'base').upper()}")
            
            if w.get('address'):
                st.caption(f"└─ `{w['address'][:10]}...{w['address'][-6:]}`")
    else:
        st.warning("⚠️ Aucun wallet configuré")
    
    st.divider()
    st.subheader("🤖 Bot Status")
    
    # Le bot tourne via cron - vérifier si enabled
    bot_enabled = bot_config.get('enabled', False)
    if bot_enabled:
        st.success("✅ Bot actif (cron toutes les heures)")
        st.caption(f"Dernière config: {bot_config.get('updated_at', 'N/A')}")
    else:
        st.info("⏸️ Bot en pause")

with col_right:
    st.subheader("✅ Checklist")
    
    has_wallet = len(wallets) > 0
    has_sim_funds = total_value > 0
    has_config = any(w.get('ai_profile') for w in wallets)
    bot_running = bot_config.get('enabled', False)
    
    steps = [
        ("👛 Créer un wallet", has_wallet),
        ("💰 Fonds disponibles", has_sim_funds),
        ("⚙️ Config wallet", has_config),
        ("🤖 Bot actif", bot_running),
    ]
    
    for step, done in steps:
        if done:
            st.markdown(f"✅ ~~{step}~~")
        else:
            st.markdown(f"⬜ {step}")
    
    if all(done for _, done in steps):
        st.success("🎉 Tout est prêt!")

st.divider()

# Navigation
st.subheader("📍 Navigation")
nav_cols = st.columns(4)

with nav_cols[0]:
    if st.button("👛 Wallets", use_container_width=True, type="primary"):
        st.switch_page("pages/1_wallet.py")

with nav_cols[1]:
    if st.button("📊 Positions", use_container_width=True):
        st.switch_page("pages/9_positions.py")

with nav_cols[2]:
    if st.button("📈 Trades", use_container_width=True):
        st.switch_page("pages/2_trades.py")

with nav_cols[3]:
    if st.button("🤖 Logs IA", use_container_width=True):
        st.switch_page("pages/9_logs_ia.py")

st.divider()
st.caption("SmallCap Trader v0.2.0 - Bot trading IA par Jean-Michel 🥖")
