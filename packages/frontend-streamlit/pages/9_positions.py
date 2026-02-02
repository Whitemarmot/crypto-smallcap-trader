"""
📊 Positions - Suivi et graphiques d'évolution
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import requests
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SIM_PATH = os.path.join(DATA_DIR, 'simulation.json')
HISTORY_PATH = os.path.join(DATA_DIR, 'position_history.json')
CONFIG_PATH = os.path.join(DATA_DIR, 'bot_config.json')
CMC_API_KEY = '849ddcc694a049708d0b5392486d6eaa'

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def get_current_price(symbol):
    """Get current price from CMC API"""
    try:
        resp = requests.get(
            'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest',
            headers={'X-CMC_PRO_API_KEY': CMC_API_KEY},
            params={'symbol': symbol.upper(), 'convert': 'USD'},
            timeout=10
        )
        data = resp.json()
        if 'data' in data and symbol.upper() in data['data']:
            return data['data'][symbol.upper()]['quote']['USD']['price']
    except Exception as e:
        st.error(f"Erreur prix {symbol}: {e}")
    return 0

def close_position(symbol, reason="manual_close"):
    """Close a position at current market price"""
    sim = load_json(SIM_PATH, {})
    
    if symbol not in sim.get('positions', {}):
        return False, f"Position {symbol} non trouvée"
    
    pos = sim['positions'][symbol]
    qty = pos['amount']
    avg_price = pos.get('avg_price', 0)
    entry_date = pos.get('entry_date', '')
    
    # Get current price
    price = get_current_price(symbol)
    if price <= 0:
        return False, f"Impossible d'obtenir le prix pour {symbol}"
    
    # Calculate PnL
    entry_value = qty * avg_price
    exit_value = qty * price
    pnl_usd = exit_value - entry_value
    pnl_pct = ((price / avg_price) - 1) * 100 if avg_price > 0 else 0
    
    # Calculate holding duration
    holding_hours = 0
    if entry_date:
        try:
            entry_dt = datetime.fromisoformat(entry_date.replace('Z', '+00:00'))
            holding_hours = round((datetime.now() - entry_dt.replace(tzinfo=None)).total_seconds() / 3600, 1)
        except:
            pass
    
    # Add cash back
    sim['portfolio']['USDC'] = sim.get('portfolio', {}).get('USDC', 0) + exit_value
    
    # Record closed position
    if 'closed_positions' not in sim:
        sim['closed_positions'] = []
    
    closed_pos = {
        'symbol': symbol,
        'entry_date': entry_date,
        'exit_date': datetime.now().isoformat(),
        'holding_hours': holding_hours,
        'qty': qty,
        'entry_price': avg_price,
        'exit_price': price,
        'entry_value': round(entry_value, 2),
        'exit_value': round(exit_value, 2),
        'pnl_usd': round(pnl_usd, 2),
        'pnl_pct': round(pnl_pct, 2),
        'reason': reason,
    }
    sim['closed_positions'].append(closed_pos)
    
    # Remove position
    del sim['positions'][symbol]
    
    # Add to history
    if 'history' not in sim:
        sim['history'] = []
    sim['history'].append({
        'ts': datetime.now().isoformat(),
        'action': 'SELL',
        'symbol': symbol,
        'qty': qty,
        'price': price,
        'usd': exit_value,
        'pnl_usd': round(pnl_usd, 2),
        'pnl_pct': round(pnl_pct, 2),
        'auto': False,
        'reason': reason,
    })
    
    # Save
    save_json(SIM_PATH, sim)
    
    pnl_emoji = "🟢" if pnl_usd >= 0 else "🔴"
    return True, f"{pnl_emoji} {symbol} vendu @ ${price:.6f} | P&L: ${pnl_usd:+.2f} ({pnl_pct:+.2f}%)"

st.set_page_config(page_title="📊 Positions", layout="wide")
st.title("📊 Suivi des Positions")

# Load data
sim = load_json(SIM_PATH, {})
history = load_json(HISTORY_PATH, {'snapshots': {}})
config = load_json(CONFIG_PATH, {})

positions = sim.get('positions', {})
max_positions = config.get('max_positions', 10)

# Header stats
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Positions ouvertes", f"{len(positions)}/{max_positions}")
with col2:
    total_value = sum(p.get('amount', 0) * p.get('avg_price', 0) for p in positions.values())
    st.metric("Valeur totale", f"${total_value:,.2f}")
with col3:
    cash = sim.get('portfolio', {}).get('USDC', 0)
    st.metric("Cash disponible", f"${cash:,.2f}")
with col4:
    exposure = (total_value / (total_value + cash) * 100) if (total_value + cash) > 0 else 0
    st.metric("Exposure", f"{exposure:.1f}%")

st.divider()

if not positions:
    st.info("🔹 Aucune position ouverte. Le bot va en créer lors de sa prochaine exécution.")
else:
    # Config: max positions
    st.sidebar.header("⚙️ Configuration")
    new_max = st.sidebar.number_input("Max positions", min_value=1, max_value=20, value=max_positions)
    if new_max != max_positions:
        config['max_positions'] = new_max
        config['updated_at'] = datetime.now().isoformat()
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        st.sidebar.success(f"✅ Max positions: {new_max}")
        st.rerun()
    
    # Position cards
    st.subheader("📈 Positions actuelles")
    
    # Handle close confirmations
    if 'confirm_close' not in st.session_state:
        st.session_state.confirm_close = None
    
    cols = st.columns(min(len(positions), 3))
    for i, (symbol, pos) in enumerate(positions.items()):
        with cols[i % 3]:
            amount = pos.get('amount', 0)
            avg_price = pos.get('avg_price', 0)
            value = amount * avg_price
            
            # Get latest price from history
            hist = history.get('snapshots', {}).get(symbol, [])
            if hist:
                latest = hist[-1]
                current_price = latest.get('price', avg_price)
                pnl_pct = latest.get('pnl_pct', 0)
            else:
                current_price = avg_price
                pnl_pct = 0
            
            current_value = amount * current_price
            pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
            
            st.markdown(f"""
            **{symbol}** {pnl_emoji} {pnl_pct:+.2f}%
            - Quantité: `{amount:,.4f}`
            - Prix moyen: `${avg_price:.6f}`
            - Prix actuel: `${current_price:.6f}`
            - Valeur: `${current_value:,.2f}`
            """)
            
            # Show TP/SL if set
            if pos.get('stop_loss') or pos.get('tp1'):
                sl = pos.get('stop_loss', 0)
                tp1 = pos.get('tp1', 0)
                tp2 = pos.get('tp2', 0)
                st.caption(f"SL: ${sl:.6f} | TP1: ${tp1:.6f} | TP2: ${tp2:.6f}")
            
            # Close button
            if st.session_state.confirm_close == symbol:
                # Confirmation mode
                st.warning(f"⚠️ Fermer {symbol} au prix marché ?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Oui", key=f"yes_{symbol}"):
                        success, msg = close_position(symbol, reason="manual_close")
                        if success:
                            st.success(msg)
                            st.session_state.confirm_close = None
                            st.rerun()
                        else:
                            st.error(msg)
                with col_no:
                    if st.button("❌ Non", key=f"no_{symbol}"):
                        st.session_state.confirm_close = None
                        st.rerun()
            else:
                if st.button(f"🔻 Fermer", key=f"close_{symbol}"):
                    st.session_state.confirm_close = symbol
                    st.rerun()
    
    st.divider()
    
    # Charts
    st.subheader("📉 Évolution des positions")
    
    if not history.get('snapshots'):
        st.warning("⏳ Pas encore d'historique. Les données seront collectées à chaque exécution du bot.")
    else:
        # Select position to view
        selected = st.selectbox("Choisir une position", list(positions.keys()))
        
        if selected and selected in history['snapshots']:
            snapshots = history['snapshots'][selected]
            
            if len(snapshots) < 2:
                st.info(f"⏳ Seulement {len(snapshots)} point(s) de données pour {selected}. Plus de données à venir...")
            else:
                df = pd.DataFrame(snapshots)
                df['ts'] = pd.to_datetime(df['ts'])
                
                # Create dual-axis chart
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                
                # Price line
                fig.add_trace(
                    go.Scatter(x=df['ts'], y=df['price'], name="Prix", line=dict(color='#00D4FF', width=2)),
                    secondary_y=False,
                )
                
                # PnL bars
                colors = ['#00FF88' if p >= 0 else '#FF4444' for p in df['pnl_pct']]
                fig.add_trace(
                    go.Bar(x=df['ts'], y=df['pnl_pct'], name="PnL %", marker_color=colors, opacity=0.5),
                    secondary_y=True,
                )
                
                # Entry price line
                entry_price = positions[selected].get('avg_price', 0)
                fig.add_hline(y=entry_price, line_dash="dash", line_color="yellow", 
                             annotation_text=f"Entry: ${entry_price:.6f}")
                
                # TP/SL lines
                if positions[selected].get('stop_loss'):
                    fig.add_hline(y=positions[selected]['stop_loss'], line_dash="dot", line_color="red",
                                 annotation_text="Stop Loss")
                if positions[selected].get('tp1'):
                    fig.add_hline(y=positions[selected]['tp1'], line_dash="dot", line_color="green",
                                 annotation_text="TP1")
                
                fig.update_layout(
                    title=f"📊 {selected} - Évolution",
                    xaxis_title="Date",
                    template="plotly_dark",
                    height=500,
                    showlegend=True
                )
                fig.update_yaxes(title_text="Prix ($)", secondary_y=False)
                fig.update_yaxes(title_text="PnL %", secondary_y=True)
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Stats
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Min", f"${df['price'].min():.6f}")
                with col2:
                    st.metric("Max", f"${df['price'].max():.6f}")
                with col3:
                    st.metric("PnL min", f"{df['pnl_pct'].min():+.2f}%")
                with col4:
                    st.metric("PnL max", f"{df['pnl_pct'].max():+.2f}%")
        
        # All positions PnL comparison
        st.divider()
        st.subheader("📊 Comparaison PnL - Toutes positions")
        
        pnl_data = []
        for symbol in positions.keys():
            if symbol in history['snapshots'] and history['snapshots'][symbol]:
                latest = history['snapshots'][symbol][-1]
                pnl_data.append({
                    'Symbol': symbol,
                    'PnL %': latest.get('pnl_pct', 0),
                    'Valeur $': latest.get('value', 0)
                })
        
        if pnl_data:
            df_pnl = pd.DataFrame(pnl_data)
            
            fig_bar = px.bar(df_pnl, x='Symbol', y='PnL %', 
                            color='PnL %',
                            color_continuous_scale=['#FF4444', '#FFAA00', '#00FF88'],
                            title="PnL par position")
            fig_bar.update_layout(template="plotly_dark", height=400)
            st.plotly_chart(fig_bar, use_container_width=True)

# Footer
st.divider()
st.caption(f"Dernière mise à jour: {history.get('last_update', 'N/A')}")
