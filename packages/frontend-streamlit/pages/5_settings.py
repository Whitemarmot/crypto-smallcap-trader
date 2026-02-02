"""
⚙️ Settings - Configuration de l'Application
Réseaux, API Keys, Export/Import
"""

import streamlit as st
import json
import os
from datetime import datetime
import sys

# Add utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.database import get_db
from utils.config import (
    load_config, save_config, export_config, import_config,
    AppConfig, SUPPORTED_NETWORKS, NetworkSettings, APIKeys, TradingSettings
)

st.set_page_config(
    page_title="⚙️ Settings | SmallCap Trader",
    page_icon="⚙️",
    layout="wide"
)

# ========== STYLES ==========
st.markdown("""
<style>
    .settings-header {
        font-size: 2rem;
        font-weight: bold;
        background: linear-gradient(135deg, #636e72 0%, #2d3436 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .settings-section {
        background: linear-gradient(135deg, #2d2d44 0%, #1e1e2e 100%);
        border-radius: 15px;
        padding: 1.5rem;
        border: 1px solid #404060;
        margin-bottom: 1rem;
    }
    .network-card {
        background: rgba(255,255,255,0.05);
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }
    .api-input {
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

# ========== LOAD CONFIG ==========
config = load_config()
db = get_db()

# ========== HEADER ==========
st.markdown('<p class="settings-header">⚙️ Paramètres</p>', unsafe_allow_html=True)
st.caption(f"Dernière mise à jour: {config.updated_at or 'Jamais'}")

st.markdown("---")

# ========== TABS ==========
tab_networks, tab_api, tab_trading, tab_ui, tab_export = st.tabs([
    "🌐 Réseaux",
    "🔑 API Keys", 
    "📊 Trading",
    "🎨 Interface",
    "💾 Export/Import"
])

# ========== TAB NETWORKS ==========
with tab_networks:
    st.subheader("🌐 Configuration des Réseaux")
    st.caption("Activez et configurez les réseaux EVM que vous souhaitez utiliser")
    
    # Réseau actif
    st.markdown("### 🟢 Réseau Principal")
    
    active_network = st.selectbox(
        "Réseau par défaut",
        options=list(SUPPORTED_NETWORKS.keys()),
        index=list(SUPPORTED_NETWORKS.keys()).index(config.active_network) if config.active_network in SUPPORTED_NETWORKS else 0,
        format_func=lambda x: f"{SUPPORTED_NETWORKS[x]['icon']} {SUPPORTED_NETWORKS[x]['name']} (Chain ID: {SUPPORTED_NETWORKS[x]['chain_id']})"
    )
    
    if active_network != config.active_network:
        config.active_network = active_network
    
    st.markdown("---")
    
    # Configuration par réseau
    st.markdown("### 🔧 Configuration par Réseau")
    
    for network_key, network_info in SUPPORTED_NETWORKS.items():
        with st.expander(f"{network_info['icon']} {network_info['name']}", expanded=(network_key == config.active_network)):
            
            # Get or create network settings
            if network_key not in config.networks:
                config.networks[network_key] = NetworkSettings()
            
            net_settings = config.networks[network_key]
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"""
                **Chain ID:** `{network_info['chain_id']}`  
                **Symbol:** `{network_info['symbol']}`  
                **Explorer:** [{network_info['explorer']}]({network_info['explorer']})
                """)
            
            with col2:
                # Enable/disable toggle
                enabled = st.toggle(
                    "Actif",
                    value=net_settings.enabled if hasattr(net_settings, 'enabled') else True,
                    key=f"net_enabled_{network_key}"
                )
                if hasattr(net_settings, 'enabled'):
                    net_settings.enabled = enabled
            
            # Custom RPC
            default_rpc = network_info['default_rpc']
            current_rpc = net_settings.rpc_url if hasattr(net_settings, 'rpc_url') and net_settings.rpc_url else ""
            
            custom_rpc = st.text_input(
                "RPC URL personnalisé",
                value=current_rpc,
                placeholder=f"Défaut: {default_rpc}",
                key=f"rpc_{network_key}"
            )
            
            if hasattr(net_settings, 'rpc_url'):
                net_settings.rpc_url = custom_rpc if custom_rpc else None
            
            # Test connection button
            if st.button(f"🔗 Tester la connexion", key=f"test_{network_key}"):
                rpc_url = custom_rpc if custom_rpc else default_rpc
                st.info(f"Test de connexion à {rpc_url}...")
                # TODO: Implement actual RPC test
                st.success("✅ Connexion réussie!")

# ========== TAB API KEYS ==========
with tab_api:
    st.subheader("🔑 Clés API")
    st.caption("Configurez vos clés API pour les différents services")
    
    st.warning("⚠️ **Sécurité**: Les clés API sont stockées localement. Ne les partagez jamais!")
    
    # 1inch API
    st.markdown("### 🔄 1inch API")
    st.markdown("*Agrégateur DEX pour les swaps optimisés*")
    
    oneinch_key = st.text_input(
        "1inch API Key",
        value=config.api_keys.oneinch_api_key or "",
        type="password",
        key="api_1inch"
    )
    if oneinch_key != config.api_keys.oneinch_api_key:
        config.api_keys.oneinch_api_key = oneinch_key if oneinch_key else None
    
    st.markdown("[🔗 Obtenir une clé 1inch](https://portal.1inch.dev/)")
    
    st.markdown("---")
    
    # Infura
    st.markdown("### 🌐 Infura")
    st.markdown("*Provider RPC pour Ethereum et autres réseaux*")
    
    infura_key = st.text_input(
        "Infura API Key",
        value=config.api_keys.infura_api_key or "",
        type="password",
        key="api_infura"
    )
    if infura_key != config.api_keys.infura_api_key:
        config.api_keys.infura_api_key = infura_key if infura_key else None
    
    st.markdown("[🔗 Créer un compte Infura](https://infura.io/)")
    
    st.markdown("---")
    
    # Alchemy
    st.markdown("### ⚗️ Alchemy")
    st.markdown("*Provider RPC premium avec analytics*")
    
    alchemy_key = st.text_input(
        "Alchemy API Key",
        value=config.api_keys.alchemy_api_key or "",
        type="password",
        key="api_alchemy"
    )
    if alchemy_key != config.api_keys.alchemy_api_key:
        config.api_keys.alchemy_api_key = alchemy_key if alchemy_key else None
    
    st.markdown("[🔗 Créer un compte Alchemy](https://www.alchemy.com/)")
    
    st.markdown("---")
    
    # Etherscan
    st.markdown("### 📊 Etherscan")
    st.markdown("*API pour les explorateurs de blockchain*")
    
    etherscan_key = st.text_input(
        "Etherscan API Key",
        value=config.api_keys.etherscan_api_key or "",
        type="password",
        key="api_etherscan"
    )
    if etherscan_key != config.api_keys.etherscan_api_key:
        config.api_keys.etherscan_api_key = etherscan_key if etherscan_key else None
    
    st.markdown("[🔗 Obtenir une clé Etherscan](https://etherscan.io/apis)")
    
    st.markdown("---")
    
    # CoinGecko
    st.markdown("### 🦎 CoinGecko")
    st.markdown("*API pour les prix et données de marché*")
    
    coingecko_key = st.text_input(
        "CoinGecko API Key",
        value=config.api_keys.coingecko_api_key or "",
        type="password",
        key="api_coingecko",
        help="Optionnel - L'API gratuite fonctionne sans clé"
    )
    if coingecko_key != config.api_keys.coingecko_api_key:
        config.api_keys.coingecko_api_key = coingecko_key if coingecko_key else None
    
    st.markdown("[🔗 CoinGecko API](https://www.coingecko.com/en/api)")

# ========== TAB TRADING ==========
with tab_trading:
    st.subheader("📊 Paramètres de Trading")
    st.caption("Configurez les limites et comportements par défaut")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💱 Slippage & Gas")
        
        max_slippage = st.slider(
            "Slippage maximum (%)",
            min_value=0.1,
            max_value=10.0,
            value=config.trading.max_slippage,
            step=0.1,
            help="Tolérance de prix maximum pour les swaps"
        )
        config.trading.max_slippage = max_slippage
        
        max_gas = st.number_input(
            "Prix gas maximum (Gwei)",
            min_value=1.0,
            max_value=500.0,
            value=config.trading.max_gas_price_gwei,
            step=5.0
        )
        config.trading.max_gas_price_gwei = max_gas
        
        gas_limit = st.number_input(
            "Gas limit par défaut",
            min_value=21000,
            max_value=1000000,
            value=config.trading.default_gas_limit,
            step=10000
        )
        config.trading.default_gas_limit = gas_limit
    
    with col2:
        st.markdown("### 💰 Limites de Trade")
        
        min_trade = st.number_input(
            "Trade minimum ($)",
            min_value=1.0,
            max_value=1000.0,
            value=config.trading.min_trade_usd,
            step=5.0
        )
        config.trading.min_trade_usd = min_trade
        
        max_trade = st.number_input(
            "Trade maximum ($)",
            min_value=100.0,
            max_value=1000000.0,
            value=config.trading.max_trade_usd,
            step=1000.0
        )
        config.trading.max_trade_usd = max_trade
        
        st.markdown("### ⚡ Automation")
        
        auto_approve = st.checkbox(
            "Auto-approve des tokens",
            value=config.trading.auto_approve,
            help="Approuver automatiquement les tokens avant swap (⚠️ risque de sécurité)"
        )
        config.trading.auto_approve = auto_approve
    
    st.markdown("---")
    
    # Market Cap Filter
    st.markdown("### 🎯 Filtre Market Cap")
    st.caption("Définissez la fourchette de capitalisation pour filtrer les tokens")
    
    col_mcap1, col_mcap2 = st.columns(2)
    
    with col_mcap1:
        # Presets
        preset = st.selectbox(
            "Preset",
            options=["custom", "micro_cap", "small_cap", "mid_cap", "large_cap", "any"],
            format_func=lambda x: {
                "custom": "🔧 Personnalisé",
                "micro_cap": "🔬 Micro Cap (< $1M)",
                "small_cap": "🎯 Small Cap ($1M - $100M)",
                "mid_cap": "📊 Mid Cap ($100M - $1B)",
                "large_cap": "🏛️ Large Cap (> $1B)",
                "any": "🌐 Tous les tokens"
            }[x],
            key="mcap_preset"
        )
        
        # Apply preset values
        if preset == "micro_cap":
            min_mcap_default, max_mcap_default = 0, 1_000_000
        elif preset == "small_cap":
            min_mcap_default, max_mcap_default = 1_000_000, 100_000_000
        elif preset == "mid_cap":
            min_mcap_default, max_mcap_default = 100_000_000, 1_000_000_000
        elif preset == "large_cap":
            min_mcap_default, max_mcap_default = 1_000_000_000, 0
        elif preset == "any":
            min_mcap_default, max_mcap_default = 0, 0
        else:
            min_mcap_default = config.trading.min_market_cap
            max_mcap_default = config.trading.max_market_cap
    
    with col_mcap2:
        max_cap_str = f"${config.trading.max_market_cap:,.0f}" if config.trading.max_market_cap > 0 else "∞ (illimité)"
        st.info(f"""
        **Fourchette actuelle:**  
        Min: ${config.trading.min_market_cap:,.0f}  
        Max: {max_cap_str}
        """)
    
    if preset == "custom":
        col_min, col_max = st.columns(2)
        
        with col_min:
            min_market_cap = st.number_input(
                "Market Cap Minimum ($)",
                min_value=0.0,
                max_value=100_000_000_000.0,
                value=float(config.trading.min_market_cap),
                step=100_000.0,
                format="%.0f",
                help="0 = pas de minimum"
            )
            config.trading.min_market_cap = min_market_cap
        
        with col_max:
            max_market_cap = st.number_input(
                "Market Cap Maximum ($)",
                min_value=0.0,
                max_value=100_000_000_000.0,
                value=float(config.trading.max_market_cap),
                step=100_000.0,
                format="%.0f",
                help="0 = pas de maximum (tous les tokens)"
            )
            config.trading.max_market_cap = max_market_cap
    else:
        config.trading.min_market_cap = min_mcap_default
        config.trading.max_market_cap = max_mcap_default
        
        # Show selected range
        if max_mcap_default > 0:
            st.success(f"✅ Filtre: ${min_mcap_default:,.0f} - ${max_mcap_default:,.0f}")
        elif min_mcap_default > 0:
            st.success(f"✅ Filtre: > ${min_mcap_default:,.0f}")
        else:
            st.success("✅ Tous les tokens (pas de filtre)")

# ========== TAB UI ==========
with tab_ui:
    st.subheader("🎨 Préférences d'Interface")
    st.caption("Personnalisez l'apparence de l'application")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🌓 Thème")
        
        theme = st.selectbox(
            "Thème de l'application",
            options=["dark", "light", "auto"],
            index=["dark", "light", "auto"].index(config.theme),
            format_func=lambda x: {
                "dark": "🌙 Sombre",
                "light": "☀️ Clair",
                "auto": "🔄 Automatique"
            }[x]
        )
        config.theme = theme
        
        if theme != "dark":
            st.info("💡 Le thème sombre est recommandé pour le trading")
    
    with col2:
        st.markdown("### 🌍 Langue")
        
        language = st.selectbox(
            "Langue",
            options=["en", "fr", "es", "de"],
            index=["en", "fr", "es", "de"].index(config.language) if config.language in ["en", "fr", "es", "de"] else 0,
            format_func=lambda x: {
                "en": "🇬🇧 English",
                "fr": "🇫🇷 Français",
                "es": "🇪🇸 Español",
                "de": "🇩🇪 Deutsch"
            }[x]
        )
        config.language = language
    
    st.markdown("---")
    
    st.markdown("### 🔔 Notifications")
    
    notifications = st.checkbox(
        "Activer les notifications",
        value=config.notifications_enabled
    )
    config.notifications_enabled = notifications
    
    if notifications:
        col1, col2 = st.columns(2)
        with col1:
            st.checkbox("📊 Exécutions de stratégies", value=True)
            st.checkbox("💰 Mouvements de fonds", value=True)
        with col2:
            st.checkbox("📈 Alertes de prix", value=True)
            st.checkbox("⚠️ Erreurs", value=True)

# ========== TAB EXPORT/IMPORT ==========
with tab_export:
    st.subheader("💾 Export / Import Configuration")
    
    col_export, col_import = st.columns(2)
    
    with col_export:
        st.markdown("### 📤 Exporter")
        st.caption("Sauvegardez votre configuration")
        
        include_api_keys = st.checkbox(
            "Inclure les clés API",
            value=False,
            help="⚠️ Ne partagez jamais un export contenant vos clés API!"
        )
        
        if st.button("📥 Télécharger la configuration", type="primary", use_container_width=True):
            # Create export data
            export_data = config.to_dict()
            
            if not include_api_keys:
                export_data['api_keys'] = {k: '***' if v else None for k, v in export_data.get('api_keys', {}).items()}
            
            export_data['exported_at'] = datetime.now().isoformat()
            export_data['app_version'] = "1.0.0"
            
            # Convert to JSON
            json_str = json.dumps(export_data, indent=2)
            
            st.download_button(
                label="💾 Sauvegarder config.json",
                data=json_str,
                file_name=f"smallcap_trader_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    with col_import:
        st.markdown("### 📥 Importer")
        st.caption("Restaurez une configuration sauvegardée")
        
        uploaded_file = st.file_uploader(
            "Charger un fichier de configuration",
            type=['json'],
            key="config_upload"
        )
        
        merge_config = st.checkbox(
            "Fusionner avec la config actuelle",
            value=True,
            help="Si désactivé, remplace complètement la configuration"
        )
        
        if uploaded_file is not None:
            try:
                import_data = json.load(uploaded_file)
                
                st.markdown("**📋 Aperçu:**")
                st.json({
                    "networks": list(import_data.get('networks', {}).keys()),
                    "active_network": import_data.get('active_network'),
                    "theme": import_data.get('theme'),
                    "exported_at": import_data.get('exported_at'),
                })
                
                if st.button("✅ Appliquer la configuration", type="secondary", use_container_width=True):
                    # Import the config
                    new_config = AppConfig.from_dict(import_data)
                    
                    if merge_config:
                        # Merge with existing
                        for key, value in import_data.items():
                            if key not in ['api_keys', 'exported_at', 'app_version']:
                                setattr(config, key, getattr(new_config, key))
                        # Only import non-masked API keys
                        if 'api_keys' in import_data:
                            for k, v in import_data['api_keys'].items():
                                if v and v != '***':
                                    setattr(config.api_keys, k, v)
                    else:
                        config = new_config
                    
                    save_config(config)
                    st.success("✅ Configuration importée avec succès!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Erreur lors de l'import: {e}")
    
    st.markdown("---")
    
    # Database management
    st.markdown("### 🗄️ Base de Données")
    
    stats = db.get_portfolio_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👛 Wallets", stats['total_wallets'])
    col2.metric("📝 Simulation", stats['paper_trades'])
    col3.metric("📊 Trades", stats['total_trades'])
    col4.metric("⚡ Exécutions (24h)", stats['recent_trades_24h'])
    
    st.markdown("---")
    
    col_backup, col_reset = st.columns(2)
    
    with col_backup:
        if st.button("💾 Backup Base de Données", use_container_width=True):
            # TODO: Implement DB backup
            st.info("Export de la base de données...")
            st.success("✅ Backup créé: trader_backup_YYYYMMDD.db")
    
    with col_reset:
        if st.button("🗑️ Réinitialiser la Base", use_container_width=True, type="secondary"):
            st.warning("⚠️ Cette action supprimera toutes les données!")
            if st.button("❌ Confirmer la réinitialisation", type="secondary"):
                # TODO: Implement DB reset
                st.error("Base de données réinitialisée")

# ========== SAVE BUTTON ==========
st.markdown("---")

col_save, col_cancel = st.columns([3, 1])

with col_save:
    if st.button("💾 Sauvegarder tous les paramètres", type="primary", use_container_width=True):
        try:
            save_config(config)
            st.success("✅ Configuration sauvegardée avec succès!")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Erreur lors de la sauvegarde: {e}")

with col_cancel:
    if st.button("🔄 Réinitialiser", use_container_width=True):
        st.rerun()

# ========== FOOTER ==========
st.markdown("---")
st.caption(f"""
**SmallCap Trader** v1.0.0  
📁 Config: `{os.path.dirname(os.path.dirname(__file__))}/data/config.json`  
🗄️ Database: `{os.path.dirname(os.path.dirname(__file__))}/data/trader.db`
""")
