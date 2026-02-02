"""
👛 Wallet Configuration - Simple et efficace
Configure: Profil risque, Modèle IA, Market Cap, Blockchain
"""

import streamlit as st
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.database import get_db, WalletRecord
from utils.config import load_config, save_config, SUPPORTED_NETWORKS, AI_PROFILES
from utils.llm_providers import get_available_providers, LLM_MODELS

try:
    from eth_account import Account
    WALLET_AVAILABLE = True
except ImportError:
    WALLET_AVAILABLE = False

st.set_page_config(
    page_title="👛 Wallets | SmallCap Trader",
    page_icon="👛",
    layout="wide"
)

st.title("👛 Configuration Wallets")
st.caption("Configure chaque wallet : risque, IA, market cap, blockchain")

db = get_db()
config = load_config()
available_providers = get_available_providers()

# ========== MARKET CAP PRESETS ==========
MARKET_CAP_PRESETS = {
    'micro_cap': {'name': '🔬 Micro Cap (<$1M)', 'min': 0, 'max': 1_000_000},
    'small_cap': {'name': '🐟 Small Cap ($1M-$100M)', 'min': 1_000_000, 'max': 100_000_000},
    'mid_cap': {'name': '🦈 Mid Cap ($100M-$1B)', 'min': 100_000_000, 'max': 1_000_000_000},
    'large_cap': {'name': '🐋 Large Cap (>$1B)', 'min': 1_000_000_000, 'max': 0},
    'all': {'name': '🌍 Tous', 'min': 0, 'max': 0},
}

# ========== LISTE DES WALLETS ==========
wallets = db.get_wallets()

if wallets:
    for wallet in wallets:
        # Get wallet config
        wallet_cfg = config.trading.wallets.get(wallet.address, {})
        
        with st.container():
            # Header
            status = "🟢" if wallet.is_active else "⚪"
            st.markdown(f"### {status} {wallet.name}")
            st.caption(f"`{wallet.address}`")
            
            # 4 columns for 4 settings
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                # 1. Profil de risque
                current_profile = wallet_cfg.get('ai_profile', 'modere')
                new_profile = st.selectbox(
                    "🎯 Profil Risque",
                    options=list(AI_PROFILES.keys()),
                    format_func=lambda x: AI_PROFILES[x].name,
                    index=list(AI_PROFILES.keys()).index(current_profile) if current_profile in AI_PROFILES else 1,
                    key=f"profile_{wallet.id}"
                )
            
            with col2:
                # 2. Modèle IA
                current_provider = wallet_cfg.get('llm_provider', 'openclaw')
                provider_list = list(available_providers.keys()) if available_providers else ['openclaw']
                
                new_provider = st.selectbox(
                    "🤖 Modèle IA",
                    options=provider_list,
                    format_func=lambda x: LLM_MODELS.get(x, {}).get('name', x),
                    index=provider_list.index(current_provider) if current_provider in provider_list else 0,
                    key=f"provider_{wallet.id}"
                )
            
            with col3:
                # 3. Market Cap Range
                current_mcap = wallet_cfg.get('market_cap_preset', 'small_cap')
                new_mcap = st.selectbox(
                    "💰 Market Cap",
                    options=list(MARKET_CAP_PRESETS.keys()),
                    format_func=lambda x: MARKET_CAP_PRESETS[x]['name'],
                    index=list(MARKET_CAP_PRESETS.keys()).index(current_mcap) if current_mcap in MARKET_CAP_PRESETS else 1,
                    key=f"mcap_{wallet.id}"
                )
            
            with col4:
                # 4. Blockchain
                current_network = wallet.network
                new_network = st.selectbox(
                    "⛓️ Blockchain",
                    options=list(SUPPORTED_NETWORKS.keys()),
                    format_func=lambda x: f"{SUPPORTED_NETWORKS[x]['icon']} {SUPPORTED_NETWORKS[x]['name']}",
                    index=list(SUPPORTED_NETWORKS.keys()).index(current_network) if current_network in SUPPORTED_NETWORKS else 0,
                    key=f"network_{wallet.id}"
                )
            
            # Save button
            col_save, col_status, col_delete = st.columns([1, 2, 1])
            
            with col_save:
                if st.button("💾 Sauvegarder", key=f"save_{wallet.id}", type="primary"):
                    # Update config
                    if wallet.address not in config.trading.wallets:
                        config.trading.wallets[wallet.address] = {}
                    
                    config.trading.wallets[wallet.address].update({
                        'name': wallet.name,
                        'ai_profile': new_profile,
                        'llm_provider': new_provider,
                        'market_cap_preset': new_mcap,
                        'network': new_network,
                        'enabled': True
                    })
                    save_config(config)
                    
                    # Update network in DB if changed
                    if new_network != wallet.network:
                        db.cursor.execute(
                            "UPDATE wallets SET network = ? WHERE id = ?",
                            (new_network, wallet.id)
                        )
                        db.conn.commit()
                    
                    st.success("✅ Sauvegardé!")
                    st.rerun()
            
            with col_status:
                # Show current config summary
                profile_info = AI_PROFILES.get(new_profile, AI_PROFILES['modere'])
                mcap_info = MARKET_CAP_PRESETS.get(new_mcap, MARKET_CAP_PRESETS['small_cap'])
                st.caption(f"Score min: {profile_info.min_score} | {mcap_info['name']}")
            
            with col_delete:
                if not wallet.is_active:
                    if st.button("✅ Activer", key=f"activate_{wallet.id}"):
                        db.set_active_wallet(wallet.id)
                        st.rerun()
                else:
                    st.caption("✅ Actif")
            
            st.markdown("---")
else:
    st.info("📭 Aucun wallet configuré")

# ========== AJOUTER UN WALLET ==========
st.subheader("➕ Ajouter un Wallet")

if WALLET_AVAILABLE:
    with st.expander("Créer ou importer un wallet"):
        tab1, tab2 = st.tabs(["🎰 Générer", "📥 Importer"])
        
        with tab1:
            new_name = st.text_input("Nom", value="Mon Wallet", key="new_wallet_name")
            new_net = st.selectbox(
                "Blockchain",
                options=list(SUPPORTED_NETWORKS.keys()),
                format_func=lambda x: f"{SUPPORTED_NETWORKS[x]['icon']} {SUPPORTED_NETWORKS[x]['name']}",
                key="new_wallet_network"
            )
            
            if st.button("🎰 Générer", type="primary"):
                account = Account.create()
                
                wallet_id = db.add_wallet(
                    address=account.address,
                    private_key=account.key.hex(),
                    name=new_name,
                    network=new_net
                )
                
                st.success(f"✅ Wallet créé!")
                st.code(account.address)
                st.warning("⚠️ Sauvegarde ta clé privée!")
                st.code(account.key.hex())
                st.rerun()
        
        with tab2:
            import_name = st.text_input("Nom", value="Wallet Importé", key="import_name")
            import_key = st.text_input("Clé privée", type="password", key="import_key")
            import_net = st.selectbox(
                "Blockchain",
                options=list(SUPPORTED_NETWORKS.keys()),
                format_func=lambda x: f"{SUPPORTED_NETWORKS[x]['icon']} {SUPPORTED_NETWORKS[x]['name']}",
                key="import_network"
            )
            
            if st.button("📥 Importer"):
                try:
                    if import_key.startswith('0x'):
                        import_key = import_key[2:]
                    account = Account.from_key(import_key)
                    
                    wallet_id = db.add_wallet(
                        address=account.address,
                        private_key=import_key,
                        name=import_name,
                        network=import_net
                    )
                    
                    st.success(f"✅ Wallet importé: {account.address[:12]}...")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erreur: {e}")
else:
    st.warning("⚠️ `eth-account` non installé")

# ========== INFO ==========
st.markdown("---")
with st.expander("ℹ️ Comment ça marche"):
    st.markdown("""
    ### 🎯 Profils de Risque
    | Profil | Score Min | Trade % | Style |
    |--------|-----------|---------|-------|
    | 🛡️ Conservateur | 80 | 5% | Peu de trades |
    | ⚖️ Modéré | 65 | 10% | Équilibré |
    | 🔥 Agressif | 50 | 20% | Plus de risque |
    | 🎰 Degen | 40 | 30% | YOLO |
    
    ### 🤖 Modèles IA
    - **🥖 Jean-Michel** = Moi ! (Claude Opus via OpenClaw)
    - **🌐 OpenRouter** = Accès à tous les modèles
    - Autres = API directes
    
    ### 💰 Market Cap
    - **Micro Cap** = High risk, high reward
    - **Small Cap** = Le sweet spot
    - **Mid/Large** = Plus stable
    
    ### ⛓️ Blockchain
    - Configure la chaîne sur laquelle trader
    """)

# Navigation
st.markdown("---")
cols = st.columns(4)
with cols[0]:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/0_dashboard.py")
with cols[1]:
    if st.button("📝 Simulation", use_container_width=True):
        st.switch_page("pages/8_simulation.py")
with cols[2]:
    if st.button("📜 Logs IA", use_container_width=True):
        st.switch_page("pages/9_logs_ia.py")
with cols[3]:
    if st.button("⚙️ Settings", use_container_width=True):
        st.switch_page("pages/5_settings.py")
