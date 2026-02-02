#!/usr/bin/env python3
"""
🔬 Full Analysis for Jean-Michel Trading Bot
Combines all analysis tools for comprehensive trading decisions.
"""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from analysis_tools import (
    get_technical_indicators,
    analyze_sentiment_text,
    get_crypto_news_rss,
    get_exchange_data
)
from utils.social_signals import get_fear_greed_index, get_tokens_by_market_cap_cmc

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SIM_PATH = os.path.join(DATA_DIR, 'simulation.json')
CONFIG_PATH = os.path.join(DATA_DIR, 'bot_config.json')

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default

def analyze_token(symbol: str, name: str = None) -> dict:
    """Full analysis of a single token"""
    result = {
        'symbol': symbol,
        'name': name,
        'timestamp': datetime.now().isoformat(),
    }
    
    # Technical Analysis
    print(f"  📊 Technical analysis for {symbol}...", file=sys.stderr)
    result['technical'] = get_technical_indicators(symbol)
    time.sleep(0.5)
    
    # Exchange Data
    print(f"  📈 Exchange data for {symbol}...", file=sys.stderr)
    result['exchange'] = get_exchange_data(symbol)
    time.sleep(0.3)
    
    # Score calculation
    score = 50  # Base score
    reasons = []
    
    tech = result.get('technical', {})
    if tech.get('rsi_signal') == 'OVERSOLD':
        score += 15
        reasons.append(f"RSI oversold ({tech.get('rsi', 0):.0f})")
    elif tech.get('rsi_signal') == 'OVERBOUGHT':
        score -= 15
        reasons.append(f"RSI overbought ({tech.get('rsi', 0):.0f})")
    
    if tech.get('macd_cross') == 'CROSS_UP':
        score += 20
        reasons.append("MACD bullish crossover")
    elif tech.get('macd_cross') == 'CROSS_DOWN':
        score -= 20
        reasons.append("MACD bearish crossover")
    
    if tech.get('trend') == 'BULLISH':
        score += 10
        reasons.append("Bullish trend (SMA20>SMA50)")
    elif tech.get('trend') == 'BEARISH':
        score -= 5
        reasons.append("Bearish trend")
    
    exch = result.get('exchange', {})
    if exch.get('buy_pressure', 50) > 60:
        score += 10
        reasons.append(f"Strong buy pressure ({exch['buy_pressure']:.0f}%)")
    elif exch.get('buy_pressure', 50) < 40:
        score -= 10
        reasons.append(f"Weak buy pressure ({exch.get('buy_pressure', 0):.0f}%)")
    
    result['score'] = min(100, max(0, score))
    result['reasons'] = reasons
    result['recommendation'] = 'BUY' if score >= 65 else 'HOLD' if score >= 40 else 'AVOID'
    
    return result

def main():
    print("🔬 Starting Full Analysis...", file=sys.stderr)
    
    # Load config
    config = load_json(CONFIG_PATH, {})
    sim = load_json(SIM_PATH, {'portfolio': {'USDC': 10000}, 'positions': {}})
    
    # Market Overview
    print("📡 Getting market overview...", file=sys.stderr)
    fg = get_fear_greed_index()
    news = get_crypto_news_rss(limit=5)
    
    # Analyze news sentiment
    news_sentiment = []
    for article in news[:5]:
        sent = analyze_sentiment_text(article.get('title', ''))
        news_sentiment.append(sent.get('compound', 0))
    avg_news_sentiment = sum(news_sentiment) / len(news_sentiment) if news_sentiment else 0
    
    # Get tokens based on config
    mcap = config.get('mcap', 'small')
    mcap_ranges = {
        'micro': (0, 1_000_000),
        'small': (1_000_000, 100_000_000),
        'mid': (100_000_000, 1_000_000_000),
        'large': (1_000_000_000, float('inf')),
    }
    min_mcap, max_mcap = mcap_ranges.get(mcap, (1_000_000, 100_000_000))
    
    print(f"📊 Fetching tokens (mcap: {mcap})...", file=sys.stderr)
    tokens = get_tokens_by_market_cap_cmc(min_mcap, max_mcap, limit=100)
    sorted_tokens = sorted(tokens, key=lambda x: x.get('price_change_24h', 0) or 0, reverse=True)
    
    # Portfolio info
    cash = sim.get('portfolio', {}).get('USDC', 0)
    positions = sim.get('positions', {})
    
    # Analyze top candidates
    print("🔍 Analyzing top 5 candidates...", file=sys.stderr)
    candidates = []
    for t in sorted_tokens[:5]:
        symbol = t.get('symbol', '')
        name = t.get('name', '')
        
        analysis = analyze_token(symbol, name)
        analysis['cmc_data'] = {
            'price': t.get('price'),
            'change_24h': t.get('price_change_24h'),
            'mcap': t.get('market_cap'),
        }
        candidates.append(analysis)
    
    # Analyze current positions
    print("📋 Analyzing open positions...", file=sys.stderr)
    position_analysis = []
    for symbol, pos in positions.items():
        entry_date = pos.get('entry_date', '')
        entry_formatted = ''
        holding_hours = 0
        if entry_date:
            try:
                entry_dt = datetime.fromisoformat(entry_date.replace('Z', '+00:00'))
                entry_formatted = entry_dt.strftime('%d/%m %H:%M')
                holding_hours = round((datetime.now() - entry_dt.replace(tzinfo=None)).total_seconds() / 3600, 1)
            except:
                entry_formatted = entry_date[:16] if len(entry_date) > 16 else entry_date
        
        analysis = {
            'symbol': symbol,
            'amount': pos.get('amount', 0),
            'avg_price': pos.get('avg_price', 0),
            'entry_date': entry_date,
            'entry_formatted': entry_formatted,
            'holding_hours': holding_hours,
            'stop_loss': pos.get('stop_loss'),
            'tp1': pos.get('tp1'),
            'tp2': pos.get('tp2'),
        }
        
        # Get current price
        tech = get_technical_indicators(symbol)
        if tech.get('price'):
            current_price = tech['price']
            analysis['current_price'] = current_price
            analysis['pnl_pct'] = round((current_price / pos['avg_price'] - 1) * 100, 2) if pos.get('avg_price') else 0
            analysis['technical'] = tech
            
            # Check stop loss / take profit
            if pos.get('stop_loss') and current_price <= pos['stop_loss']:
                analysis['alert'] = 'STOP_LOSS_HIT'
            elif pos.get('tp1') and current_price >= pos['tp1']:
                analysis['alert'] = 'TP1_HIT'
            elif pos.get('tp2') and current_price >= pos['tp2']:
                analysis['alert'] = 'TP2_HIT'
        
        position_analysis.append(analysis)
        time.sleep(0.3)
    
    # Output
    output = {
        'timestamp': datetime.now().isoformat(),
        'market': {
            'fear_greed': fg.value if fg else 50,
            'fear_greed_class': fg.classification if fg else 'Neutral',
            'news_sentiment': round(avg_news_sentiment, 3),
            'news_sentiment_label': 'POSITIVE' if avg_news_sentiment > 0.1 else 'NEGATIVE' if avg_news_sentiment < -0.1 else 'NEUTRAL',
        },
        'news': news[:5],
        'config': {
            'mcap': mcap,
            'max_positions': config.get('max_positions', 10),
            'profile': config.get('profile', 'moderate'),
        },
        'portfolio': {
            'cash': round(cash, 2),
            'positions_count': len(positions),
            'max_positions': config.get('max_positions', 10),
            'slots_available': config.get('max_positions', 10) - len(positions),
        },
        'positions': position_analysis,
        'candidates': candidates,
    }
    
    print(json.dumps(output, indent=2, default=str))

if __name__ == '__main__':
    main()
