"""
Crypto SmallCap Trader - Historique des Trades
Suivi et analyse des trades passés
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.database import get_db

st.set_page_config(
    page_title="📈 Trades | SmallCap Trader",
    page_icon="📈",
    layout="wide"
)

db = get_db()

st.title("📈 Historique des Trades")
st.markdown("Analysez vos performances de trading")

# Fetch real trades
trades = db.get_trades(limit=100)
stats = db.get_portfolio_stats()

# Stats
st.markdown("---")
stat_cols = st.columns(4)

with stat_cols[0]:
    st.metric("📊 Total Trades", str(stats['total_trades']))
    
with stat_cols[1]:
    st.metric("📅 Trades (24h)", str(stats['recent_trades_24h']))
    
with stat_cols[2]:
    st.metric("🎯 Win Rate", "--", "Pas encore de données")
    
with stat_cols[3]:
    st.metric("💰 P&L Total", "--", "Pas encore de données")

st.markdown("---")

# Trades list
st.subheader("📜 Liste des Trades")

if trades:
    # Convert to dataframe
    trades_data = []
    for trade in trades:
        trades_data.append({
            'Date': trade.get('created_at', 'N/A'),
            'Type': trade.get('trade_type', 'swap').upper(),
            'Token In': trade.get('token_in', '?'),
            'Token Out': trade.get('token_out', '?'),
            'Amount In': trade.get('amount_in', '0'),
            'Amount Out': trade.get('amount_out', '0'),
            'Status': trade.get('status', 'pending'),
            'TX Hash': trade.get('tx_hash', 'N/A')[:16] + '...' if trade.get('tx_hash') else 'N/A'
        })
    
    df = pd.DataFrame(trades_data)
    
    # Style status
    def style_status(val):
        colors = {
            'confirmed': 'background-color: #00ff8822',
            'pending': 'background-color: #ffaa0022',
            'failed': 'background-color: #ff000022'
        }
        return colors.get(val.lower(), '')
    
    st.dataframe(
        df,
        column_config={
            "Date": st.column_config.DatetimeColumn("📅 Date", format="DD/MM/YY HH:mm"),
            "Type": st.column_config.TextColumn("📊 Type"),
            "Token In": st.column_config.TextColumn("📥 Token In"),
            "Token Out": st.column_config.TextColumn("📤 Token Out"),
            "Amount In": st.column_config.TextColumn("💰 Amount In"),
            "Amount Out": st.column_config.TextColumn("💰 Amount Out"),
            "Status": st.column_config.TextColumn("✅ Status"),
            "TX Hash": st.column_config.TextColumn("🔗 TX"),
        },
        hide_index=True,
        use_container_width=True
    )
else:
    st.info("📭 Aucun trade enregistré")
    st.markdown("""
    Les trades apparaîtront ici une fois que :
    1. ✅ Tu auras configuré un wallet avec des fonds
    2. ✅ Tu auras créé une stratégie de trading
    3. ✅ Le bot aura exécuté des trades
    """)

st.markdown("---")

# Manual trade form (for testing)
with st.expander("➕ Enregistrer un Trade Manuel"):
    st.caption("Pour tests ou trades manuels effectués hors du bot")
    
    col1, col2 = st.columns(2)
    
    with col1:
        trade_type = st.selectbox("Type", ["buy", "sell", "swap"])
        token_in = st.text_input("Token In", value="ETH")
        amount_in = st.text_input("Amount In", value="0.1")
    
    with col2:
        token_out = st.text_input("Token Out", value="USDC")
        amount_out = st.text_input("Amount Out", value="0")
        tx_hash = st.text_input("TX Hash (optionnel)")
    
    if st.button("💾 Enregistrer", type="primary"):
        try:
            db.add_trade(
                wallet_id=1,  # Default wallet
                trade_type=trade_type,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
                tx_hash=tx_hash or None,
                status='confirmed'
            )
            st.success("✅ Trade enregistré!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erreur: {e}")

# Navigation
st.markdown("---")
nav_cols = st.columns(4)

with nav_cols[0]:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/0_dashboard.py")

with nav_cols[1]:
    if st.button("👛 Wallets", use_container_width=True):
        st.switch_page("pages/1_wallet.py")

with nav_cols[2]:
    if st.button("📡 Signaux", use_container_width=True):
        st.switch_page("pages/3_signals.py")

with nav_cols[3]:
    if st.button("🎯 Stratégies", use_container_width=True):
        st.switch_page("pages/4_strategies.py")
