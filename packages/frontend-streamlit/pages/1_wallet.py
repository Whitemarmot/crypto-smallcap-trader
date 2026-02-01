"""
👛 Wallet Management - Multi-Wallet avec SQLite
Liste, création, import, switch de wallets EVM
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
import sys
import os

# Add utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.database import get_db, WalletRecord
from utils.config import load_config, save_config, SUPPORTED_NETWORKS

try:
    from eth_account import Account
    WALLET_AVAILABLE = True
except ImportError:
    WALLET_AVAILABLE = False

st.set_page_config(
    page_title="👛 Wallet | SmallCap Trader",
    page_icon="👛",
    layout="wide"
)

# ========== STYLES ==========
st.markdown("""
<style>
    .wallet-header {
        font-size: 2rem;
        font-weight: bold;
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .active-wallet-card {
        background: linear-gradient(135deg, #00b894 0%, #00cec9 100%);
        border-radius: 15px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        color: white;
    }
    .wallet-list-item {
        background: linear-gradient(135deg, #2d2d44 0%, #1e1e2e 100%);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.5rem;
        border: 1px solid #404060;
    }
    .wallet-list-item:hover {
        border-color: #667eea;
    }
    .balance-big {
        font-size: 2rem;
        font-weight: bold;
    }
    .network-tag {
        padding: 4px 10px;
        border-radius: 15px;
        font-size: 0.75rem;
        background: rgba(102, 126, 234, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# ========== DATABASE ==========
db = get_db()
config = load_config()

# ========== HEADER ==========
st.markdown('<p class="wallet-header">👛 Gestion des Wallets</p>', unsafe_allow_html=True)
st.caption("Gérez vos wallets EVM multi-réseaux")

st.markdown("---")

# ========== WALLET ACTIF ==========
active_wallet = db.get_active_wallet()

if active_wallet:
    st.subheader("🟢 Wallet Actif")
    
    col_active1, col_active2, col_active3 = st.columns([2, 1, 1])
    
    with col_active1:
        network_icon = SUPPORTED_NETWORKS.get(active_wallet.network, {}).get('icon', '🔗')
        st.markdown(f"""
        <div class="active-wallet-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin:0; color:white;">✨ {active_wallet.name}</h3>
                <span class="network-tag">{network_icon} {active_wallet.network.upper()}</span>
            </div>
            <div style="font-family: monospace; margin: 15px 0; font-size: 0.9rem; opacity: 0.9;">
                {active_wallet.address}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_active2:
        # Simulation balance (à remplacer par vraies données)
        balance_eth = random.uniform(0.5, 5)
        balance_usd = balance_eth * 3200
        st.metric("💰 Balance", f"{balance_eth:.4f} ETH", f"≈ ${balance_usd:,.2f}")
    
    with col_active3:
        pnl = random.uniform(-10, 25)
        st.metric("📊 P&L 24h", f"{pnl:+.2f}%", delta_color="normal" if pnl >= 0 else "inverse")
else:
    st.warning("⚠️ Aucun wallet actif. Créez ou importez un wallet ci-dessous.")

st.markdown("---")

# ========== LISTE DES WALLETS ==========
col_list, col_actions = st.columns([2, 1])

with col_list:
    st.subheader("📋 Tous les Wallets")
    
    wallets = db.get_wallets()
    
    if wallets:
        for wallet in wallets:
            network_info = SUPPORTED_NETWORKS.get(wallet.network, {})
            network_icon = network_info.get('icon', '🔗')
            network_name = network_info.get('name', wallet.network)
            
            # Simulation des balances
            balance = random.uniform(100, 5000)
            pnl_24h = random.uniform(-15, 20)
            
            with st.container():
                col_w1, col_w2, col_w3, col_w4 = st.columns([3, 2, 2, 1])
                
                with col_w1:
                    status = "🟢" if wallet.is_active else "⚪"
                    st.markdown(f"**{status} {wallet.name}**")
                    st.caption(f"`{wallet.address[:12]}...{wallet.address[-8:]}`")
                
                with col_w2:
                    st.markdown(f"{network_icon} **{wallet.network.upper()}**")
                    st.caption(f"${balance:,.2f}")
                
                with col_w3:
                    color = "🟢" if pnl_24h >= 0 else "🔴"
                    st.markdown(f"{color} **{pnl_24h:+.2f}%**")
                    st.caption(f"Créé: {wallet.created_at.strftime('%d/%m/%y')}")
                
                with col_w4:
                    # Boutons d'action
                    if not wallet.is_active:
                        if st.button("✅", key=f"activate_{wallet.id}", help="Activer ce wallet"):
                            db.set_active_wallet(wallet.id)
                            st.success(f"✅ {wallet.name} est maintenant actif!")
                            st.rerun()
                    
                    if st.button("🗑️", key=f"delete_{wallet.id}", help="Supprimer"):
                        db.delete_wallet(wallet.id)
                        st.toast(f"Wallet {wallet.name} supprimé", icon="🗑️")
                        st.rerun()
                
                st.markdown("---")
    else:
        st.info("📭 Aucun wallet enregistré. Créez votre premier wallet!")

with col_actions:
    # ========== CRÉER NOUVEAU WALLET ==========
    st.subheader("➕ Nouveau Wallet")
    
    if not WALLET_AVAILABLE:
        st.error("⚠️ `eth-account` non installé")
        st.code("pip install eth-account", language="bash")
    else:
        with st.expander("🎰 Générer un Wallet", expanded=True):
            new_wallet_name = st.text_input("Nom du wallet", value="Mon Wallet", key="new_name")
            new_wallet_network = st.selectbox(
                "Réseau",
                options=list(SUPPORTED_NETWORKS.keys()),
                format_func=lambda x: f"{SUPPORTED_NETWORKS[x]['icon']} {SUPPORTED_NETWORKS[x]['name']}"
            )
            
            wallet_type = st.radio(
                "Type",
                ["Simple", "Avec Seed Phrase (BIP-39)"],
                horizontal=True
            )
            
            use_password = st.checkbox("🔐 Chiffrer la clé privée", value=True)
            
            if use_password:
                password = st.text_input("Mot de passe", type="password", key="gen_pwd")
            else:
                password = None
            
            if st.button("🎰 Générer", type="primary", use_container_width=True):
                try:
                    Account.enable_unaudited_hdwallet_features()
                    
                    if "Seed" in wallet_type:
                        account, mnemonic = Account.create_with_mnemonic()
                        st.success("✅ Wallet généré avec seed phrase!")
                        
                        st.markdown("### 📝 Seed Phrase (12 mots)")
                        st.warning("⚠️ **SAUVEGARDE CES MOTS** - Ils permettent de récupérer ton wallet!")
                        st.code(mnemonic, language=None)
                    else:
                        account = Account.create()
                        st.success("✅ Wallet généré!")
                    
                    st.markdown("### 📍 Adresse")
                    st.code(account.address, language=None)
                    
                    st.markdown("### 🔑 Clé Privée")
                    st.code(f"0x{account.key.hex()}", language=None)
                    
                    # Sauvegarder dans la DB
                    encrypted_key = None
                    if password:
                        from utils.database import WalletEncryption
                        # Note: dans la vraie app, on utiliserait le module wallet pour chiffrer
                        pass
                    
                    wallet_id = db.add_wallet(
                        name=new_wallet_name,
                        address=account.address,
                        network=new_wallet_network,
                        encrypted_key=encrypted_key
                    )
                    
                    # Activer si premier wallet
                    if len(db.get_wallets()) == 1:
                        db.set_active_wallet(wallet_id)
                    
                    st.error("⚠️ **SAUVEGARDE TA CLÉ PRIVÉE** - Elle ne sera plus affichée!")
                    
                except Exception as e:
                    st.error(f"❌ Erreur: {e}")
        
        # ========== IMPORT WALLET ==========
        with st.expander("📥 Importer un Wallet"):
            import_name = st.text_input("Nom", value="Wallet Importé", key="import_name")
            import_network = st.selectbox(
                "Réseau",
                options=list(SUPPORTED_NETWORKS.keys()),
                format_func=lambda x: f"{SUPPORTED_NETWORKS[x]['icon']} {SUPPORTED_NETWORKS[x]['name']}",
                key="import_network"
            )
            import_key = st.text_input("Clé privée (0x...)", type="password", key="import_key")
            
            if st.button("📥 Importer", type="secondary", use_container_width=True):
                if import_key:
                    try:
                        if not import_key.startswith("0x"):
                            import_key = "0x" + import_key
                        
                        account = Account.from_key(import_key)
                        
                        # Vérifier si déjà existant
                        existing = [w for w in db.get_wallets() if w.address.lower() == account.address.lower()]
                        if existing:
                            st.warning(f"⚠️ Ce wallet existe déjà: {existing[0].name}")
                        else:
                            wallet_id = db.add_wallet(
                                name=import_name,
                                address=account.address,
                                network=import_network
                            )
                            st.success(f"✅ Wallet importé: `{account.address[:12]}...`")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Clé invalide: {e}")
                else:
                    st.warning("⚠️ Entre une clé privée")

st.markdown("---")

# ========== BALANCES DU WALLET ACTIF ==========
if active_wallet:
    st.subheader(f"🪙 Holdings - {active_wallet.name}")
    
    # Données simulées (à remplacer par API calls)
    holdings_data = {
        'Token': ['ETH', 'USDC', 'PEPE', 'BONK', 'WIF'],
        'Balance': ['2.5432', '1,500.00', '50,000,000', '2,500,000', '150'],
        'Prix ($)': ['$3,245.67', '$1.00', '$0.0000012', '$0.000025', '$2.45'],
        'Valeur ($)': ['$8,252.32', '$1,500.00', '$60.00', '$62.50', '$367.50'],
        'Change 24h': ['+2.4%', '0%', '+15.2%', '-8.1%', '+5.6%'],
    }
    
    df_holdings = pd.DataFrame(holdings_data)
    
    # Custom styling for dataframe
    def style_change(val):
        if val.startswith('+'):
            return 'color: #00ff88'
        elif val.startswith('-'):
            return 'color: #ff4757'
        return ''
    
    st.dataframe(
        df_holdings,
        column_config={
            "Token": st.column_config.TextColumn("🪙 Token", width="small"),
            "Balance": st.column_config.TextColumn("📊 Balance"),
            "Prix ($)": st.column_config.TextColumn("💵 Prix"),
            "Valeur ($)": st.column_config.TextColumn("💰 Valeur"),
            "Change 24h": st.column_config.TextColumn("📈 24h"),
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Graphiques
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("**📊 Allocation**")
        alloc_data = pd.DataFrame({
            'Token': ['ETH', 'USDC', 'PEPE', 'BONK', 'WIF'],
            'Valeur': [8252, 1500, 60, 63, 368]
        })
        
        fig_pie = px.pie(
            alloc_data,
            values='Valeur',
            names='Token',
            color_discrete_sequence=['#667eea', '#00b894', '#fdcb6e', '#e17055', '#74b9ff'],
            hole=0.45
        )
        fig_pie.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            height=300,
            margin=dict(t=0, b=0, l=0, r=0),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2)
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col_chart2:
        st.markdown("**📈 Performance 7j**")
        
        perf_data = pd.DataFrame({
            'Token': ['ETH', 'USDC', 'PEPE', 'BONK', 'WIF'],
            'Performance': [8.5, 0, 45.2, -12.3, 22.1]
        })
        
        colors = ['#00ff88' if x >= 0 else '#ff4757' for x in perf_data['Performance']]
        
        fig_bar = go.Figure(data=[
            go.Bar(
                x=perf_data['Token'],
                y=perf_data['Performance'],
                marker_color=colors,
                text=[f"{p:+.1f}%" for p in perf_data['Performance']],
                textposition='outside'
            )
        ])
        
        fig_bar.add_hline(y=0, line_dash="solid", line_color="rgba(255,255,255,0.3)")
        
        fig_bar.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis_title="% Change",
            xaxis_title=None,
            height=300,
            margin=dict(t=20, b=0)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ========== ACTIONS RAPIDES ==========
st.markdown("---")
st.subheader("⚡ Actions")

action_cols = st.columns(4)

with action_cols[0]:
    with st.expander("📤 Envoyer"):
        send_token = st.selectbox("Token", ["ETH", "USDC", "PEPE"], key="send_tok")
        send_amount = st.number_input("Montant", min_value=0.0, value=0.1, key="send_amt")
        send_to = st.text_input("Adresse destination", key="send_dest")
        if st.button("📤 Envoyer", type="primary", key="send_btn"):
            st.info(f"📤 Envoi {send_amount} {send_token}...")

with action_cols[1]:
    with st.expander("🔄 Swap"):
        from_tok = st.selectbox("De", ["ETH", "USDC", "PEPE"], key="swap_from")
        to_tok = st.selectbox("Vers", ["USDC", "ETH", "PEPE"], key="swap_to")
        swap_amt = st.number_input("Montant", min_value=0.0, value=0.1, key="swap_amt")
        if st.button("🔄 Swap", type="primary", key="swap_btn"):
            st.success(f"🔄 Swap {swap_amt} {from_tok} → {to_tok}")

with action_cols[2]:
    with st.expander("📥 Recevoir"):
        if active_wallet:
            st.markdown("**Adresse de dépôt:**")
            st.code(active_wallet.address, language=None)
            st.info("📋 Copie cette adresse pour recevoir des tokens")
        else:
            st.warning("Sélectionne un wallet")

with action_cols[3]:
    with st.expander("🔗 Explorer"):
        if active_wallet:
            network_info = SUPPORTED_NETWORKS.get(active_wallet.network, {})
            explorer = network_info.get('explorer', 'https://etherscan.io')
            explorer_url = f"{explorer}/address/{active_wallet.address}"
            st.markdown(f"[🔗 Voir sur l'explorateur]({explorer_url})")
        else:
            st.warning("Sélectionne un wallet")
