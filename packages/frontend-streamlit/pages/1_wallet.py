"""
👛 Wallets - Gestion unifiée des wallets (simulation + réels)
"""

import streamlit as st
import json
import os
from datetime import datetime

# Add parent to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.real_trader import RealTrader, NATIVE_TOKEN

st.set_page_config(
    page_title="👛 Wallets | SmallCap Trader",
    page_icon="👛",
    layout="wide"
)

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
WALLETS_DIR = os.path.join(DATA_DIR, 'wallets')
WALLETS_CONFIG = os.path.join(WALLETS_DIR, 'config.json')

os.makedirs(WALLETS_DIR, exist_ok=True)

# ========== CONFIG ==========
AI_PROFILES = {
    'conservateur': {'name': '🛡️ Conservateur', 'min_score': 80, 'trade_pct': 5},
    'modere': {'name': '⚖️ Modéré', 'min_score': 65, 'trade_pct': 10},
    'agressif': {'name': '🔥 Agressif', 'min_score': 50, 'trade_pct': 20},
    'degen': {'name': '🎰 Degen', 'min_score': 40, 'trade_pct': 30},
}

MARKET_CAP_PRESETS = {
    'micro': {'name': '🔬 Micro (<$1M)', 'min': 0, 'max': 1_000_000},
    'small': {'name': '🐟 Small ($1M-$100M)', 'min': 1_000_000, 'max': 100_000_000},
    'mid': {'name': '🦈 Mid ($100M-$1B)', 'min': 100_000_000, 'max': 1_000_000_000},
    'large': {'name': '🐋 Large (>$1B)', 'min': 1_000_000_000, 'max': 0},
}

CHAINS = {
    'ethereum': {'name': 'Ethereum', 'icon': '🔷'},
    'base': {'name': 'Base', 'icon': '🔵'},
    'arbitrum': {'name': 'Arbitrum', 'icon': '🔶'},
    'bsc': {'name': 'BSC', 'icon': '🟡'},
    'solana': {'name': 'Solana', 'icon': '🟣'},
}


@st.cache_data(ttl=60)  # Cache 1 minute
def get_eth_price() -> float:
    """Get ETH price from CMC API"""
    import requests
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": "849ddcc694a049708d0b5392486d6eaa"}
        params = {"symbol": "ETH", "convert": "USD"}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data['data']['ETH']['quote']['USD']['price']
    except:
        pass
    return 2500  # Fallback


# Stablecoin addresses by chain
STABLECOINS = {
    'base': {
        'USDC': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
    },
    'ethereum': {
        'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        'USDT': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
    },
    'arbitrum': {
        'USDC': '0xaf88d065e77c8cC2239327C5EDb3A432268e5831',
    },
}


@st.cache_data(ttl=60)  # Cache 1 minute
def get_onchain_balance(address: str, chain: str) -> dict:
    """Get on-chain ETH + stablecoin balances"""
    try:
        from web3 import Web3
        # Convert to checksum address
        address = Web3.to_checksum_address(address)
        
        trader = RealTrader(chain=chain)
        
        # Get ETH balance
        eth_balance = trader.w3.eth.get_balance(address)
        eth_amount = float(trader.w3.from_wei(eth_balance, 'ether'))
        
        # Get ETH price from CMC
        eth_price_usd = get_eth_price()
        eth_usd = eth_amount * eth_price_usd
        
        # Get stablecoin balances
        stables = STABLECOINS.get(chain, {})
        stablecoin_usd = 0
        stablecoin_balances = {}
        
        # ERC20 balanceOf ABI
        balance_abi = [{"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}]
        
        for symbol, token_addr in stables.items():
            try:
                contract = trader.w3.eth.contract(
                    address=Web3.to_checksum_address(token_addr),
                    abi=balance_abi
                )
                balance = contract.functions.balanceOf(address).call()
                # USDC/USDT have 6 decimals
                decimals = 6
                token_balance = balance / (10 ** decimals)
                stablecoin_balances[symbol] = token_balance
                stablecoin_usd += token_balance  # 1:1 for stablecoins
            except Exception as e:
                print(f"Error getting {symbol} balance: {e}")
        
        total_usd = eth_usd + stablecoin_usd
        
        return {
            'eth': eth_amount,
            'eth_usd': eth_usd,
            'eth_price': eth_price_usd,
            'stablecoins': stablecoin_balances,
            'stablecoin_usd': stablecoin_usd,
            'usd': total_usd,
        }
    except Exception as e:
        return {'eth': 0, 'usd': 0, 'eth_price': 0, 'stablecoins': {}, 'stablecoin_usd': 0, 'error': str(e)}


def load_wallets_config():
    if os.path.exists(WALLETS_CONFIG):
        with open(WALLETS_CONFIG, 'r') as f:
            return json.load(f)
    return {'wallets': [], 'active_wallet': None}


def save_wallets_config(config):
    with open(WALLETS_CONFIG, 'w') as f:
        json.dump(config, f, indent=2)


def load_wallet_data(wallet_id):
    path = os.path.join(WALLETS_DIR, f'{wallet_id}.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {'portfolio': {'USDC': 0}, 'positions': {}, 'history': [], 'closed_positions': []}


def save_wallet_data(wallet_id, data):
    path = os.path.join(WALLETS_DIR, f'{wallet_id}.json')
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def create_wallet(wallet_type, name, initial_capital=10000, chain='base'):
    config = load_wallets_config()
    wallet_id = f"{wallet_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    wallet = {
        'id': wallet_id,
        'name': name,
        'type': wallet_type,
        'enabled': True,
        'chain': chain,
        'initial_capital': initial_capital,
        'max_positions': 10,
        'position_size_pct': 5,
        'stop_loss_pct': 15,
        'take_profit_pct': 20,
        'ai_profile': 'modere',
        'market_cap': 'small',
        'created_at': datetime.now().isoformat(),
    }
    
    if wallet_type == 'real':
        wallet['address'] = ''
    
    config['wallets'].append(wallet)
    
    if not config.get('active_wallet'):
        config['active_wallet'] = wallet_id
    
    save_wallets_config(config)
    
    if wallet_type == 'paper':
        save_wallet_data(wallet_id, {
            'portfolio': {'USDC': initial_capital},
            'positions': {},
            'history': [],
            'closed_positions': []
        })
    
    return wallet_id


def delete_wallet(wallet_id):
    config = load_wallets_config()
    config['wallets'] = [w for w in config['wallets'] if w['id'] != wallet_id]
    
    if config.get('active_wallet') == wallet_id:
        config['active_wallet'] = config['wallets'][0]['id'] if config['wallets'] else None
    
    save_wallets_config(config)
    
    path = os.path.join(WALLETS_DIR, f'{wallet_id}.json')
    if os.path.exists(path):
        os.remove(path)


# ========== PAGE ==========
st.title("👛 Gestion des Wallets")

config = load_wallets_config()
wallets = config.get('wallets', [])

# ========== WALLET LIST ==========
if wallets:
    for wallet in wallets:
        wallet_id = wallet['id']
        wallet_type = wallet.get('type', 'paper')
        is_sim = wallet_type == 'paper'
        
        data = load_wallet_data(wallet_id)
        positions = data.get('positions', {})
        
        # Header with type badge
        type_badge = "🎮 SIMULATION" if is_sim else "💳 RÉEL"
        status_icon = '🟢' if wallet.get('enabled') else '⚪'
        
        st.subheader(f"{status_icon} {wallet['name']} — {type_badge}")
        
        # Wallet address for real wallets
        wallet_address = wallet.get('address', '')
        if wallet_address:
            st.code(wallet_address)
        
        # Get balance based on wallet type
        if is_sim:
            # Paper wallet: use JSON data
            cash = data.get('portfolio', {}).get('USDC', 0)
            total_value = cash
            for sym, pos in positions.items():
                total_value += pos.get('amount', 0) * pos.get('avg_price', 0)
            cash_label = "💵 Cash (USDC)"
            positions_value = total_value - cash
            extra_balances = None
        else:
            # Real wallet: get on-chain balance
            if wallet_address:
                chain = wallet.get('chain', 'base')
                balance = get_onchain_balance(wallet_address, chain)
                eth_usd = balance.get('eth_usd', 0)
                eth_amount = balance.get('eth', 0)
                stablecoin_usd = balance.get('stablecoin_usd', 0)
                stablecoins = balance.get('stablecoins', {})
                
                # Calculate positions value (tokens we bought)
                positions_value = 0
                for sym, pos in positions.items():
                    # Use current price if available, else avg_price
                    price = pos.get('current_price', pos.get('avg_price', 0))
                    positions_value += pos.get('amount', 0) * price
                
                cash = eth_usd + stablecoin_usd  # ETH + stablecoins = cash
                total_value = cash + positions_value
                
                # Build cash label with breakdown
                parts = [f"ETH ({eth_amount:.4f})"]
                for sym, amt in stablecoins.items():
                    if amt > 0:
                        parts.append(f"{sym} ({amt:.2f})")
                cash_label = "💵 " + " + ".join(parts)
                extra_balances = {'eth': eth_amount, 'eth_usd': eth_usd, 'stablecoins': stablecoins}
            else:
                cash = 0
                total_value = 0
                positions_value = 0
                cash_label = "💵 Cash"
                extra_balances = None
        
        # Stats
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Valeur totale", f"${total_value:,.2f}")
        col2.metric(cash_label, f"${cash:,.2f}")
        col3.metric("📊 Positions", f"{len(positions)}/{wallet.get('max_positions', 10)}")
        col4.metric("⛓️ Chain", wallet.get('chain', 'base').upper())
        
        # Config expander
        with st.expander("⚙️ Configuration"):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                new_profile = st.selectbox(
                    "🎯 Profil Risque",
                    options=list(AI_PROFILES.keys()),
                    format_func=lambda x: AI_PROFILES[x]['name'],
                    index=list(AI_PROFILES.keys()).index(wallet.get('ai_profile', 'modere')),
                    key=f"profile_{wallet_id}"
                )
            
            with col2:
                new_mcap = st.selectbox(
                    "💰 Market Cap",
                    options=list(MARKET_CAP_PRESETS.keys()),
                    format_func=lambda x: MARKET_CAP_PRESETS[x]['name'],
                    index=list(MARKET_CAP_PRESETS.keys()).index(wallet.get('market_cap', 'small')),
                    key=f"mcap_{wallet_id}"
                )
            
            with col3:
                new_chain = st.selectbox(
                    "⛓️ Chain",
                    options=list(CHAINS.keys()),
                    format_func=lambda x: f"{CHAINS[x]['icon']} {CHAINS[x]['name']}",
                    index=list(CHAINS.keys()).index(wallet.get('chain', 'base')) if wallet.get('chain', 'base') in CHAINS else 0,
                    key=f"chain_{wallet_id}"
                )
            
            with col4:
                new_max_pos = st.number_input(
                    "📊 Max Positions",
                    min_value=1, max_value=50, value=wallet.get('max_positions', 10),
                    key=f"maxpos_{wallet_id}"
                )
            
            col5, col6, col7, col8 = st.columns(4)
            
            with col5:
                new_pos_size = st.number_input(
                    "📏 Taille Position (%)",
                    min_value=1, max_value=50, value=wallet.get('position_size_pct', 5),
                    key=f"possize_{wallet_id}"
                )
            
            with col6:
                new_sl = st.number_input(
                    "🔴 Stop Loss (%)",
                    min_value=5, max_value=50, value=wallet.get('stop_loss_pct', 15),
                    key=f"sl_{wallet_id}"
                )
            
            with col7:
                new_tp = st.number_input(
                    "🟢 Take Profit (%)",
                    min_value=5, max_value=200, value=wallet.get('take_profit_pct', 20),
                    key=f"tp_{wallet_id}"
                )
            
            with col8:
                enabled = st.checkbox("✅ Actif", value=wallet.get('enabled', True), key=f"enabled_{wallet_id}")
            
            # Actions
            col_save, col_reset, col_delete = st.columns([2, 1, 1])
            
            with col_save:
                if st.button("💾 Sauvegarder", key=f"save_{wallet_id}", type="primary"):
                    for w in config['wallets']:
                        if w['id'] == wallet_id:
                            w['ai_profile'] = new_profile
                            w['market_cap'] = new_mcap
                            w['chain'] = new_chain
                            w['max_positions'] = new_max_pos
                            w['position_size_pct'] = new_pos_size
                            w['stop_loss_pct'] = new_sl
                            w['take_profit_pct'] = new_tp
                            w['enabled'] = enabled
                            w['updated_at'] = datetime.now().isoformat()
                            break
                    save_wallets_config(config)
                    st.success("✅ Sauvegardé!")
                    st.rerun()
            
            with col_reset:
                if is_sim and st.button("🔄 Reset", key=f"reset_{wallet_id}"):
                    initial = wallet.get('initial_capital', 10000)
                    save_wallet_data(wallet_id, {
                        'portfolio': {'USDC': initial},
                        'positions': {},
                        'history': [],
                        'closed_positions': []
                    })
                    st.success(f"✅ Reset à ${initial:,}")
                    st.rerun()
            
            with col_delete:
                if st.button("🗑️ Supprimer", key=f"delete_{wallet_id}"):
                    st.session_state[f"confirm_delete_{wallet_id}"] = True
            
            if st.session_state.get(f"confirm_delete_{wallet_id}"):
                st.warning(f"⚠️ Supprimer '{wallet['name']}' ?")
                c1, c2 = st.columns(2)
                if c1.button("✅ Oui", key=f"yes_{wallet_id}"):
                    delete_wallet(wallet_id)
                    del st.session_state[f"confirm_delete_{wallet_id}"]
                    st.rerun()
                if c2.button("❌ Non", key=f"no_{wallet_id}"):
                    del st.session_state[f"confirm_delete_{wallet_id}"]
                    st.rerun()
        
        st.divider()

else:
    st.info("📭 Aucun wallet. Crée-en un ci-dessous!")

# ========== CREATE WALLET ==========
st.subheader("➕ Créer un Wallet")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🎮 Simulation")
    st.caption("Paper trading avec argent virtuel")
    
    with st.form("create_sim"):
        sim_name = st.text_input("Nom", value="Simulation")
        sim_capital = st.number_input("Capital initial ($)", min_value=100, max_value=1000000, value=10000)
        sim_chain = st.selectbox("Chain", list(CHAINS.keys()), format_func=lambda x: f"{CHAINS[x]['icon']} {CHAINS[x]['name']}")
        
        if st.form_submit_button("🎮 Créer", type="primary"):
            create_wallet('paper', sim_name, sim_capital, sim_chain)
            st.success(f"✅ '{sim_name}' créé!")
            st.rerun()

with col2:
    st.markdown("### 💳 Réel")
    st.caption("Trading avec vrais fonds")
    
    with st.form("create_real"):
        real_name = st.text_input("Nom", value="Mon Wallet")
        real_chain = st.selectbox("Chain", list(CHAINS.keys()), format_func=lambda x: f"{CHAINS[x]['icon']} {CHAINS[x]['name']}", key="real_chain")
        real_address = st.text_input("Adresse (0x...)", placeholder="0x...")
        
        if st.form_submit_button("💳 Créer"):
            if real_address and real_address.startswith("0x") and len(real_address) == 42:
                wallet_id = create_wallet('real', real_name, 0, real_chain)
                cfg = load_wallets_config()
                for w in cfg['wallets']:
                    if w['id'] == wallet_id:
                        w['address'] = real_address
                        break
                save_wallets_config(cfg)
                st.success(f"✅ '{real_name}' créé!")
                st.rerun()
            else:
                st.error("❌ Adresse invalide")
