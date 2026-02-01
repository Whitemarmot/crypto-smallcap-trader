"""
🐋 Whale Tracker - Monitor whale wallets and copy their trades
"""

import streamlit as st
import sys
import os
from datetime import datetime, timedelta
import json
import time

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'copy-trader'))

from utils.config import SUPPORTED_NETWORKS, load_config
from utils.database import get_db

# Page config
st.set_page_config(
    page_title="🐋 Whale Tracker",
    page_icon="🐋",
    layout="wide"
)

# Load configuration
config = load_config()
db = get_db()

# Custom CSS
st.markdown("""
<style>
    .whale-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        border: 1px solid #0f3460;
    }
    .whale-name {
        font-size: 1.2rem;
        font-weight: bold;
        color: #e94560;
    }
    .whale-address {
        font-family: monospace;
        color: #888;
        font-size: 0.85rem;
    }
    .tx-buy {
        color: #00ff88;
        font-weight: bold;
    }
    .tx-sell {
        color: #ff4444;
        font-weight: bold;
    }
    .alert-high {
        border-left: 4px solid #ff4444;
        padding-left: 10px;
    }
    .alert-medium {
        border-left: 4px solid #ffaa00;
        padding-left: 10px;
    }
    .copy-button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🐋 Whale Tracker")
st.caption("Monitor large wallets and copy their trades")

# Sidebar
with st.sidebar:
    st.subheader("⚙️ Settings")
    
    # Network selection
    network = st.selectbox(
        "Network",
        options=["ethereum", "base"],
        format_func=lambda x: f"{SUPPORTED_NETWORKS.get(x, {}).get('icon', '🔗')} {x.upper()}"
    )
    
    # API Key check
    api_key = config.api_keys.etherscan_api_key if config.api_keys else None
    if not api_key:
        api_key = os.environ.get('ETHERSCAN_API_KEY', '')
    
    if not api_key:
        st.warning("⚠️ No Etherscan API key configured")
        st.caption("Go to Settings to add your API key")
        api_key_input = st.text_input("Or enter API key here:", type="password")
        if api_key_input:
            api_key = api_key_input
    else:
        st.success("✅ API Key configured")
    
    st.markdown("---")
    
    # Refresh settings
    auto_refresh = st.checkbox("Auto-refresh", value=False)
    if auto_refresh:
        refresh_interval = st.slider("Interval (seconds)", 30, 300, 60)

# Initialize session state
if 'tracked_whales' not in st.session_state:
    st.session_state.tracked_whales = []
if 'whale_transactions' not in st.session_state:
    st.session_state.whale_transactions = {}
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = None

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Known Whales",
    "👀 Tracking",
    "📊 Transactions",
    "🚨 Alerts"
])

# ============================================================================
# TAB 1: Known Whales
# ============================================================================
with tab1:
    st.subheader("Known Whale Addresses")
    
    try:
        from whale_api import get_known_whales, KNOWN_WHALES_ETHEREUM, KNOWN_WHALES_BASE
        
        whales = get_known_whales(network)
        
        if not whales:
            st.info(f"No known whales configured for {network}")
        else:
            # Filter options
            col1, col2 = st.columns([2, 1])
            with col1:
                search = st.text_input("🔍 Search by name or address", "")
            with col2:
                type_filter = st.selectbox(
                    "Filter by type",
                    ["All", "exchange", "market_maker", "smart_money", "defi_whale", "whale"]
                )
            
            # Display whales
            displayed = 0
            for address, info in whales.items():
                # Apply filters
                if search:
                    if search.lower() not in info['name'].lower() and search.lower() not in address.lower():
                        continue
                if type_filter != "All" and info.get('type') != type_filter:
                    continue
                
                displayed += 1
                
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        importance_emoji = {
                            "high": "🔴",
                            "medium": "🟡",
                            "low": "🟢"
                        }.get(info.get('importance', 'medium'), "⚪")
                        
                        st.markdown(f"**{importance_emoji} {info['name']}**")
                        st.code(address, language=None)
                        
                        if info.get('description'):
                            st.caption(info['description'])
                        
                        # Type badge
                        type_emoji = {
                            "exchange": "🏦",
                            "market_maker": "📈",
                            "smart_money": "🧠",
                            "defi_whale": "🌊",
                            "whale": "🐋",
                            "foundation": "🏛️",
                            "bridge": "🌉"
                        }.get(info.get('type', 'whale'), "🐋")
                        st.caption(f"{type_emoji} {info.get('type', 'whale').replace('_', ' ').title()}")
                    
                    with col2:
                        # Check if already tracking
                        is_tracking = address in [w['address'] for w in st.session_state.tracked_whales]
                        
                        if is_tracking:
                            if st.button("🚫 Untrack", key=f"untrack_{address}"):
                                st.session_state.tracked_whales = [
                                    w for w in st.session_state.tracked_whales 
                                    if w['address'] != address
                                ]
                                st.rerun()
                        else:
                            if st.button("👀 Track", key=f"track_{address}", type="primary"):
                                st.session_state.tracked_whales.append({
                                    'address': address,
                                    'name': info['name'],
                                    'type': info.get('type', 'whale'),
                                    'network': network
                                })
                                st.success(f"Now tracking {info['name']}")
                                st.rerun()
                    
                    with col3:
                        explorer_url = SUPPORTED_NETWORKS.get(network, {}).get('explorer', 'https://etherscan.io')
                        st.link_button(
                            "🔗 Explorer",
                            f"{explorer_url}/address/{address}",
                            use_container_width=True
                        )
                    
                    st.markdown("---")
            
            if displayed == 0:
                st.info("No whales match your filters")
            else:
                st.caption(f"Showing {displayed} of {len(whales)} whales")
    
    except ImportError as e:
        st.error(f"Could not load whale_api module: {e}")
        st.info("Make sure the copy-trader package is properly installed")
    
    # Add custom whale
    st.markdown("---")
    st.subheader("➕ Add Custom Whale")
    
    with st.form("add_whale"):
        col1, col2 = st.columns(2)
        with col1:
            custom_address = st.text_input("Wallet Address", placeholder="0x...")
        with col2:
            custom_name = st.text_input("Name", placeholder="My Whale")
        
        if st.form_submit_button("Add to Tracking", type="primary"):
            if custom_address and custom_address.startswith("0x") and len(custom_address) == 42:
                st.session_state.tracked_whales.append({
                    'address': custom_address.lower(),
                    'name': custom_name or f"Custom Whale",
                    'type': 'custom',
                    'network': network
                })
                st.success(f"Added {custom_name or custom_address[:10]}... to tracking!")
                st.rerun()
            else:
                st.error("Invalid address format")

# ============================================================================
# TAB 2: Tracking List
# ============================================================================
with tab2:
    st.subheader("👀 Currently Tracking")
    
    if not st.session_state.tracked_whales:
        st.info("You're not tracking any whales yet. Go to 'Known Whales' tab to add some!")
    else:
        for i, whale in enumerate(st.session_state.tracked_whales):
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.markdown(f"**🐋 {whale['name']}**")
                    st.code(whale['address'], language=None)
                    st.caption(f"Network: {whale.get('network', 'ethereum').upper()} | Type: {whale['type']}")
                
                with col2:
                    if st.button("📊 View Txs", key=f"view_{i}"):
                        st.session_state.selected_whale = whale['address']
                        # Will be handled in tab 3
                
                with col3:
                    if st.button("📋 Analyze", key=f"analyze_{i}"):
                        with st.spinner("Analyzing portfolio..."):
                            try:
                                from whale_api import analyze_whale_portfolio_sync
                                portfolio = analyze_whale_portfolio_sync(
                                    whale['address'],
                                    whale.get('network', network),
                                    api_key
                                )
                                st.session_state[f"portfolio_{whale['address']}"] = portfolio
                                st.success("Analysis complete!")
                            except Exception as e:
                                st.error(f"Error: {e}")
                
                with col4:
                    if st.button("🗑️", key=f"remove_{i}"):
                        st.session_state.tracked_whales.pop(i)
                        st.rerun()
                
                # Show portfolio if analyzed
                portfolio_key = f"portfolio_{whale['address']}"
                if portfolio_key in st.session_state:
                    portfolio = st.session_state[portfolio_key]
                    with st.expander("📊 Portfolio Details"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Native Balance", f"{portfolio.get('native_balance', 0):.4f} ETH")
                        with col2:
                            st.metric("Tokens Held", len(portfolio.get('holdings', [])))
                        with col3:
                            if portfolio.get('last_activity'):
                                st.metric("Last Activity", portfolio['last_activity'][:10])
                        
                        if portfolio.get('holdings'):
                            st.markdown("**Token Holdings:**")
                            for holding in portfolio['holdings'][:10]:
                                st.write(f"• {holding['symbol']}: {holding['balance']:.4f}")
                
                st.markdown("---")
        
        # Bulk actions
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh All", type="primary"):
                with st.spinner("Fetching transactions..."):
                    try:
                        from whale_api import get_whale_transactions_sync
                        for whale in st.session_state.tracked_whales:
                            txs = get_whale_transactions_sync(
                                whale['address'],
                                whale.get('network', network),
                                limit=20,
                                api_key=api_key
                            )
                            st.session_state.whale_transactions[whale['address']] = txs
                            time.sleep(0.3)  # Rate limiting
                        st.session_state.last_refresh = datetime.now()
                        st.success("All wallets refreshed!")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        with col2:
            if st.button("🗑️ Clear All"):
                st.session_state.tracked_whales = []
                st.session_state.whale_transactions = {}
                st.rerun()
        
        if st.session_state.last_refresh:
            st.caption(f"Last refreshed: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

# ============================================================================
# TAB 3: Transactions
# ============================================================================
with tab3:
    st.subheader("📊 Recent Transactions")
    
    if not st.session_state.tracked_whales:
        st.info("Start tracking whales to see their transactions")
    elif not st.session_state.whale_transactions:
        st.info("Click 'Refresh All' in the Tracking tab to fetch transactions")
    else:
        # Combine and sort all transactions
        all_txs = []
        for address, txs in st.session_state.whale_transactions.items():
            whale_info = next(
                (w for w in st.session_state.tracked_whales if w['address'] == address),
                {'name': address[:10] + '...', 'address': address}
            )
            for tx in txs:
                tx['whale_name'] = whale_info['name']
                all_txs.append(tx)
        
        # Sort by timestamp
        all_txs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_type = st.selectbox("Type", ["All", "Swaps Only", "Transfers Only"])
        with col2:
            filter_direction = st.selectbox("Direction", ["All", "Buy", "Sell"])
        with col3:
            filter_token = st.text_input("Token Symbol", "")
        
        # Display transactions
        displayed = 0
        for tx in all_txs[:50]:
            # Apply filters
            if filter_type == "Swaps Only" and not tx.get('is_swap'):
                continue
            if filter_type == "Transfers Only" and tx.get('is_swap'):
                continue
            if filter_direction == "Buy" and tx.get('swap_direction') != "buy":
                continue
            if filter_direction == "Sell" and tx.get('swap_direction') != "sell":
                continue
            if filter_token and filter_token.upper() not in tx.get('token_symbol', '').upper():
                continue
            
            displayed += 1
            
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                
                with col1:
                    # Direction indicator
                    if tx.get('swap_direction') == 'buy':
                        direction = "🟢 BUY"
                        direction_class = "tx-buy"
                    elif tx.get('swap_direction') == 'sell':
                        direction = "🔴 SELL"
                        direction_class = "tx-sell"
                    else:
                        direction = "➡️ TRANSFER"
                        direction_class = ""
                    
                    st.markdown(f"**{tx.get('whale_name', 'Unknown')}** - <span class='{direction_class}'>{direction}</span>", 
                               unsafe_allow_html=True)
                    st.caption(f"Hash: {tx.get('hash', '')[:16]}...")
                
                with col2:
                    st.markdown(f"**{tx.get('value', 0):.6f} {tx.get('token_symbol', 'ETH')}**")
                    if tx.get('method_name'):
                        st.caption(f"via {tx.get('method_name')}")
                
                with col3:
                    timestamp = tx.get('timestamp', '')
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            st.caption(dt.strftime('%m/%d %H:%M'))
                        except:
                            st.caption(timestamp[:16])
                
                with col4:
                    # Copy Trade button (dry run)
                    if tx.get('is_swap') and tx.get('token_address'):
                        if st.button("📋 Copy", key=f"copy_{tx.get('hash', '')[:8]}_{displayed}"):
                            st.session_state.copy_trade = tx
                            st.info(f"""
                            **🔄 Copy Trade (DRY RUN)**
                            
                            Would execute:
                            - **Action**: {tx.get('swap_direction', 'swap').upper()}
                            - **Token**: {tx.get('token_symbol')}
                            - **Amount**: Match whale position size
                            
                            ⚠️ This is a simulation - no real trade executed
                            """)
                
                st.markdown("---")
        
        if displayed == 0:
            st.info("No transactions match your filters")
        else:
            st.caption(f"Showing {displayed} transactions")

# ============================================================================
# TAB 4: Alerts
# ============================================================================
with tab4:
    st.subheader("🚨 Whale Alerts")
    
    # Alert settings
    with st.expander("⚙️ Alert Settings"):
        col1, col2 = st.columns(2)
        with col1:
            min_amount = st.number_input("Min Amount (ETH)", value=1.0, min_value=0.0)
        with col2:
            lookback = st.slider("Lookback (minutes)", 15, 1440, 60)
    
    if st.button("🔄 Check for Alerts", type="primary"):
        if not st.session_state.tracked_whales:
            st.warning("No whales being tracked")
        else:
            with st.spinner("Checking for alerts..."):
                try:
                    from whale_api import check_for_alerts_sync
                    
                    all_alerts = []
                    for whale in st.session_state.tracked_whales:
                        alerts = check_for_alerts_sync(
                            whale['address'],
                            whale.get('network', network),
                            min_amount_usd=min_amount * 2000,  # Rough ETH price estimate
                            lookback_minutes=lookback,
                            api_key=api_key
                        )
                        all_alerts.extend(alerts)
                        time.sleep(0.3)
                    
                    st.session_state.alerts = all_alerts
                    if all_alerts:
                        st.success(f"Found {len(all_alerts)} alerts!")
                    else:
                        st.info("No significant activity detected")
                
                except Exception as e:
                    st.error(f"Error checking alerts: {e}")
    
    # Display alerts
    if 'alerts' in st.session_state and st.session_state.alerts:
        for alert in st.session_state.alerts:
            importance_class = f"alert-{alert.get('importance', 'medium')}"
            
            with st.container():
                st.markdown(f"""
                <div class="{importance_class}">
                    <strong>{alert.get('message', 'Whale activity detected')}</strong>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.caption(f"Token: {alert.get('token_symbol', 'ETH')}")
                with col2:
                    st.caption(f"Amount: {alert.get('amount', 0):.4f}")
                with col3:
                    explorer_url = SUPPORTED_NETWORKS.get(alert.get('network', 'ethereum'), {}).get('explorer', '')
                    if explorer_url:
                        st.link_button("View TX", f"{explorer_url}/tx/{alert.get('tx_hash', '')}")
                
                st.markdown("---")
    else:
        st.info("No alerts yet. Click 'Check for Alerts' to scan tracked whales.")
    
    # Copy Trade Modal
    if 'copy_trade' in st.session_state and st.session_state.copy_trade:
        st.markdown("---")
        st.subheader("📋 Copy Trade Preview")
        
        tx = st.session_state.copy_trade
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Original Trade:**")
            st.write(f"• Whale: {tx.get('whale_name', 'Unknown')}")
            st.write(f"• Action: {tx.get('swap_direction', 'swap').upper()}")
            st.write(f"• Token: {tx.get('token_symbol')}")
            st.write(f"• Amount: {tx.get('value', 0):.6f}")
        
        with col2:
            st.markdown("**Your Settings:**")
            copy_percentage = st.slider("Copy Size %", 1, 100, 10)
            use_stop_loss = st.checkbox("Add Stop Loss (-10%)", value=True)
            use_take_profit = st.checkbox("Add Take Profit (+50%)", value=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Execute Copy (DRY RUN)", type="primary"):
                st.success(f"""
                **✅ DRY RUN COMPLETE**
                
                Would have copied trade:
                - {tx.get('swap_direction', 'swap').upper()} {tx.get('value', 0) * copy_percentage / 100:.6f} {tx.get('token_symbol')}
                - Stop Loss: {'Yes (-10%)' if use_stop_loss else 'No'}
                - Take Profit: {'Yes (+50%)' if use_take_profit else 'No'}
                
                ⚠️ No actual trade was executed. Enable live trading in Settings.
                """)
        
        with col2:
            if st.button("❌ Cancel"):
                del st.session_state.copy_trade
                st.rerun()

# Auto-refresh logic
if auto_refresh and st.session_state.tracked_whales:
    time.sleep(refresh_interval)
    st.rerun()

# Footer
st.markdown("---")
st.caption("🐋 Whale Tracker v0.1.0 | Data from Etherscan/Basescan APIs")
