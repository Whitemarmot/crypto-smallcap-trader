"""
📝 Paper Trading - Mode Simulation
Simule les décisions de trading sans risque
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
ai_path = os.path.join(os.path.dirname(__file__), '..', '..', 'ai-decision', 'python')
sys.path.insert(0, ai_path)

st.set_page_config(
    page_title="📝 Simulation | SmallCap Trader",
    page_icon="📝",
    layout="wide"
)

# Imports
try:
    from utils.social_signals import (
        get_fear_greed_index,
        get_trending_tokens,
        get_tokens_by_market_cap,
        get_google_trends,
        get_cryptopanic_sentiment
    )
    from utils.config import load_config
    from analyzer import analyze_token, TradingAction
    import requests
    MODULES_OK = True
except ImportError as e:
    MODULES_OK = False
    st.error(f"❌ Module error: {e}")
    st.stop()

# Simulation database (JSON file)
SIM_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'simulation.json')

def load_simulation_data():
    """Load simulation state from JSON"""
    if os.path.exists(SIM_DB_PATH):
        with open(SIM_DB_PATH, 'r') as f:
            return json.load(f)
    return {
        'portfolio': {'USD': 10000.0},  # Start with $10k virtual
        'positions': {},  # {symbol: {amount, avg_price, entry_date}}
        'history': [],  # Trade history
        'settings': {
            'initial_capital': 10000.0,
            'max_position_pct': 10.0,  # Max 10% per position
            'auto_trade': False
        }
    }

def save_simulation_data(data):
    """Save simulation state to JSON"""
    os.makedirs(os.path.dirname(SIM_DB_PATH), exist_ok=True)
    with open(SIM_DB_PATH, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def get_token_price(symbol: str) -> float:
    """Get current price for a token from CoinGecko"""
    try:
        # Map common symbols to CoinGecko IDs
        symbol_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
            'PEPE': 'pepe', 'DOGE': 'dogecoin', 'SHIB': 'shiba-inu',
            'XRP': 'ripple', 'ADA': 'cardano', 'AVAX': 'avalanche-2',
            'LINK': 'chainlink', 'DOT': 'polkadot', 'MATIC': 'matic-network'
        }
        cg_id = symbol_map.get(symbol.upper(), symbol.lower())
        
        resp = requests.get(
            f'https://api.coingecko.com/api/v3/simple/price',
            params={'ids': cg_id, 'vs_currencies': 'usd'},
            timeout=10
        )
        data = resp.json()
        return data.get(cg_id, {}).get('usd', 0)
    except:
        return 0

def execute_sim_trade(sim_data: dict, action: str, symbol: str, amount_usd: float, price: float) -> dict:
    """Execute a simulated trade"""
    timestamp = datetime.now().isoformat()
    
    if action == 'BUY':
        if sim_data['portfolio'].get('USD', 0) < amount_usd:
            return {'error': 'Insufficient USD balance'}
        
        # Deduct USD
        sim_data['portfolio']['USD'] -= amount_usd
        
        # Add position
        token_amount = amount_usd / price if price > 0 else 0
        if symbol in sim_data['positions']:
            # Average up/down
            existing = sim_data['positions'][symbol]
            total_amount = existing['amount'] + token_amount
            total_cost = (existing['amount'] * existing['avg_price']) + amount_usd
            sim_data['positions'][symbol] = {
                'amount': total_amount,
                'avg_price': total_cost / total_amount if total_amount > 0 else 0,
                'entry_date': existing['entry_date']
            }
        else:
            sim_data['positions'][symbol] = {
                'amount': token_amount,
                'avg_price': price,
                'entry_date': timestamp
            }
        
        sim_data['history'].append({
            'timestamp': timestamp,
            'action': 'BUY',
            'symbol': symbol,
            'amount': token_amount,
            'price': price,
            'total_usd': amount_usd
        })
        
    elif action == 'SELL':
        if symbol not in sim_data['positions']:
            return {'error': f'No {symbol} position to sell'}
        
        position = sim_data['positions'][symbol]
        sell_amount = min(position['amount'], amount_usd / price if price > 0 else 0)
        sell_value = sell_amount * price
        
        # Add USD
        sim_data['portfolio']['USD'] += sell_value
        
        # Update or remove position
        position['amount'] -= sell_amount
        if position['amount'] <= 0.0001:
            del sim_data['positions'][symbol]
        
        # Calculate PnL
        pnl = (price - position['avg_price']) * sell_amount
        pnl_pct = ((price / position['avg_price']) - 1) * 100 if position['avg_price'] > 0 else 0
        
        sim_data['history'].append({
            'timestamp': timestamp,
            'action': 'SELL',
            'symbol': symbol,
            'amount': sell_amount,
            'price': price,
            'total_usd': sell_value,
            'pnl': pnl,
            'pnl_pct': pnl_pct
        })
    
    return {'success': True}

def calculate_portfolio_value(sim_data: dict) -> dict:
    """Calculate total portfolio value"""
    usd_balance = sim_data['portfolio'].get('USD', 0)
    positions_value = 0
    position_details = []
    
    for symbol, pos in sim_data['positions'].items():
        current_price = get_token_price(symbol)
        value = pos['amount'] * current_price
        pnl = (current_price - pos['avg_price']) * pos['amount']
        pnl_pct = ((current_price / pos['avg_price']) - 1) * 100 if pos['avg_price'] > 0 else 0
        
        positions_value += value
        position_details.append({
            'symbol': symbol,
            'amount': pos['amount'],
            'avg_price': pos['avg_price'],
            'current_price': current_price,
            'value': value,
            'pnl': pnl,
            'pnl_pct': pnl_pct
        })
    
    total_value = usd_balance + positions_value
    initial = sim_data['settings']['initial_capital']
    total_pnl = total_value - initial
    total_pnl_pct = ((total_value / initial) - 1) * 100 if initial > 0 else 0
    
    return {
        'usd_balance': usd_balance,
        'positions_value': positions_value,
        'total_value': total_value,
        'total_pnl': total_pnl,
        'total_pnl_pct': total_pnl_pct,
        'positions': position_details
    }


# ==================== PAGE ====================

st.title("📝 Paper Trading")
st.caption("Mode simulation - Testez vos stratégies sans risque")

# Load simulation data
sim_data = load_simulation_data()

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Portfolio", 
    "🤖 Auto-Décisions",
    "📜 Historique",
    "⚙️ Paramètres"
])

# ============ TAB 1: Portfolio ============
with tab1:
    st.subheader("💼 Portfolio Virtuel")
    
    # Calculate values
    portfolio = calculate_portfolio_value(sim_data)
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "💰 Valeur Totale",
            f"${portfolio['total_value']:,.2f}",
            f"{portfolio['total_pnl']:+,.2f} ({portfolio['total_pnl_pct']:+.1f}%)"
        )
    
    with col2:
        st.metric("💵 USD Disponible", f"${portfolio['usd_balance']:,.2f}")
    
    with col3:
        st.metric("📈 En Positions", f"${portfolio['positions_value']:,.2f}")
    
    with col4:
        st.metric("🎯 Positions", len(sim_data['positions']))
    
    st.markdown("---")
    
    # Positions table
    if portfolio['positions']:
        st.subheader("📊 Positions Ouvertes")
        
        for pos in portfolio['positions']:
            pnl_color = "green" if pos['pnl'] >= 0 else "red"
            
            cols = st.columns([1, 1, 1, 1, 1, 2])
            cols[0].markdown(f"**{pos['symbol']}**")
            cols[1].markdown(f"{pos['amount']:.4f}")
            cols[2].markdown(f"${pos['avg_price']:.4f}")
            cols[3].markdown(f"${pos['current_price']:.4f}")
            cols[4].markdown(f"${pos['value']:.2f}")
            cols[5].markdown(f":{pnl_color}[{pos['pnl']:+.2f}$ ({pos['pnl_pct']:+.1f}%)]")
    else:
        st.info("📭 Aucune position ouverte")
    
    st.markdown("---")
    
    # Manual trade
    st.subheader("🔧 Trade Manuel")
    
    mcol1, mcol2, mcol3 = st.columns(3)
    
    with mcol1:
        manual_symbol = st.text_input("Symbol", value="ETH").upper()
    
    with mcol2:
        manual_amount = st.number_input("Montant USD", min_value=10.0, value=100.0, step=10.0)
    
    with mcol3:
        manual_action = st.selectbox("Action", ["BUY", "SELL"])
    
    if st.button(f"🚀 {manual_action} {manual_symbol}", type="primary"):
        price = get_token_price(manual_symbol)
        if price > 0:
            result = execute_sim_trade(sim_data, manual_action, manual_symbol, manual_amount, price)
            if 'error' in result:
                st.error(result['error'])
            else:
                save_simulation_data(sim_data)
                st.success(f"✅ {manual_action} {manual_symbol} @ ${price:.4f}")
                st.rerun()
        else:
            st.error(f"❌ Prix non trouvé pour {manual_symbol}")


# ============ TAB 2: Auto-Decisions ============
with tab2:
    st.subheader("🤖 Décisions Automatiques")
    st.caption("L'IA analyse les tokens et propose des trades")
    
    # Current signals
    fg = get_fear_greed_index()
    fg_value = fg.value if fg else 50
    
    if fg:
        fg_color = "#ff4444" if fg.value <= 25 else "#ff8844" if fg.value <= 45 else "#ffff44" if fg.value <= 55 else "#88ff44"
        st.markdown(f"😱 **Fear & Greed:** {fg.value} ({fg.classification})")
    
    # Analyze trending tokens
    if st.button("🔍 Analyser les tokens trending", type="primary", use_container_width=True):
        
        with st.spinner("Récupération des tokens..."):
            trending = get_trending_tokens()
        
        if not trending:
            st.warning("Impossible de charger les tokens trending")
        else:
            decisions = []
            progress = st.progress(0)
            
            for i, token in enumerate(trending[:10]):
                progress.progress((i + 1) / 10, text=f"Analyse {token.symbol}...")
                
                # Get price
                price = get_token_price(token.symbol)
                if price <= 0:
                    continue
                
                # Simple scoring based on Fear & Greed
                # In extreme fear, we want to buy. In extreme greed, we want to sell.
                score = 50
                
                if fg_value <= 25:  # Extreme fear = buy opportunity
                    score = 70 + (25 - fg_value)
                    action = "BUY"
                    reason = f"Extreme Fear ({fg_value}) = opportunité d'achat"
                elif fg_value >= 75:  # Extreme greed = sell
                    score = 30 - (fg_value - 75)
                    action = "SELL"
                    reason = f"Extreme Greed ({fg_value}) = prendre profits"
                else:
                    action = "HOLD"
                    reason = "Marché neutre"
                
                decisions.append({
                    'symbol': token.symbol,
                    'name': token.name,
                    'price': price,
                    'action': action,
                    'score': score,
                    'reason': reason
                })
            
            progress.empty()
            
            # Store decisions
            st.session_state['sim_decisions'] = decisions
    
    # Display decisions
    if 'sim_decisions' in st.session_state:
        decisions = st.session_state['sim_decisions']
        
        st.markdown("---")
        st.markdown(f"### 📋 {len(decisions)} Décisions")
        
        for d in sorted(decisions, key=lambda x: x['score'], reverse=True):
            action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(d['action'], "⚪")
            action_color = {"BUY": "green", "SELL": "red", "HOLD": "orange"}.get(d['action'], "gray")
            
            cols = st.columns([1, 2, 1, 1, 3, 1])
            cols[0].markdown(f"{action_emoji}")
            cols[1].markdown(f"**{d['symbol']}**")
            cols[2].markdown(f"${d['price']:.4f}")
            cols[3].markdown(f"{d['score']}/100")
            cols[4].caption(d['reason'])
            
            # Execute button for BUY signals
            if d['action'] == 'BUY':
                if cols[5].button("💰", key=f"buy_{d['symbol']}", help=f"Buy {d['symbol']}"):
                    amount = min(100, sim_data['portfolio'].get('USD', 0) * 0.1)  # 10% or $100 max
                    result = execute_sim_trade(sim_data, 'BUY', d['symbol'], amount, d['price'])
                    if 'error' not in result:
                        save_simulation_data(sim_data)
                        st.success(f"✅ Bought {d['symbol']}")
                        st.rerun()


# ============ TAB 3: History ============
with tab3:
    st.subheader("📜 Historique des Trades")
    
    history = sim_data.get('history', [])
    
    if history:
        # Reverse to show newest first
        for trade in reversed(history[-50:]):
            action_emoji = "🟢" if trade['action'] == 'BUY' else "🔴"
            
            cols = st.columns([1, 1, 2, 1, 1, 2])
            cols[0].markdown(trade['timestamp'][:10])
            cols[1].markdown(f"{action_emoji} {trade['action']}")
            cols[2].markdown(f"**{trade['symbol']}**")
            cols[3].markdown(f"{trade['amount']:.4f}")
            cols[4].markdown(f"${trade['price']:.4f}")
            
            if trade['action'] == 'SELL' and 'pnl' in trade:
                pnl_color = "green" if trade['pnl'] >= 0 else "red"
                cols[5].markdown(f":{pnl_color}[{trade['pnl']:+.2f}$ ({trade['pnl_pct']:+.1f}%)]")
            else:
                cols[5].markdown(f"${trade['total_usd']:.2f}")
        
        # Stats
        st.markdown("---")
        buys = [t for t in history if t['action'] == 'BUY']
        sells = [t for t in history if t['action'] == 'SELL']
        
        wins = len([s for s in sells if s.get('pnl', 0) > 0])
        losses = len([s for s in sells if s.get('pnl', 0) < 0])
        
        scol1, scol2, scol3 = st.columns(3)
        scol1.metric("Total Trades", len(history))
        scol2.metric("Wins/Losses", f"{wins}/{losses}")
        if wins + losses > 0:
            scol3.metric("Win Rate", f"{wins/(wins+losses)*100:.1f}%")
    else:
        st.info("📭 Aucun trade effectué")


# ============ TAB 4: Settings ============
with tab4:
    st.subheader("⚙️ Paramètres Simulation")
    
    new_capital = st.number_input(
        "Capital Initial ($)",
        min_value=100.0,
        value=float(sim_data['settings']['initial_capital']),
        step=1000.0
    )
    
    new_max_pos = st.slider(
        "Max % par position",
        min_value=1.0,
        max_value=50.0,
        value=float(sim_data['settings']['max_position_pct']),
        step=1.0
    )
    
    if st.button("💾 Sauvegarder"):
        sim_data['settings']['initial_capital'] = new_capital
        sim_data['settings']['max_position_pct'] = new_max_pos
        save_simulation_data(sim_data)
        st.success("✅ Paramètres sauvegardés")
    
    st.markdown("---")
    
    if st.button("🔄 Reset Simulation", type="secondary"):
        sim_data = {
            'portfolio': {'USD': new_capital},
            'positions': {},
            'history': [],
            'settings': {
                'initial_capital': new_capital,
                'max_position_pct': new_max_pos,
                'auto_trade': False
            }
        }
        save_simulation_data(sim_data)
        st.success("✅ Simulation réinitialisée")
        st.rerun()


# Navigation
st.markdown("---")
cols = st.columns(4)
with cols[0]:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/0_dashboard.py")
with cols[1]:
    if st.button("🤖 AI Analysis", use_container_width=True):
        st.switch_page("pages/6_ai_analysis.py")
with cols[2]:
    if st.button("📡 Signals", use_container_width=True):
        st.switch_page("pages/3_signals.py")
with cols[3]:
    if st.button("⚙️ Settings", use_container_width=True):
        st.switch_page("pages/5_settings.py")
