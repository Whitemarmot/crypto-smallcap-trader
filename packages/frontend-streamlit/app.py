"""
Crypto SmallCap Trader - Dashboard Principal
Interface moderne et organisée
"""

import streamlit as st
from datetime import datetime
import json
import os
import requests

st.set_page_config(
    page_title="🚀 SmallCap Trader",
    page_icon="🚀",
    layout="wide"
)

# ═══════════════════════════════════════════════════════════════════════════════
# 📁 CONFIGURATION & PATHS
# ═══════════════════════════════════════════════════════════════════════════════

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
WALLETS_DIR = os.path.join(DATA_DIR, 'wallets')
WALLETS_CONFIG = os.path.join(WALLETS_DIR, 'config.json')
BOT_CONFIG = os.path.join(DATA_DIR, 'bot_config.json')


def load_json(path, default):
    """Charge un fichier JSON de manière sécurisée"""
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default


# ═══════════════════════════════════════════════════════════════════════════════
# 🌐 API CALLS
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_fear_greed_index():
    """Récupère le Fear & Greed Index depuis Alternative.me"""
    try:
        resp = requests.get(
            'https://api.alternative.me/fng/?limit=1',
            timeout=5
        )
        data = resp.json()
        if data.get('data'):
            value = int(data['data'][0]['value'])
            classification = data['data'][0]['value_classification']
            return {'value': value, 'label': classification}
    except:
        pass
    return {'value': None, 'label': 'N/A'}


@st.cache_data(ttl=120)
def get_real_wallet_balance(address: str, chain: str) -> dict:
    """Récupère le solde on-chain pour les wallets réels"""
    try:
        from web3 import Web3
        
        rpc_urls = {
            'base': 'https://mainnet.base.org',
            'ethereum': 'https://eth.llamarpc.com',
            'arbitrum': 'https://arb1.arbitrum.io/rpc',
        }
        
        stables = {
            'base': {'USDC': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'},
            'ethereum': {'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'},
        }
        
        w3 = Web3(Web3.HTTPProvider(rpc_urls.get(chain, rpc_urls['base'])))
        address = Web3.to_checksum_address(address)
        
        eth_balance = w3.eth.get_balance(address)
        eth_amount = float(w3.from_wei(eth_balance, 'ether'))
        
        resp = requests.get(
            'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest',
            headers={'X-CMC_PRO_API_KEY': '849ddcc694a049708d0b5392486d6eaa'},
            params={'symbol': 'ETH'}, timeout=10
        )
        eth_price = resp.json()['data']['ETH']['quote']['USD']['price']
        eth_usd = eth_amount * eth_price
        
        stable_usd = 0
        chain_stables = stables.get(chain, {})
        balance_abi = [{"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}]
        
        for symbol, token_addr in chain_stables.items():
            try:
                contract = w3.eth.contract(address=Web3.to_checksum_address(token_addr), abi=balance_abi)
                bal = contract.functions.balanceOf(address).call()
                stable_usd += bal / 1e6
            except:
                pass
        
        return {'eth': eth_amount, 'eth_usd': eth_usd, 'stable_usd': stable_usd, 'total_usd': eth_usd + stable_usd}
    except Exception as e:
        return {'eth': 0, 'eth_usd': 0, 'stable_usd': 0, 'total_usd': 0, 'error': str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# 📊 CHARGEMENT DES DONNÉES
# ═══════════════════════════════════════════════════════════════════════════════

wallets_config = load_json(WALLETS_CONFIG, {'wallets': []})
bot_config = load_json(BOT_CONFIG, {})
wallets = wallets_config.get('wallets', [])

# Calcul des totaux
total_value = 0
total_positions = 0
total_cash = 0
total_pnl = 0
win_count = 0
total_trades = 0

for w in wallets:
    wallet_path = os.path.join(WALLETS_DIR, f"{w['id']}.json")
    data = load_json(wallet_path, {'portfolio': {'USDC': 0}, 'positions': {}, 'closed_positions': []})
    
    positions = data.get('positions', {})
    closed = data.get('closed_positions', [])
    
    # Cash selon le type de wallet
    if w.get('type') == 'real' and w.get('address'):
        balance = get_real_wallet_balance(w['address'], w.get('chain', 'base'))
        cash = balance.get('total_usd', 0)
    else:
        cash = data.get('portfolio', {}).get('USDC', 0)
    
    # Valeur des positions
    pos_value = 0
    for sym, pos in positions.items():
        pos_value += pos.get('amount', 0) * pos.get('avg_price', 0)
    
    total_value += cash + pos_value
    total_cash += cash
    total_positions += len(positions)
    
    # P&L et Win rate
    for p in closed:
        pnl = p.get('pnl_usd', 0)
        total_pnl += pnl
        if pnl > 0:
            win_count += 1
    total_trades += len(closed)

win_rate = round(win_count / total_trades * 100) if total_trades > 0 else 0

# Fear & Greed Index
fear_greed = get_fear_greed_index()


# ═══════════════════════════════════════════════════════════════════════════════
# 🎨 SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("🚀 SmallCap Trader")
    st.caption("Bot trading IA pour smallcaps")
    
    st.divider()
    
    st.subheader("📍 Navigation")
    st.page_link("pages/1_wallet.py", label="👛 Wallets", icon="👛")
    st.page_link("pages/9_positions.py", label="📊 Positions", icon="📊")
    st.page_link("pages/2_trades.py", label="📈 Trades", icon="📈")
    st.page_link("pages/9_logs_ia.py", label="🤖 Logs IA", icon="🤖")
    
    st.divider()
    
    # Mini status bot
    bot_enabled = bot_config.get('enabled', False)
    if bot_enabled:
        st.success("🟢 Bot actif")
    else:
        st.info("⚪ Bot en pause")
    
    st.divider()
    st.caption(f"v0.3.0 | {datetime.now().strftime('%d/%m/%Y %H:%M')}")


# ═══════════════════════════════════════════════════════════════════════════════
# 🏠 PAGE PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════════

st.title("🚀 Dashboard Crypto SmallCap")
st.caption("Vue d'ensemble de votre portfolio et du marché")

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 📈 SECTION: MÉTRIQUES PRINCIPALES
# ═══════════════════════════════════════════════════════════════════════════════

with st.container():
    st.subheader("📈 Résumé Portfolio")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 Valeur Totale",
            value=f"${total_value:,.2f}",
            help="Valeur totale du portfolio (cash + positions)"
        )
    
    with col2:
        pnl_delta = f"+${total_pnl:,.2f}" if total_pnl >= 0 else f"-${abs(total_pnl):,.2f}"
        st.metric(
            label="📊 P&L Total",
            value=f"${total_pnl:,.2f}",
            delta=f"{win_rate}% win rate" if total_trades > 0 else None,
            delta_color="normal" if total_pnl >= 0 else "inverse",
            help="Profit/Perte réalisé sur les trades clôturés"
        )
    
    with col3:
        st.metric(
            label="🎯 Positions Actives",
            value=f"{total_positions}",
            delta=f"{len(wallets)} wallets",
            delta_color="off",
            help="Nombre de positions ouvertes"
        )
    
    with col4:
        # Fear & Greed avec couleur selon le niveau
        fg_value = fear_greed['value']
        fg_label = fear_greed['label']
        
        if fg_value is not None:
            if fg_value <= 25:
                fg_emoji = "😱"  # Extreme Fear
            elif fg_value <= 45:
                fg_emoji = "😰"  # Fear
            elif fg_value <= 55:
                fg_emoji = "😐"  # Neutral
            elif fg_value <= 75:
                fg_emoji = "😊"  # Greed
            else:
                fg_emoji = "🤑"  # Extreme Greed
            
            st.metric(
                label=f"{fg_emoji} Fear & Greed",
                value=f"{fg_value}/100",
                delta=fg_label,
                delta_color="off",
                help="Indicateur de sentiment du marché crypto"
            )
        else:
            st.metric(
                label="😐 Fear & Greed",
                value="N/A",
                help="Indicateur indisponible"
            )

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 👛 SECTION: WALLETS & BOT STATUS
# ═══════════════════════════════════════════════════════════════════════════════

col_wallets, col_status = st.columns([2, 1])

with col_wallets:
    with st.container():
        st.subheader("👛 Mes Wallets")
        
        if wallets:
            for w in wallets:
                wallet_path = os.path.join(WALLETS_DIR, f"{w['id']}.json")
                data = load_json(wallet_path, {'portfolio': {'USDC': 0}, 'positions': {}})
                positions = data.get('positions', {})
                
                # Cash selon le type
                if w.get('type') == 'real' and w.get('address'):
                    balance = get_real_wallet_balance(w['address'], w.get('chain', 'base'))
                    cash = balance.get('total_usd', 0)
                else:
                    cash = data.get('portfolio', {}).get('USDC', 0)
                
                pos_value = sum(p.get('amount', 0) * p.get('avg_price', 0) for p in positions.values())
                total = cash + pos_value
                
                # Badges visuels
                type_badge = "🎮 Paper" if w.get('type') == 'paper' else "💳 Real"
                status_icon = "🟢" if w.get('enabled') else "⚪"
                chain = w.get('chain', 'base').upper()
                
                with st.expander(f"{status_icon} **{w['name']}** — ${total:,.2f}", expanded=False):
                    info_col1, info_col2 = st.columns(2)
                    
                    with info_col1:
                        st.write(f"**Type:** {type_badge}")
                        st.write(f"**Chain:** {chain}")
                        st.write(f"**Positions:** {len(positions)}")
                    
                    with info_col2:
                        st.write(f"**Cash:** ${cash:,.2f}")
                        st.write(f"**Investi:** ${pos_value:,.2f}")
                        if w.get('ai_profile'):
                            st.write(f"**Profil IA:** {w['ai_profile']}")
                    
                    if w.get('address'):
                        st.code(w['address'], language=None)
        else:
            st.warning("⚠️ Aucun wallet configuré")
            st.info("👉 Créez votre premier wallet dans la section Wallets")


with col_status:
    with st.container():
        st.subheader("🤖 Status Bot")
        
        bot_enabled = bot_config.get('enabled', False)
        
        if bot_enabled:
            st.success("✅ Bot actif")
            st.caption("Le bot analyse le marché toutes les heures via cron")
            if bot_config.get('updated_at'):
                st.caption(f"📅 Dernière config: {bot_config['updated_at']}")
        else:
            st.info("⏸️ Bot en pause")
            st.caption("Activez le bot pour commencer le trading automatique")
        
        st.divider()
        
        # Checklist de configuration
        st.subheader("✅ Checklist")
        
        has_wallet = len(wallets) > 0
        has_funds = total_value > 0
        has_config = any(w.get('ai_profile') for w in wallets)
        bot_running = bot_config.get('enabled', False)
        
        steps = [
            ("👛 Créer un wallet", has_wallet),
            ("💰 Ajouter des fonds", has_funds),
            ("⚙️ Configurer l'IA", has_config),
            ("🤖 Activer le bot", bot_running),
        ]
        
        progress = sum(1 for _, done in steps if done)
        st.progress(progress / len(steps), text=f"{progress}/{len(steps)} étapes")
        
        for step, done in steps:
            if done:
                st.write(f"✅ ~~{step}~~")
            else:
                st.write(f"⬜ {step}")
        
        if progress == len(steps):
            st.balloons()
            st.success("🎉 Configuration complète!")


st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 🧭 SECTION: NAVIGATION RAPIDE
# ═══════════════════════════════════════════════════════════════════════════════

with st.container():
    st.subheader("🧭 Actions Rapides")
    
    nav_col1, nav_col2, nav_col3, nav_col4 = st.columns(4)
    
    with nav_col1:
        if st.button("👛 Gérer Wallets", use_container_width=True, type="primary"):
            st.switch_page("pages/1_wallet.py")
    
    with nav_col2:
        if st.button("📊 Voir Positions", use_container_width=True):
            st.switch_page("pages/9_positions.py")
    
    with nav_col3:
        if st.button("📈 Historique Trades", use_container_width=True):
            st.switch_page("pages/2_trades.py")
    
    with nav_col4:
        if st.button("🤖 Logs IA", use_container_width=True):
            st.switch_page("pages/9_logs_ia.py")


# ═══════════════════════════════════════════════════════════════════════════════
# 📊 SECTION: STATS RAPIDES (si on a des trades)
# ═══════════════════════════════════════════════════════════════════════════════

if total_trades > 0:
    st.divider()
    
    with st.container():
        st.subheader("📊 Statistiques de Trading")
        
        stat_col1, stat_col2, stat_col3 = st.columns(3)
        
        with stat_col1:
            st.metric("🔄 Trades Total", total_trades)
        
        with stat_col2:
            st.metric("✅ Trades Gagnants", win_count)
        
        with stat_col3:
            st.metric("❌ Trades Perdants", total_trades - win_count)


# ═══════════════════════════════════════════════════════════════════════════════
# 📌 FOOTER
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()

footer_col1, footer_col2, footer_col3 = st.columns(3)

with footer_col1:
    st.caption("🚀 SmallCap Trader v0.3.0")

with footer_col2:
    st.caption(f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}")

with footer_col3:
    st.caption("Made with ❤️ by Jean-Michel 🥖")
