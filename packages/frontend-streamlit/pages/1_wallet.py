"""
👛 Wallets - Gestion unifiée des wallets (simulation + réels)
"""

import streamlit as st
import json
import os
from datetime import datetime

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
        cash = data.get('portfolio', {}).get('USDC', 0)
        positions = data.get('positions', {})
        
        total_value = cash
        for sym, pos in positions.items():
            total_value += pos.get('amount', 0) * pos.get('avg_price', 0)
        
        # Header with type badge
        type_badge = "🎮 SIMULATION" if is_sim else "💳 RÉEL"
        status_icon = '🟢' if wallet.get('enabled') else '⚪'
        
        st.subheader(f"{status_icon} {wallet['name']} — {type_badge}")
        
        # Wallet address for real wallets
        wallet_address = wallet.get('address', '')
        if wallet_address:
            st.code(wallet_address)
        
        # Stats
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Valeur totale", f"${total_value:,.2f}")
        col2.metric("💵 Cash", f"${cash:,.2f}")
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
