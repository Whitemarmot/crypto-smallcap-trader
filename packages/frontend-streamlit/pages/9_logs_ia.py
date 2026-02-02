"""
📜 Logs IA - Historique des prompts et réponses LLM + Bot Trading
"""

import streamlit as st
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TZ_PARIS = ZoneInfo('Europe/Paris')

st.set_page_config(
    page_title="📜 Logs IA | SmallCap Trader",
    page_icon="📜",
    layout="wide"
)

# ========== BOT TRADING LOGS ==========
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
BOT_STATUS_FILE = os.path.join(DATA_DIR, 'bot_status.json')
BOT_LOG_FILE = os.path.join(DATA_DIR, 'bot_run.log')

def get_bot_status():
    try:
        if os.path.exists(BOT_STATUS_FILE):
            with open(BOT_STATUS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return None

st.title("📜 Logs IA & Bot")

# Bot status section
st.subheader("🤖 Bot Trading - Dernier Run")
bot_status = get_bot_status()

if bot_status:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("⏰ Dernier Run", bot_status.get('last_run', 'N/A'))
    with col2:
        st.metric("📊 Tokens analysés", bot_status.get('tokens_analyzed', 0))
    with col3:
        st.metric("🎯 Trades exécutés", bot_status.get('trades_executed', 0))
    
    # Summary
    if bot_status.get('summary'):
        with st.expander("📋 Résumé complet", expanded=True):
            st.markdown(bot_status.get('summary', ''))
else:
    st.info("⏳ Aucun run enregistré. Lance une analyse via le Dashboard!")

st.markdown("---")

try:
    from utils.llm_providers import get_llm_logs, get_available_providers, LLM_MODELS
    MODULES_OK = True
except ImportError as e:
    MODULES_OK = False
    st.error(f"Module error: {e}")

# LLM Logs section
st.subheader("🧠 Logs LLM (OpenRouter/Claude)")
st.caption("Historique des prompts et réponses des modèles IA")

if MODULES_OK:
    # Show available providers
    available = get_available_providers()
    
    st.subheader("🔌 Providers configurés")
    
    if available:
        cols = st.columns(len(available))
        for i, (key, provider) in enumerate(available.items()):
            with cols[i]:
                st.markdown(f"""
                <div style="background: #1e1e2e; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #444;">
                    <div style="font-size: 2rem;">{provider['icon']}</div>
                    <div style="color: #ffffff; font-weight: bold; font-size: 1.1rem;">{provider['name']}</div>
                    <div style="color: #00ff88;">✅ Connecté</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.warning("⚠️ Aucun provider configuré. Ajoute des clés API dans `.env`")
        st.code("""
# Ajoute dans .env:
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
XAI_API_KEY=xai-...
OPENAI_API_KEY=sk-...
        """)
    
    # Show unconfigured providers
    unconfigured = set(LLM_MODELS.keys()) - set(available.keys())
    if unconfigured:
        with st.expander("➕ Providers non configurés"):
            for key in unconfigured:
                provider = LLM_MODELS[key]
                st.markdown(f"{provider['icon']} **{provider['name']}** - Ajoute `{provider['api_key_env']}` dans `.env`")
    
    st.markdown("---")
    
    # Logs section
    st.subheader("📋 Historique des appels")
    
    # Filters
    col1, col2 = st.columns([1, 3])
    with col1:
        limit = st.selectbox("Nombre de logs", [10, 25, 50, 100], index=1)
    
    logs = get_llm_logs(limit)
    
    if logs:
        st.success(f"📊 {len(logs)} appels enregistrés")
        
        for i, log in enumerate(logs):
            # Format timestamp
            try:
                ts = datetime.fromisoformat(log['timestamp']).strftime('%d/%m %H:%M:%S')
            except:
                ts = log['timestamp'][:19]
            
            # Provider info
            provider_info = LLM_MODELS.get(log['provider'], {})
            icon = provider_info.get('icon', '🤖')
            
            # Status
            status = "✅" if not log.get('error') else "❌"
            
            with st.expander(f"{status} {icon} {log['model']} | {ts} | {log['latency_ms']}ms"):
                # Metrics
                mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                mcol1.metric("Provider", log['provider'])
                mcol2.metric("Tokens In", log['tokens_in'])
                mcol3.metric("Tokens Out", log['tokens_out'])
                mcol4.metric("Latence", f"{log['latency_ms']}ms")
                
                # Error if any
                if log.get('error'):
                    st.error(f"❌ Erreur: {log['error']}")
                
                # Prompt
                st.markdown("**📝 Prompt:**")
                st.code(log['prompt'], language=None)
                
                # Response
                st.markdown("**💬 Réponse:**")
                st.code(log['response'], language=None)
    else:
        st.info("📭 Aucun log pour le moment. Lance une analyse IA pour voir les logs!")

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
    if st.button("📝 Simulation", use_container_width=True):
        st.switch_page("pages/8_simulation.py")
with cols[3]:
    if st.button("⚙️ Settings", use_container_width=True):
        st.switch_page("pages/5_settings.py")
