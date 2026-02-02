"""
👛 Wallets - Gestion unifiée des wallets (simulation + réels)
"""

import streamlit as st
import pandas as pd
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


@st.cache_data(ttl=60)
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


@st.cache_data(ttl=60)
def get_onchain_balance(address: str, chain: str) -> dict:
    """Get on-chain ETH + stablecoin balances"""
    try:
        from web3 import Web3
        address = Web3.to_checksum_address(address)
        
        trader = RealTrader(chain=chain)
        
        eth_balance = trader.w3.eth.get_balance(address)
        eth_amount = float(trader.w3.from_wei(eth_balance, 'ether'))
        eth_price_usd = get_eth_price()
        eth_usd = eth_amount * eth_price_usd
        
        stables = STABLECOINS.get(chain, {})
        stablecoin_usd = 0
        stablecoin_balances = {}
        
        balance_abi = [{"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}]
        
        for symbol, token_addr in stables.items():
            try:
                contract = trader.w3.eth.contract(
                    address=Web3.to_checksum_address(token_addr),
                    abi=balance_abi
                )
                balance = contract.functions.balanceOf(address).call()
                decimals = 6
                token_balance = balance / (10 ** decimals)
                stablecoin_balances[symbol] = token_balance
                stablecoin_usd += token_balance
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
            'status': 'ok'
        }
    except Exception as e:
        return {'eth': 0, 'usd': 0, 'eth_price': 0, 'stablecoins': {}, 'stablecoin_usd': 0, 'error': str(e), 'status': 'error'}


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


def get_status_indicator(wallet, balance_status=None):
    """Retourne l'indicateur de statut visuel"""
    if not wallet.get('enabled'):
        return "⚪", "Désactivé"
    if balance_status == 'error':
        return "🔴", "Erreur connexion"
    if wallet.get('type') == 'real' and not wallet.get('address'):
        return "🟡", "Adresse manquante"
    return "🟢", "Actif"


def render_wallet_card(wallet, config):
    """Affiche une carte wallet avec toutes ses infos"""
    wallet_id = wallet['id']
    wallet_type = wallet.get('type', 'paper')
    is_sim = wallet_type == 'paper'
    
    data = load_wallet_data(wallet_id)
    positions = data.get('positions', {})
    
    # Calculer balances
    balance_status = 'ok'
    if is_sim:
        cash = data.get('portfolio', {}).get('USDC', 0)
        positions_value = sum(
            pos.get('amount', 0) * pos.get('avg_price', 0) 
            for pos in positions.values()
        )
        total_value = cash + positions_value
        eth_amount = 0
        stablecoins = {}
    else:
        wallet_address = wallet.get('address', '')
        if wallet_address:
            chain = wallet.get('chain', 'base')
            balance = get_onchain_balance(wallet_address, chain)
            balance_status = balance.get('status', 'error')
            eth_amount = balance.get('eth', 0)
            eth_usd = balance.get('eth_usd', 0)
            stablecoins = balance.get('stablecoins', {})
            stablecoin_usd = balance.get('stablecoin_usd', 0)
            
            positions_value = sum(
                pos.get('amount', 0) * pos.get('current_price', pos.get('avg_price', 0))
                for pos in positions.values()
            )
            
            cash = eth_usd + stablecoin_usd
            total_value = cash + positions_value
        else:
            cash = 0
            total_value = 0
            positions_value = 0
            eth_amount = 0
            stablecoins = {}
    
    # Calcul P&L
    initial = wallet.get('initial_capital', 0) if is_sim else cash
    pnl = total_value - initial if initial > 0 else 0
    pnl_pct = (pnl / initial * 100) if initial > 0 else 0
    
    # Header avec statut
    status_icon, status_text = get_status_indicator(wallet, balance_status)
    chain_info = CHAINS.get(wallet.get('chain', 'base'), {'icon': '🔵', 'name': 'Base'})
    
    # Container pour le wallet
    with st.container():
        # Titre avec statut
        header_cols = st.columns([0.5, 4, 2])
        with header_cols[0]:
            st.markdown(f"### {status_icon}")
        with header_cols[1]:
            st.markdown(f"### {wallet['name']}")
        with header_cols[2]:
            st.caption(f"{chain_info['icon']} {chain_info['name']} • {status_text}")
        
        # Adresse pour wallets réels
        if not is_sim and wallet.get('address'):
            st.code(wallet.get('address'), language=None)
        
        # Metrics cards
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="💰 Valeur Totale",
                value=f"${total_value:,.2f}",
                delta=f"{pnl:+,.2f} ({pnl_pct:+.1f}%)" if initial > 0 else None,
                delta_color="normal"
            )
        
        with col2:
            if is_sim:
                st.metric(
                    label="💵 Cash (USDC)",
                    value=f"${cash:,.2f}"
                )
            else:
                # Afficher ETH + stablecoins
                eth_display = f"Ξ{eth_amount:.4f}" if eth_amount > 0 else "$0"
                stable_parts = [f"{sym} ${amt:,.2f}" for sym, amt in stablecoins.items() if amt > 0]
                st.metric(
                    label="💵 Liquidités",
                    value=f"${cash:,.2f}",
                    help=f"ETH: {eth_amount:.4f}\n" + "\n".join(stable_parts) if stable_parts else f"ETH: {eth_amount:.4f}"
                )
        
        with col3:
            st.metric(
                label="📊 Positions Ouvertes",
                value=f"{len(positions)} / {wallet.get('max_positions', 10)}",
                delta=f"${positions_value:,.2f}" if positions_value > 0 else None
            )
        
        with col4:
            profile = AI_PROFILES.get(wallet.get('ai_profile', 'modere'), AI_PROFILES['modere'])
            st.metric(
                label="🎯 Profil",
                value=profile['name'].split(' ')[0],  # Emoji only
                help=profile['name']
            )
        
        # Section Positions (si existantes)
        if positions:
            with st.expander(f"📈 Positions ouvertes ({len(positions)})", expanded=False):
                positions_data = []
                for symbol, pos in positions.items():
                    amount = pos.get('amount', 0)
                    avg_price = pos.get('avg_price', 0)
                    current_price = pos.get('current_price', avg_price)
                    value = amount * current_price
                    cost = amount * avg_price
                    pos_pnl = value - cost
                    pos_pnl_pct = (pos_pnl / cost * 100) if cost > 0 else 0
                    
                    # Indicateur de performance
                    if pos_pnl_pct >= 10:
                        perf_icon = "🟢"
                    elif pos_pnl_pct >= 0:
                        perf_icon = "🔵"
                    elif pos_pnl_pct >= -10:
                        perf_icon = "🟡"
                    else:
                        perf_icon = "🔴"
                    
                    positions_data.append({
                        'Statut': perf_icon,
                        'Token': symbol,
                        'Quantité': f"{amount:,.4f}",
                        'Prix Achat': f"${avg_price:.6f}",
                        'Prix Actuel': f"${current_price:.6f}",
                        'Valeur': f"${value:,.2f}",
                        'P&L': f"{pos_pnl:+,.2f} ({pos_pnl_pct:+.1f}%)"
                    })
                
                if positions_data:
                    df = pd.DataFrame(positions_data)
                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True
                    )
        
        # Configuration
        with st.expander("⚙️ Configuration", expanded=False):
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
                enabled = st.checkbox(
                    "✅ Actif", 
                    value=wallet.get('enabled', True), 
                    key=f"enabled_{wallet_id}"
                )
            
            # Boutons d'action
            st.markdown("---")
            action_cols = st.columns([2, 1, 1, 2])
            
            with action_cols[0]:
                if st.button("💾 Sauvegarder", key=f"save_{wallet_id}", type="primary", use_container_width=True):
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
                    st.success("✅ Configuration sauvegardée!")
                    st.rerun()
            
            with action_cols[1]:
                if is_sim:
                    if st.button("🔄 Reset", key=f"reset_{wallet_id}", use_container_width=True):
                        initial = wallet.get('initial_capital', 10000)
                        save_wallet_data(wallet_id, {
                            'portfolio': {'USDC': initial},
                            'positions': {},
                            'history': [],
                            'closed_positions': []
                        })
                        st.success(f"✅ Reset à ${initial:,}")
                        st.rerun()
            
            with action_cols[2]:
                if st.button("🗑️ Supprimer", key=f"delete_{wallet_id}", use_container_width=True):
                    st.session_state[f"confirm_delete_{wallet_id}"] = True
            
            # Confirmation de suppression
            if st.session_state.get(f"confirm_delete_{wallet_id}"):
                st.warning(f"⚠️ Êtes-vous sûr de vouloir supprimer '{wallet['name']}' ?")
                confirm_cols = st.columns(2)
                with confirm_cols[0]:
                    if st.button("✅ Oui, supprimer", key=f"yes_{wallet_id}", type="primary"):
                        delete_wallet(wallet_id)
                        del st.session_state[f"confirm_delete_{wallet_id}"]
                        st.rerun()
                with confirm_cols[1]:
                    if st.button("❌ Annuler", key=f"no_{wallet_id}"):
                        del st.session_state[f"confirm_delete_{wallet_id}"]
                        st.rerun()


# ========== PAGE PRINCIPALE ==========
st.title("👛 Gestion des Wallets")

config = load_wallets_config()
wallets = config.get('wallets', [])

# Séparer wallets simulation et réels
sim_wallets = [w for w in wallets if w.get('type', 'paper') == 'paper']
real_wallets = [w for w in wallets if w.get('type', 'paper') == 'real']

# Tabs principales
tab_sim, tab_real, tab_create = st.tabs([
    f"🎮 Simulation ({len(sim_wallets)})",
    f"💳 Réel ({len(real_wallets)})",
    "➕ Créer"
])

# ========== TAB SIMULATION ==========
with tab_sim:
    if sim_wallets:
        # Résumé des wallets simulation
        total_sim_value = 0
        total_sim_positions = 0
        
        for wallet in sim_wallets:
            data = load_wallet_data(wallet['id'])
            cash = data.get('portfolio', {}).get('USDC', 0)
            positions = data.get('positions', {})
            pos_value = sum(
                pos.get('amount', 0) * pos.get('avg_price', 0) 
                for pos in positions.values()
            )
            total_sim_value += cash + pos_value
            total_sim_positions += len(positions)
        
        # Métriques globales
        st.markdown("### 📊 Résumé Simulation")
        summary_cols = st.columns(4)
        with summary_cols[0]:
            st.metric("🎮 Wallets Actifs", f"{len([w for w in sim_wallets if w.get('enabled')])}/{len(sim_wallets)}")
        with summary_cols[1]:
            st.metric("💰 Valeur Totale", f"${total_sim_value:,.2f}")
        with summary_cols[2]:
            st.metric("📈 Positions Totales", total_sim_positions)
        with summary_cols[3]:
            active_count = len([w for w in sim_wallets if w.get('enabled')])
            st.metric("Statut", "🟢 Trading" if active_count > 0 else "⚪ Inactif")
        
        st.markdown("---")
        
        # Liste des wallets
        for wallet in sim_wallets:
            render_wallet_card(wallet, config)
            st.markdown("---")
    else:
        st.info("📭 Aucun wallet de simulation. Créez-en un dans l'onglet **➕ Créer**!")

# ========== TAB RÉEL ==========
with tab_real:
    if real_wallets:
        # Résumé des wallets réels
        total_real_value = 0
        total_real_positions = 0
        connected_wallets = 0
        
        for wallet in real_wallets:
            if wallet.get('address'):
                connected_wallets += 1
                chain = wallet.get('chain', 'base')
                balance = get_onchain_balance(wallet.get('address'), chain)
                if balance.get('status') == 'ok':
                    total_real_value += balance.get('usd', 0)
            
            data = load_wallet_data(wallet['id'])
            total_real_positions += len(data.get('positions', {}))
        
        # Métriques globales
        st.markdown("### 📊 Résumé Portefeuille Réel")
        summary_cols = st.columns(4)
        with summary_cols[0]:
            st.metric("💳 Wallets Connectés", f"{connected_wallets}/{len(real_wallets)}")
        with summary_cols[1]:
            st.metric("💰 Valeur On-Chain", f"${total_real_value:,.2f}")
        with summary_cols[2]:
            st.metric("📈 Positions Totales", total_real_positions)
        with summary_cols[3]:
            if connected_wallets == len(real_wallets) and connected_wallets > 0:
                st.metric("Statut", "🟢 Connecté")
            elif connected_wallets > 0:
                st.metric("Statut", "🟡 Partiel")
            else:
                st.metric("Statut", "🔴 Déconnecté")
        
        st.markdown("---")
        
        # Avertissement
        st.warning("⚠️ **Attention**: Les wallets réels utilisent de vrais fonds. Tradez de manière responsable!")
        
        # Liste des wallets
        for wallet in real_wallets:
            render_wallet_card(wallet, config)
            st.markdown("---")
    else:
        st.info("📭 Aucun wallet réel configuré. Créez-en un dans l'onglet **➕ Créer**!")

# ========== TAB CRÉER ==========
with tab_create:
    st.markdown("### ➕ Créer un Nouveau Wallet")
    
    create_cols = st.columns(2)
    
    with create_cols[0]:
        st.markdown("#### 🎮 Wallet Simulation")
        st.caption("Paper trading avec capital virtuel - Idéal pour tester vos stratégies sans risque")
        
        with st.form("create_sim", clear_on_submit=True):
            sim_name = st.text_input("📝 Nom du wallet", value="Ma Simulation", placeholder="Ex: Test Agressif")
            sim_capital = st.number_input(
                "💵 Capital initial ($)", 
                min_value=100, 
                max_value=1_000_000, 
                value=10_000,
                step=1000,
                help="Montant virtuel pour commencer"
            )
            sim_chain = st.selectbox(
                "⛓️ Blockchain", 
                list(CHAINS.keys()), 
                format_func=lambda x: f"{CHAINS[x]['icon']} {CHAINS[x]['name']}",
                index=1  # Base par défaut
            )
            
            st.markdown("---")
            
            if st.form_submit_button("🎮 Créer Simulation", type="primary", use_container_width=True):
                wallet_id = create_wallet('paper', sim_name, sim_capital, sim_chain)
                st.success(f"✅ Wallet '{sim_name}' créé avec ${sim_capital:,} de capital!")
                st.balloons()
                st.rerun()
    
    with create_cols[1]:
        st.markdown("#### 💳 Wallet Réel")
        st.caption("Connectez un wallet existant pour trader avec de vrais fonds")
        
        with st.form("create_real", clear_on_submit=True):
            real_name = st.text_input("📝 Nom du wallet", value="Mon Wallet", placeholder="Ex: Wallet Principal")
            real_chain = st.selectbox(
                "⛓️ Blockchain", 
                list(CHAINS.keys()), 
                format_func=lambda x: f"{CHAINS[x]['icon']} {CHAINS[x]['name']}",
                key="real_chain",
                index=1  # Base par défaut
            )
            real_address = st.text_input(
                "🔗 Adresse du wallet", 
                placeholder="0x...",
                help="Adresse Ethereum/EVM de votre wallet"
            )
            
            st.markdown("---")
            
            if st.form_submit_button("💳 Connecter Wallet", use_container_width=True):
                if real_address and real_address.startswith("0x") and len(real_address) == 42:
                    wallet_id = create_wallet('real', real_name, 0, real_chain)
                    cfg = load_wallets_config()
                    for w in cfg['wallets']:
                        if w['id'] == wallet_id:
                            w['address'] = real_address
                            break
                    save_wallets_config(cfg)
                    st.success(f"✅ Wallet '{real_name}' connecté!")
                    st.rerun()
                else:
                    st.error("❌ Adresse invalide. Format attendu: 0x... (42 caractères)")

# Footer
st.markdown("---")
st.caption("💡 Astuce: Commencez par un wallet simulation pour tester vos stratégies avant de passer au réel!")
