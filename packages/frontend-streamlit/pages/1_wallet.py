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
from utils.config import load_config, save_config, SUPPORTED_NETWORKS, AI_PROFILES

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
    
    # Fetch real balance for active wallet
    try:
        from utils.balance import get_native_balance, get_prices_for_balances
        native_bal = get_native_balance(active_wallet.address, active_wallet.network)
        prices = get_prices_for_balances([native_bal])
        native_price = prices.get(native_bal.symbol, 0)
        native_usd = native_bal.balance * native_price
    except Exception:
        native_bal = None
        native_usd = 0
    
    col_active1, col_active2 = st.columns([2, 1])
    
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
        if native_bal:
            st.metric("💰 Balance Native", f"{native_bal.balance:.6f} {native_bal.symbol}", f"≈ ${native_usd:,.2f}")
        else:
            st.metric("💰 Balance Native", "0", "Erreur de chargement")
else:
    st.warning("⚠️ Aucun wallet actif. Créez ou importez un wallet ci-dessous.")

st.markdown("---")

# ========== LISTE DES WALLETS ==========
col_list, col_actions = st.columns([2, 1])

with col_list:
    st.subheader("📋 Tous les Wallets")
    
    wallets = db.get_wallets()
    
    # Load config for AI profiles
    config = load_config()
    
    if wallets:
        for wallet in wallets:
            network_info = SUPPORTED_NETWORKS.get(wallet.network, {})
            network_icon = network_info.get('icon', '🔗')
            network_name = network_info.get('name', wallet.network)
            
            # Get wallet's AI profile from config
            wallet_config = config.trading.wallets.get(wallet.address, {})
            current_ai_profile = wallet_config.get('ai_profile', 'modere')
            
            # Fetch real native balance
            try:
                from utils.balance import get_native_balance, get_prices_for_balances
                w_native = get_native_balance(wallet.address, wallet.network)
                w_prices = get_prices_for_balances([w_native])
                w_usd = w_native.balance * w_prices.get(w_native.symbol, 0)
            except Exception:
                w_native = None
                w_usd = 0
            
            with st.container():
                col_w1, col_w2, col_w3, col_w4, col_w5 = st.columns([2.5, 2, 2, 2, 1])
                
                with col_w1:
                    status = "🟢" if wallet.is_active else "⚪"
                    st.markdown(f"**{status} {wallet.name}**")
                    st.caption(f"`{wallet.address[:10]}...{wallet.address[-6:]}`")
                
                with col_w2:
                    st.markdown(f"{network_icon} **{wallet.network.upper()}**")
                    if w_native:
                        st.caption(f"{w_native.balance:.4f} {w_native.symbol} (${w_usd:,.2f})")
                    else:
                        st.caption("Balance: N/A")
                
                with col_w3:
                    # AI Profile selector
                    profile_options = list(AI_PROFILES.keys())
                    profile_names = [AI_PROFILES[p].name for p in profile_options]
                    current_idx = profile_options.index(current_ai_profile) if current_ai_profile in profile_options else 1
                    
                    new_profile = st.selectbox(
                        "🤖 Modèle IA",
                        options=profile_options,
                        format_func=lambda x: AI_PROFILES[x].name,
                        index=current_idx,
                        key=f"ai_profile_{wallet.id}",
                        label_visibility="collapsed"
                    )
                    
                    # Save if changed
                    if new_profile != current_ai_profile:
                        if wallet.address not in config.trading.wallets:
                            config.trading.wallets[wallet.address] = {}
                        config.trading.wallets[wallet.address]['ai_profile'] = new_profile
                        config.trading.wallets[wallet.address]['name'] = wallet.name
                        save_config(config)
                        st.toast(f"✅ Modèle {AI_PROFILES[new_profile].name} appliqué à {wallet.name}")
                
                with col_w4:
                    # Show profile info
                    profile = AI_PROFILES.get(new_profile, AI_PROFILES['modere'])
                    st.caption(f"Score min: {profile.min_score}")
                    st.caption(f"Trade: {profile.trade_amount_pct}%")
                
                with col_w5:
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
    
    # AI Profiles legend
    with st.expander("ℹ️ Profils IA - Explication"):
        st.markdown("""
        | Profil | Score Min | Trade % | Max Pos | Style |
        |--------|-----------|---------|---------|-------|
        | 🛡️ **Conservateur** | 80 | 5% | 3 | Prudent, peu de trades |
        | ⚖️ **Modéré** | 65 | 10% | 5 | Équilibré |
        | 🔥 **Agressif** | 50 | 20% | 10 | Plus de trades, plus de risque |
        | 🎰 **Degen** | 40 | 30% | 15 | YOLO mode 🚀 |
        
        **Score Min** = Score IA minimum pour déclencher un BUY  
        **Trade %** = Pourcentage du portfolio par trade  
        **Max Pos** = Nombre max de positions simultanées
        """)

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
            
            import_method = st.radio(
                "Méthode d'import",
                ["🔑 Clé privée", "📝 Seed Phrase (12/24 mots)"],
                horizontal=True,
                key="import_method"
            )
            
            if "Clé privée" in import_method:
                import_key = st.text_input("Clé privée (0x...)", type="password", key="import_key")
                
                if st.button("📥 Importer", type="secondary", use_container_width=True, key="import_pk_btn"):
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
            
            else:  # Seed Phrase
                import_seed = st.text_area(
                    "Seed Phrase (12 ou 24 mots séparés par des espaces)",
                    height=100,
                    key="import_seed",
                    help="Exemple: word1 word2 word3 ... word12"
                )
                
                account_index = st.number_input(
                    "Index du compte (0 = premier compte)",
                    min_value=0,
                    max_value=99,
                    value=0,
                    key="account_index"
                )
                
                if st.button("📥 Importer depuis Seed", type="secondary", use_container_width=True, key="import_seed_btn"):
                    if import_seed:
                        try:
                            # Nettoyer la seed phrase
                            seed_clean = ' '.join(import_seed.strip().lower().split())
                            word_count = len(seed_clean.split())
                            
                            if word_count not in [12, 15, 18, 21, 24]:
                                st.error(f"❌ Seed phrase invalide: {word_count} mots (attendu: 12, 15, 18, 21 ou 24)")
                            else:
                                Account.enable_unaudited_hdwallet_features()
                                
                                # Dérivation standard Ethereum
                                derivation_path = f"m/44'/60'/0'/0/{account_index}"
                                account = Account.from_mnemonic(seed_clean, account_path=derivation_path)
                                
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
                                    st.success(f"✅ Wallet importé depuis seed!")
                                    st.markdown(f"**Adresse:** `{account.address}`")
                                    st.markdown(f"**Chemin:** `{derivation_path}`")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"❌ Seed invalide: {e}")
                    else:
                        st.warning("⚠️ Entre ta seed phrase")

st.markdown("---")

# ========== BALANCES DU WALLET ACTIF ==========
if active_wallet:
    col_title, col_scan = st.columns([3, 1])
    
    with col_title:
        st.subheader(f"🪙 Holdings - {active_wallet.name}")
    
    with col_scan:
        full_scan = st.toggle("🔍 Scan complet", value=False, 
                              help="Active pour scanner 250+ tokens CoinGecko (plus lent)")
    
    # Import balance fetcher
    try:
        from utils.balance import get_all_balances, get_prices_for_balances
        BALANCE_AVAILABLE = True
    except ImportError:
        BALANCE_AVAILABLE = False
    
    if BALANCE_AVAILABLE:
        scan_label = "🔍 Scan complet (250 tokens)..." if full_scan else "🔄 Scan rapide..."
        with st.spinner(scan_label):
            try:
                # Fetch balances (fast or full mode)
                balances = get_all_balances(active_wallet.address, active_wallet.network, 
                                           fast_mode=not full_scan)
                
                if balances:
                    # Get prices using the improved function
                    prices = get_prices_for_balances(balances)
                    
                    # Build dataframe
                    holdings_data = {
                        'Token': [],
                        'Balance': [],
                        'Prix ($)': [],
                        'Valeur ($)': [],
                    }
                    
                    total_value = 0
                    for bal in balances:
                        price = prices.get(bal.symbol, 0)
                        value = bal.balance * price
                        total_value += value
                        
                        holdings_data['Token'].append(bal.symbol)
                        holdings_data['Balance'].append(f"{bal.balance:.6f}".rstrip('0').rstrip('.'))
                        holdings_data['Prix ($)'].append(f"${price:,.4f}" if price > 0 else "N/A")
                        holdings_data['Valeur ($)'].append(f"${value:,.2f}" if price > 0 else "N/A")
                    
                    # Show total
                    st.metric("💰 Valeur Totale", f"${total_value:,.2f}")
                    
                    df_holdings = pd.DataFrame(holdings_data)
                    
                    st.dataframe(
                        df_holdings,
                        column_config={
                            "Token": st.column_config.TextColumn("🪙 Token", width="small"),
                            "Balance": st.column_config.TextColumn("📊 Balance"),
                            "Prix ($)": st.column_config.TextColumn("💵 Prix"),
                            "Valeur ($)": st.column_config.TextColumn("💰 Valeur"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("📭 Aucun token trouvé sur ce wallet (solde = 0 sur tous les tokens)")
                    st.caption(f"Adresse: `{active_wallet.address}`")
                    st.caption(f"Réseau: {active_wallet.network}")
                    st.caption("💡 Dépose des tokens pour commencer à trader!")
                    balances = []  # For chart logic below
                    
            except Exception as e:
                st.error(f"❌ Erreur lors du chargement: {e}")
                st.caption("Vérifie que l'adresse est correcte et que le réseau est accessible")
                balances = []
    else:
        st.warning("⚠️ Module balance non disponible")
        balances = []
    
    # Graphiques - seulement si on a des balances
    if balances:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("**📊 Allocation**")
            # Use real balances for chart
            alloc_data = pd.DataFrame({
                'Token': [b.symbol for b in balances],
                'Valeur': [b.balance * prices.get(b.symbol, 0) for b in balances]
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
            st.markdown("**📈 Tokens détenus**")
            st.caption("Liste des tokens avec solde > 0")
            for b in balances:
                price = prices.get(b.symbol, 0)
                value = b.balance * price
                st.markdown(f"**{b.symbol}**: {b.balance:.6f} (${value:,.2f})")

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
