"""
👛 Wallets - Gestion unifiée des wallets (simulation + réels)
"""

import streamlit as st
import json
import os
from datetime import datetime
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

st.set_page_config(
    page_title="👛 Wallets | SmallCap Trader",
    page_icon="👛",
    layout="wide"
)

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
WALLETS_DIR = os.path.join(DATA_DIR, 'wallets')
WALLETS_CONFIG = os.path.join(WALLETS_DIR, 'config.json')

# Ensure directories exist
os.makedirs(WALLETS_DIR, exist_ok=True)

# Styles - fond différent pour simulation (meilleur contraste)
st.markdown("""
<style>
    .wallet-sim {
        background: #2a1f4e;
        border: 2px solid #8b5cf6;
        border-radius: 12px;
        padding: 20px;
        margin: 15px 0;
        color: #ffffff;
    }
    .wallet-real {
        background: #1a3a2a;
        border: 2px solid #22c55e;
        border-radius: 12px;
        padding: 20px;
        margin: 15px 0;
        color: #ffffff;
    }
    .wallet-sim *, .wallet-real * {
        color: #ffffff !important;
    }
    .wallet-header {
        font-size: 1.4rem;
        font-weight: bold;
        margin-bottom: 10px;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

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
    """Load wallets configuration"""
    if os.path.exists(WALLETS_CONFIG):
        with open(WALLETS_CONFIG, 'r') as f:
            return json.load(f)
    return {'wallets': [], 'active_wallet': None}


def save_wallets_config(config):
    """Save wallets configuration"""
    with open(WALLETS_CONFIG, 'w') as f:
        json.dump(config, f, indent=2)


def load_wallet_data(wallet_id):
    """Load wallet data (portfolio, positions, history)"""
    path = os.path.join(WALLETS_DIR, f'{wallet_id}.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {'portfolio': {'USDC': 0}, 'positions': {}, 'history': [], 'closed_positions': []}


def save_wallet_data(wallet_id, data):
    """Save wallet data"""
    path = os.path.join(WALLETS_DIR, f'{wallet_id}.json')
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def create_wallet(wallet_type, name, initial_capital=10000, chain='base'):
    """Create a new wallet"""
    config = load_wallets_config()
    
    # Generate unique ID
    wallet_id = f"{wallet_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create wallet entry
    wallet = {
        'id': wallet_id,
        'name': name,
        'type': wallet_type,  # 'paper' (simulation) or 'real'
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
    
    # For real wallets, we'd store address/key (encrypted)
    if wallet_type == 'real':
        wallet['address'] = ''  # To be filled
    
    config['wallets'].append(wallet)
    
    # Set as active if first wallet
    if not config.get('active_wallet'):
        config['active_wallet'] = wallet_id
    
    save_wallets_config(config)
    
    # Create wallet data file
    if wallet_type == 'paper':
        save_wallet_data(wallet_id, {
            'portfolio': {'USDC': initial_capital},
            'positions': {},
            'history': [],
            'closed_positions': []
        })
    
    return wallet_id


def delete_wallet(wallet_id):
    """Delete a wallet"""
    config = load_wallets_config()
    config['wallets'] = [w for w in config['wallets'] if w['id'] != wallet_id]
    
    # Update active wallet if needed
    if config.get('active_wallet') == wallet_id:
        config['active_wallet'] = config['wallets'][0]['id'] if config['wallets'] else None
    
    save_wallets_config(config)
    
    # Delete wallet data file
    path = os.path.join(WALLETS_DIR, f'{wallet_id}.json')
    if os.path.exists(path):
        os.remove(path)


# ========== PAGE ==========
st.title("👛 Gestion des Wallets")
st.caption("Simulation et réels - tous au même endroit")

config = load_wallets_config()
wallets = config.get('wallets', [])

# ========== WALLET LIST ==========
if wallets:
    for wallet in wallets:
        wallet_id = wallet['id']
        wallet_type = wallet.get('type', 'paper')
        is_sim = wallet_type == 'paper'
        
        # Load wallet data for stats
        data = load_wallet_data(wallet_id)
        cash = data.get('portfolio', {}).get('USDC', 0)
        positions = data.get('positions', {})
        
        # Calculate total value
        total_value = cash
        for sym, pos in positions.items():
            total_value += pos.get('amount', 0) * pos.get('avg_price', 0)
        
        # Style based on type
        style_class = "wallet-sim" if is_sim else "wallet-real"
        type_badge = "🎮 SIMULATION" if is_sim else "💳 RÉEL"
        type_color = "#a855f7" if is_sim else "#22c55e"
        
        # Get address for real wallets
        wallet_address = wallet.get('address', '')
        
        # Wallet card - using Streamlit native components for reliability
        status_icon = '🟢' if wallet.get('enabled') else '⚪'
        
        col_info, col_value = st.columns([2, 1])
        
        with col_info:
            st.markdown(f"### {status_icon} {wallet['name']} {type_badge}")
            if wallet_address:
                st.code(wallet_address, language=None)
            st.caption(f"⛓️ {wallet.get('chain', 'base').upper()} | 🎯 {wallet.get('ai_profile', 'modere')}")
        
        with col_value:
            st.metric("💰 Valeur", f"${total_value:,.2f}")
            st.caption(f"{len(positions)} positions | ${cash:,.2f} cash")
        
        # Expandable config
        with st.expander(f"⚙️ Configurer {wallet['name']}", expanded=False):
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
                if st.button("💾 Sauvegarder", key=f"save_{wallet_id}", type="primary", use_container_width=True):
                    # Update wallet config
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
                    st.success("✅ Config sauvegardée!")
                    st.rerun()
            
            with col_reset:
                if is_sim and st.button("🔄 Reset", key=f"reset_{wallet_id}", use_container_width=True):
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
                if st.button("🗑️ Supprimer", key=f"delete_{wallet_id}", use_container_width=True):
                    st.session_state[f"confirm_delete_{wallet_id}"] = True
            
            # Confirm delete
            if st.session_state.get(f"confirm_delete_{wallet_id}"):
                st.warning(f"⚠️ Supprimer définitivement '{wallet['name']}' ?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Oui, supprimer", key=f"yes_del_{wallet_id}"):
                        delete_wallet(wallet_id)
                        del st.session_state[f"confirm_delete_{wallet_id}"]
                        st.rerun()
                with col_no:
                    if st.button("❌ Non", key=f"no_del_{wallet_id}"):
                        del st.session_state[f"confirm_delete_{wallet_id}"]
                        st.rerun()
        
        st.markdown("")  # Spacing

else:
    st.info("📭 Aucun wallet configuré. Crée ton premier wallet ci-dessous!")

# ========== CREATE WALLET ==========
st.markdown("---")
st.subheader("➕ Créer un Wallet")

col1, col2 = st.columns(2)

with col1:
    # Simulation wallet
    st.markdown("""
    <div class="wallet-sim" style="text-align: center; padding: 25px;">
        <div style="font-size: 2.5em;">🎮</div>
        <div style="font-size: 1.3em; font-weight: bold; color: #fff;">Simulation</div>
        <div style="color: #bbb;">Paper trading avec argent virtuel</div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("create_sim"):
        sim_name = st.text_input("Nom", value="Simulation", key="sim_name")
        sim_capital = st.number_input("Capital initial ($)", min_value=100, max_value=1000000, value=10000, key="sim_capital")
        sim_chain = st.selectbox("Chain", list(CHAINS.keys()), format_func=lambda x: f"{CHAINS[x]['icon']} {CHAINS[x]['name']}", key="sim_chain")
        
        if st.form_submit_button("🎮 Créer Simulation", type="primary", use_container_width=True):
            wallet_id = create_wallet('paper', sim_name, sim_capital, sim_chain)
            st.success(f"✅ Wallet simulation '{sim_name}' créé!")
            st.rerun()

with col2:
    # Real wallet
    st.markdown("""
    <div class="wallet-real" style="text-align: center; padding: 25px;">
        <div style="font-size: 2.5em;">💳</div>
        <div style="font-size: 1.3em; font-weight: bold; color: #fff;">Réel</div>
        <div style="color: #bbb;">Trading avec vrais fonds</div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("create_real"):
        real_name = st.text_input("Nom", value="Mon Wallet", key="real_name")
        real_chain = st.selectbox("Chain", list(CHAINS.keys()), format_func=lambda x: f"{CHAINS[x]['icon']} {CHAINS[x]['name']}", key="real_chain")
        real_address = st.text_input("Adresse (0x...)", placeholder="0x...", key="real_address")
        
        if st.form_submit_button("💳 Créer Wallet Réel", use_container_width=True):
            if real_address and real_address.startswith("0x") and len(real_address) == 42:
                wallet_id = create_wallet('real', real_name, 0, real_chain)
                # Update address
                cfg = load_wallets_config()
                for w in cfg['wallets']:
                    if w['id'] == wallet_id:
                        w['address'] = real_address
                        break
                save_wallets_config(cfg)
                st.success(f"✅ Wallet réel '{real_name}' créé!")
                st.rerun()
            else:
                st.error("❌ Adresse invalide")

# ========== LEGEND ==========
st.markdown("---")
with st.expander("ℹ️ Légende"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="wallet-sim" style="padding: 15px;">
            🎮 <strong style="color:#fff;">Simulation</strong> <span style="color:#ccc;">= Paper trading (argent virtuel)</span>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="wallet-real" style="padding: 15px;">
            💳 <strong style="color:#fff;">Réel</strong> <span style="color:#ccc;">= Trading avec vrais fonds</span>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
    ### Profils de Risque
    | Profil | Score Min | Trade % |
    |--------|-----------|---------|
    | 🛡️ Conservateur | 80 | 5% |
    | ⚖️ Modéré | 65 | 10% |
    | 🔥 Agressif | 50 | 20% |
    | 🎰 Degen | 40 | 30% |
    """)
