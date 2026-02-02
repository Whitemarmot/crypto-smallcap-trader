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
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SIM_PATH = os.path.join(DATA_DIR, 'simulation.json')
HISTORY_PATH = os.path.join(DATA_DIR, 'position_history.json')
CONFIG_PATH = os.path.join(DATA_DIR, 'bot_config.json')

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default

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
