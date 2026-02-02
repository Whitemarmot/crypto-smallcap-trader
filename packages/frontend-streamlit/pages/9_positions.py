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

st.set_page_config(
    page_title="📊 Positions | SmallCap Trader",
    page_icon="📊",
    layout="wide"
)

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
WALLETS_DIR = os.path.join(DATA_DIR, 'wallets')
WALLETS_CONFIG = os.path.join(WALLETS_DIR, 'config.json')
SIM_PATH = os.path.join(DATA_DIR, 'simulation.json')  # Legacy fallback
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


def close_position(symbol, wallet_path, reason="manual_close"):
    """Close a position at current market price"""
    sim = load_json(wallet_path, {})
    
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
    save_json(wallet_path, sim)
    
    pnl_emoji = "🟢" if pnl_usd >= 0 else "🔴"
    return True, f"{pnl_emoji} {symbol} vendu @ ${price:.6f} | P&L: ${pnl_usd:+.2f} ({pnl_pct:+.2f}%)"


# ========== TITRE ==========
st.title("📊 Suivi des Positions")

# ========== CHARGEMENT DONNÉES ==========
wallets_config = load_json(WALLETS_CONFIG, {'wallets': [], 'active_wallet': 'simulation'})
wallets = {w['id']: w for w in wallets_config.get('wallets', [])}
wallet_list = wallets_config.get('wallets', [])
active_wallet_id = wallets_config.get('active_wallet', 'simulation')

# ========== SIDEBAR FILTRES ==========
st.sidebar.header("🔍 Filtres")

# Filtre par wallet
st.sidebar.subheader("💼 Wallet")
if wallet_list:
    wallet_options = {w['id']: f"{w['name']} ({'🎮 Sim' if w.get('type', 'paper') in ['paper', 'simulation'] else '💳 Réel'})" for w in wallet_list}
    wallet_ids = list(wallet_options.keys())
    
    # Find index of active wallet
    try:
        default_idx = wallet_ids.index(active_wallet_id)
    except ValueError:
        default_idx = 0
    
    selected_wallet_id = st.sidebar.selectbox(
        "Wallet actif",
        options=wallet_ids,
        format_func=lambda x: wallet_options.get(x, x),
        index=default_idx
    )
else:
    selected_wallet_id = 'simulation'
    st.sidebar.info("Aucun wallet configuré")

# Filtre par statut P&L
st.sidebar.subheader("💰 Filtre P&L")
pnl_filter = st.sidebar.radio(
    "Afficher",
    options=["Toutes", "🟢 Positives", "🔴 Négatives"],
    index=0,
    horizontal=True
)

# ========== CONFIG WALLET (SIDEBAR) ==========
st.sidebar.divider()
st.sidebar.header("⚙️ Config Wallet")

# Load wallet data
wallet_path = os.path.join(WALLETS_DIR, f'{selected_wallet_id}.json')
sim = None

if os.path.exists(wallet_path):
    sim = load_json(wallet_path, None)

if not sim and os.path.exists(SIM_PATH):
    sim = load_json(SIM_PATH, None)

if not sim:
    sim = {'portfolio': {'USDC': 0}, 'positions': {}, 'history': []}

history = load_json(HISTORY_PATH, {'snapshots': {}})

# Get wallet-specific config
wallet_cfg = wallets.get(selected_wallet_id, {})
max_positions = wallet_cfg.get('max_positions', 10)
position_size_pct = wallet_cfg.get('position_size_pct', 5)
stop_loss_pct = wallet_cfg.get('stop_loss_pct', 15)
take_profit_pct = wallet_cfg.get('take_profit_pct', 20)

new_max = st.sidebar.number_input("Max positions", min_value=1, max_value=20, value=max_positions, key="max_pos")
new_size = st.sidebar.number_input("Taille position (%)", min_value=1, max_value=25, value=position_size_pct, key="pos_size")
new_sl = st.sidebar.number_input("Stop Loss (%)", min_value=5, max_value=50, value=stop_loss_pct, key="sl")
new_tp = st.sidebar.number_input("Take Profit (%)", min_value=5, max_value=100, value=take_profit_pct, key="tp")

config_changed = (new_max != max_positions or new_size != position_size_pct or 
                  new_sl != stop_loss_pct or new_tp != take_profit_pct)

if config_changed:
    if st.sidebar.button("💾 Sauvegarder Config"):
        for w in wallets_config['wallets']:
            if w['id'] == selected_wallet_id:
                w['max_positions'] = new_max
                w['position_size_pct'] = new_size
                w['stop_loss_pct'] = new_sl
                w['take_profit_pct'] = new_tp
                w['updated_at'] = datetime.now().isoformat()
                break
        save_json(WALLETS_CONFIG, wallets_config)
        st.sidebar.success("✅ Config sauvegardée!")
        st.rerun()

positions = sim.get('positions', {})

# Filtrer les positions selon le P&L
def filter_positions(positions_dict, history_data):
    """Filtre les positions selon le filtre P&L"""
    if pnl_filter == "Toutes":
        return positions_dict
    
    filtered = {}
    for symbol, pos in positions_dict.items():
        hist = history_data.get('snapshots', {}).get(symbol, [])
        if hist:
            pnl_pct = hist[-1].get('pnl_pct', 0)
        else:
            pnl_pct = 0
        
        if pnl_filter == "🟢 Positives" and pnl_pct >= 0:
            filtered[symbol] = pos
        elif pnl_filter == "🔴 Négatives" and pnl_pct < 0:
            filtered[symbol] = pos
    
    return filtered

filtered_positions = filter_positions(positions, history)

# ========== STATS RÉSUMÉES ==========
st.subheader("📊 Statistiques")

# Calcul des stats
total_value = sum(p.get('amount', 0) * p.get('avg_price', 0) for p in positions.values())
cash = sim.get('portfolio', {}).get('USDC', 0)
exposure = (total_value / (total_value + cash) * 100) if (total_value + cash) > 0 else 0

# Calcul du P&L total actuel
total_current_value = 0
total_entry_value = 0
for symbol, pos in positions.items():
    amount = pos.get('amount', 0)
    avg_price = pos.get('avg_price', 0)
    hist = history.get('snapshots', {}).get(symbol, [])
    if hist:
        current_price = hist[-1].get('price', avg_price)
    else:
        current_price = avg_price
    total_current_value += amount * current_price
    total_entry_value += amount * avg_price

total_unrealized_pnl = total_current_value - total_entry_value
total_pnl_pct = ((total_current_value / total_entry_value) - 1) * 100 if total_entry_value > 0 else 0

# Meilleure et pire position
positions_pnl = []
for symbol, pos in positions.items():
    hist = history.get('snapshots', {}).get(symbol, [])
    if hist:
        pnl_pct = hist[-1].get('pnl_pct', 0)
        positions_pnl.append((symbol, pnl_pct))

best_pos = max(positions_pnl, key=lambda x: x[1]) if positions_pnl else None
worst_pos = min(positions_pnl, key=lambda x: x[1]) if positions_pnl else None

# Affichage stats
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("📈 Positions Ouvertes", f"{len(positions)}/{max_positions}")
    
with col2:
    st.metric("💵 Valeur Totale", f"${total_current_value:,.2f}")

with col3:
    st.metric("💰 Cash Disponible", f"${cash:,.2f}")

with col4:
    st.metric("📊 Exposition", f"{exposure:.1f}%")

with col5:
    delta_color = "normal" if total_unrealized_pnl >= 0 else "inverse"
    st.metric("💰 P&L Non Réalisé", f"${total_unrealized_pnl:+,.2f}", delta=f"{total_pnl_pct:+.1f}%", delta_color=delta_color)

# Best/Worst positions
if best_pos or worst_pos:
    col_best, col_worst = st.columns(2)
    
    with col_best:
        if best_pos and best_pos[1] > 0:
            st.success(f"🏆 **Meilleure position:** {best_pos[0]} → **{best_pos[1]:+.1f}%**")
        elif best_pos:
            st.info(f"🏆 Meilleure position: {best_pos[0]} → {best_pos[1]:+.1f}%")
    
    with col_worst:
        if worst_pos and worst_pos[1] < 0:
            st.error(f"💀 **Pire position:** {worst_pos[0]} → **{worst_pos[1]:+.1f}%**")
        elif worst_pos:
            st.info(f"💀 Pire position: {worst_pos[0]} → {worst_pos[1]:+.1f}%")

st.divider()

# ========== POSITIONS ==========
if not filtered_positions:
    if not positions:
        st.info("🔹 Aucune position ouverte. Le bot va en créer lors de sa prochaine exécution.")
    else:
        st.info("🔍 Aucune position ne correspond aux filtres sélectionnés.")
else:
    st.subheader(f"📈 Positions actuelles ({len(filtered_positions)})")
    
    # Handle close confirmations
    if 'confirm_close' not in st.session_state:
        st.session_state.confirm_close = None
    
    # Préparer données pour le tableau
    positions_data = []
    for symbol, pos in filtered_positions.items():
        amount = pos.get('amount', 0)
        avg_price = pos.get('avg_price', 0)
        entry_value = amount * avg_price
        
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
        pnl_usd = current_value - entry_value
        
        # Format entry date
        entry_date = pos.get('entry_date', '')
        entry_str = ""
        holding_str = ""
        if entry_date:
            try:
                entry_dt = datetime.fromisoformat(entry_date.replace('Z', '+00:00'))
                entry_str = entry_dt.strftime('%d/%m %H:%M')
                holding_hours = (datetime.now() - entry_dt.replace(tzinfo=None)).total_seconds() / 3600
                if holding_hours < 1:
                    holding_str = f"{int(holding_hours * 60)}min"
                elif holding_hours < 24:
                    holding_str = f"{holding_hours:.1f}h"
                else:
                    holding_str = f"{holding_hours / 24:.1f}j"
            except:
                entry_str = entry_date[:16]
        
        positions_data.append({
            "symbol": symbol,
            "🪙 Token": symbol,
            "📅 Entrée": entry_str,
            "⏱️ Durée": holding_str,
            "📦 Quantité": f"{amount:,.4f}",
            "💵 Prix Entrée": f"${avg_price:.6f}",
            "💵 Prix Actuel": f"${current_price:.6f}",
            "💰 Valeur": f"${current_value:,.2f}",
            "📈 P&L ($)": f"${pnl_usd:+.2f}",
            "📊 P&L (%)": f"{pnl_pct:+.1f}%",
            "pnl_pct_raw": pnl_pct,  # Pour le tri
        })
    
    # Créer le DataFrame
    df_positions = pd.DataFrame(positions_data)
    
    # Coloriser le P&L
    def color_pnl_cell(val):
        if isinstance(val, str):
            try:
                num_str = val.replace('$', '').replace('%', '').replace(',', '').replace('+', '')
                num = float(num_str)
                if num > 0:
                    return "color: #00FF88; font-weight: bold"
                elif num < 0:
                    return "color: #FF4444; font-weight: bold"
            except:
                pass
        return ""
    
    # Afficher les colonnes visibles seulement
    display_cols = ["🪙 Token", "📅 Entrée", "⏱️ Durée", "📦 Quantité", "💵 Prix Entrée", "💵 Prix Actuel", "💰 Valeur", "📈 P&L ($)", "📊 P&L (%)"]
    
    st.dataframe(
        df_positions[display_cols].style.applymap(color_pnl_cell, subset=["📈 P&L ($)", "📊 P&L (%)"]),
        use_container_width=True,
        hide_index=True,
        height=min(400, 50 + len(positions_data) * 35)
    )
    
    # ========== ACTIONS SUR POSITIONS ==========
    st.subheader("🎮 Actions")
    
    # Sélection de position pour fermeture
    position_symbols = list(filtered_positions.keys())
    
    col_select, col_action = st.columns([2, 1])
    
    with col_select:
        selected_to_close = st.selectbox(
            "Sélectionner une position à fermer",
            options=["-- Choisir --"] + position_symbols,
            key="select_close"
        )
    
    with col_action:
        if selected_to_close and selected_to_close != "-- Choisir --":
            if st.session_state.confirm_close == selected_to_close:
                st.warning(f"⚠️ Confirmer fermeture de {selected_to_close} ?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Oui", key="yes_close"):
                        success, msg = close_position(selected_to_close, wallet_path, reason="manual_close")
                        if success:
                            st.success(msg)
                            st.session_state.confirm_close = None
                            st.rerun()
                        else:
                            st.error(msg)
                with col_no:
                    if st.button("❌ Non", key="no_close"):
                        st.session_state.confirm_close = None
                        st.rerun()
            else:
                if st.button(f"🔻 Fermer {selected_to_close}", key="btn_close"):
                    st.session_state.confirm_close = selected_to_close
                    st.rerun()
    
    st.divider()
    
    # ========== GRAPHIQUES ==========
    st.subheader("📉 Évolution des positions")
    
    if not history.get('snapshots'):
        st.warning("⏳ Pas encore d'historique. Les données seront collectées à chaque exécution du bot.")
    else:
        # Select position to view
        selected = st.selectbox("Choisir une position", position_symbols, key="chart_select")
        
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
                
                # Stats du graphique
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📉 Prix Min", f"${df['price'].min():.6f}")
                with col2:
                    st.metric("📈 Prix Max", f"${df['price'].max():.6f}")
                with col3:
                    min_pnl = df['pnl_pct'].min()
                    st.metric("💀 P&L Min", f"{min_pnl:+.2f}%")
                with col4:
                    max_pnl = df['pnl_pct'].max()
                    st.metric("🏆 P&L Max", f"{max_pnl:+.2f}%")
        
        # All positions PnL comparison
        if len(positions) > 1:
            st.divider()
            st.subheader("📊 Comparaison P&L - Toutes positions")
            
            pnl_data = []
            for symbol in positions.keys():
                if symbol in history['snapshots'] and history['snapshots'][symbol]:
                    latest = history['snapshots'][symbol][-1]
                    pnl_data.append({
                        'Token': symbol,
                        'P&L %': latest.get('pnl_pct', 0),
                        'Valeur $': latest.get('value', 0)
                    })
            
            if pnl_data:
                df_pnl = pd.DataFrame(pnl_data)
                df_pnl = df_pnl.sort_values('P&L %', ascending=True)
                
                # Couleurs basées sur le P&L
                colors = ['#00FF88' if p >= 0 else '#FF4444' for p in df_pnl['P&L %']]
                
                fig_bar = go.Figure(data=[
                    go.Bar(
                        x=df_pnl['Token'],
                        y=df_pnl['P&L %'],
                        marker_color=colors,
                        text=[f"{p:+.1f}%" for p in df_pnl['P&L %']],
                        textposition='outside'
                    )
                ])
                
                fig_bar.update_layout(
                    title="P&L par position",
                    template="plotly_dark",
                    height=400,
                    xaxis_title="Token",
                    yaxis_title="P&L %"
                )
                
                st.plotly_chart(fig_bar, use_container_width=True)

# ========== NAVIGATION ==========
st.markdown("---")
cols = st.columns(4)
if cols[0].button("🏠 Home", use_container_width=True):
    st.switch_page("app.py")
if cols[1].button("👛 Wallets", use_container_width=True):
    st.switch_page("pages/1_wallet.py")
if cols[2].button("📈 Trades", use_container_width=True):
    st.switch_page("pages/2_trades.py")
if cols[3].button("🤖 Logs IA", use_container_width=True):
    st.switch_page("pages/9_logs_ia.py")

# Footer
st.divider()
st.caption(f"📅 Dernière mise à jour: {history.get('last_update', 'N/A')}")
