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
from utils.dex_pairs import filter_tradable_tokens, get_best_pair

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
WALLETS_DIR = os.path.join(DATA_DIR, 'wallets')
WALLETS_CONFIG = os.path.join(WALLETS_DIR, 'config.json')
CONFIG_PATH = os.path.join(DATA_DIR, 'bot_config.json')

# Legacy path for backwards compatibility
SIM_PATH = os.path.join(DATA_DIR, 'simulation.json')

# API key
CMC_API_KEY = os.environ.get('CMC_API_KEY', '849ddcc694a049708d0b5392486d6eaa')

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default

def analyze_token(symbol: str, name: str = None, dex_momentum: float = None) -> dict:
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
    
    # Use DexScreener momentum (passed from caller or from tech data)
    dex_change = dex_momentum if dex_momentum is not None else tech.get('change_24h', 0)
    if dex_change:
        if dex_change >= 10:
            score += 25
            reasons.append(f"Strong momentum (+{dex_change:.1f}%)")
        elif dex_change >= 5:
            score += 15
            reasons.append(f"Good momentum (+{dex_change:.1f}%)")
        elif dex_change >= 2:
            score += 10
            reasons.append(f"Positive momentum (+{dex_change:.1f}%)")
        elif dex_change >= 0:
            score += 5
            reasons.append(f"Slight momentum (+{dex_change:.1f}%)")
        elif dex_change >= -5:
            reasons.append(f"Slight dip ({dex_change:.1f}%)")
        else:
            score -= 10
            reasons.append(f"Significant drop ({dex_change:.1f}%)")
    
    # Traditional technical indicators (if available)
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

def load_wallets():
    """Load all enabled wallets"""
    wallets = []
    
    # Load wallets config
    wallets_config = load_json(WALLETS_CONFIG, {'wallets': []})
    
    for w in wallets_config.get('wallets', []):
        if not w.get('enabled', True):
            continue
        
        wallet_id = w.get('id', 'unknown')
        wallet_path = os.path.join(WALLETS_DIR, f"{wallet_id}.json")
        
        # Fallback to legacy path
        if not os.path.exists(wallet_path) and wallet_id == 'simulation':
            wallet_path = SIM_PATH
        
        wallet_data = load_json(wallet_path, {'portfolio': {'USDC': 10000}, 'positions': {}})
        
        wallets.append({
            'id': wallet_id,
            'name': w.get('name', wallet_id),
            'type': w.get('type', 'paper'),
            'chain': w.get('chain', 'base'),
            'address': w.get('address'),  # For real wallets
            'max_positions': w.get('max_positions', 10),
            'data': wallet_data,
            'path': wallet_path,
        })
    
    # Fallback: if no wallets configured, use legacy simulation
    if not wallets:
        wallets.append({
            'id': 'simulation',
            'name': '🎮 Simulation',
            'type': 'paper',
            'max_positions': 10,
            'data': load_json(SIM_PATH, {'portfolio': {'USDC': 10000}, 'positions': {}}),
            'path': SIM_PATH,
        })
    
    return wallets


def analyze_wallet_positions(wallet, tokens):
    """Analyze positions for a single wallet"""
    positions = wallet['data'].get('positions', {})
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
    
    return position_analysis


def main():
    print("🔬 Starting Full Analysis...", file=sys.stderr)
    
    # Load config
    config = load_json(CONFIG_PATH, {})
    
    # Load all wallets
    wallets = load_wallets()
    print(f"💼 Found {len(wallets)} wallet(s)", file=sys.stderr)
    
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
    
    # Get the main chain from wallets (use first enabled wallet's chain)
    main_chain = 'base'
    for w in wallets:
        if w.get('chain'):
            main_chain = w['chain']
            break
    
    # Get tokens based on wallet's mcap preference (supports single or multiple ranges)
    mcap_config = config.get('mcap', 'small')
    mcap_ranges = {
        'micro': (0, 1_000_000),
        'small': (1_000_000, 100_000_000),
        'mid': (100_000_000, 1_000_000_000),
        'large': (1_000_000_000, float('inf')),
    }
    
    # Support multiple ranges: "small", ["small", "mid"], or "small,mid"
    if isinstance(mcap_config, list):
        selected_ranges = mcap_config
    elif ',' in str(mcap_config):
        selected_ranges = [r.strip() for r in mcap_config.split(',')]
    else:
        selected_ranges = [mcap_config]
    
    # Calculate combined min/max from selected ranges
    min_mcap = float('inf')
    max_mcap = 0
    for r in selected_ranges:
        if r in mcap_ranges:
            r_min, r_max = mcap_ranges[r]
            min_mcap = min(min_mcap, r_min)
            max_mcap = max(max_mcap, r_max if r_max != float('inf') else 10_000_000_000)
    
    # Fallback if no valid range
    if min_mcap == float('inf'):
        min_mcap, max_mcap = 1_000_000, 100_000_000
    
    mcap = '+'.join(selected_ranges)  # e.g. "small+mid"
    print(f"📊 MCap filter: {selected_ranges} (${min_mcap/1e6:.0f}M - ${max_mcap/1e6:.0f}M)", file=sys.stderr)
    
    # NEW: Get tokens DIRECTLY from chain DEXes (not CMC)
    print(f"🔗 Fetching tokens directly from {main_chain} DEXes...", file=sys.stderr)
    try:
        from utils.chain_tokens import get_top_gainers_on_chain
        # Use appropriate liquidity based on mcap tier
        min_liq = 100000 if max_mcap > 100_000_000 else 30000
        chain_tokens = get_top_gainers_on_chain(
            chain=main_chain,
            min_liquidity=min_liq,
            min_change=-5.0,  # Include slightly negative too
            limit=50,
            max_mcap=max_mcap  # Pass mcap filter from wallet config
        )
        print(f"✅ Found {len(chain_tokens)} tokens on {main_chain}", file=sys.stderr)
        
        # Convert to standard format
        tradable_tokens = []
        for t in chain_tokens:
            # Skip stablecoins and wrapped tokens
            symbol = t.get('symbol', '').upper()
            if symbol in ['USDC', 'USDT', 'DAI', 'WETH', 'CBETH']:
                continue
            # Skip if MCap out of range
            mcap_val = t.get('market_cap', 0)
            if mcap_val < min_mcap or mcap_val > max_mcap:
                continue
            
            tradable_tokens.append({
                'symbol': symbol,
                'name': t.get('name', ''),
                'price': t.get('price', 0),
                'price_change_24h': t.get('price_change_24h', 0),
                'market_cap': mcap_val,
                'pair': {
                    'baseToken': {'address': t.get('address'), 'symbol': symbol},
                    'pairAddress': t.get('pair_address'),
                    'liquidity': {'usd': t.get('liquidity', 0)},
                },
                'dex': t.get('dex'),
                'chain': main_chain,
            })
        
        # No pre-filtering - let execution try multiple DEXes (Paraswap, Aerodrome, KyberSwap)
        # Tokens with DexScreener liquidity are likely tradable on at least one DEX
        print(f"  ✅ {len(tradable_tokens)} tokens with liquidity on Base DEXes", file=sys.stderr)
        
        for t in tradable_tokens[:10]:
            print(f"  📈 {t['symbol']}: {t['price_change_24h']:+.1f}% | ${t['market_cap']/1e6:.1f}M mcap | {t['dex']}", file=sys.stderr)
            
    except Exception as e:
        print(f"⚠️ Chain token fetch failed: {e}, falling back to CMC", file=sys.stderr)
        # Fallback to CMC method
        tokens = get_tokens_by_market_cap_cmc(min_mcap, max_mcap, limit=100)
        sorted_tokens = sorted(tokens, key=lambda x: x.get('price_change_24h', 0) or 0, reverse=True)
        tradable_tokens = filter_tradable_tokens(sorted_tokens[:30], main_chain, max_tokens=15)
    
    print(f"✅ {len(tradable_tokens)} tradable tokens ready for analysis", file=sys.stderr)
    
    # Analyze top candidates (only tradable ones)
    print("🔍 Analyzing top 5 tradable candidates...", file=sys.stderr)
    candidates = []
    for t in tradable_tokens[:5]:
        symbol = t.get('symbol', '')
        name = t.get('name', '')
        momentum = t.get('price_change_24h', 0)
        
        analysis = analyze_token(symbol, name, dex_momentum=momentum)
        analysis['cmc_data'] = {
            'price': t.get('price'),
            'change_24h': t.get('price_change_24h'),
            'mcap': t.get('market_cap'),
        }
        # Add DEX pair info
        if t.get('pair'):
            analysis['dex_pair'] = t['pair']
        candidates.append(analysis)
    
    # Analyze each wallet
    print("📋 Analyzing wallets...", file=sys.stderr)
    wallets_analysis = []
    total_positions = 0
    total_slots = 0
    
    for wallet in wallets:
        print(f"  💼 {wallet['name']}...", file=sys.stderr)
        
        wallet_data = wallet['data']
        positions = wallet_data.get('positions', {})
        max_pos = wallet.get('max_positions', 10)
        
        # Get cash based on wallet type
        if wallet.get('type') == 'real' and wallet.get('address'):
            # Real wallet: get on-chain balance
            try:
                from web3 import Web3
                import requests as req
                
                chain = wallet.get('chain', 'base')
                rpc_urls = {'base': 'https://mainnet.base.org', 'ethereum': 'https://eth.llamarpc.com'}
                stables = {'base': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'}
                
                w3 = Web3(Web3.HTTPProvider(rpc_urls.get(chain, rpc_urls['base'])))
                address = Web3.to_checksum_address(wallet['address'])
                
                # ETH balance
                eth_bal = w3.eth.get_balance(address)
                eth_amount = float(w3.from_wei(eth_bal, 'ether'))
                
                # ETH price
                resp = req.get('https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest',
                    headers={'X-CMC_PRO_API_KEY': CMC_API_KEY}, params={'symbol': 'ETH'}, timeout=10)
                eth_price = resp.json()['data']['ETH']['quote']['USD']['price']
                eth_usd = eth_amount * eth_price
                
                # USDC balance
                usdc_usd = 0
                if chain in stables:
                    balance_abi = [{"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}]
                    contract = w3.eth.contract(address=Web3.to_checksum_address(stables[chain]), abi=balance_abi)
                    usdc_usd = contract.functions.balanceOf(address).call() / 1e6
                
                cash = eth_usd + usdc_usd
                print(f"    💰 On-chain: ${cash:.2f} (ETH ${eth_usd:.2f} + USDC ${usdc_usd:.2f})", file=sys.stderr)
            except Exception as e:
                print(f"    ⚠️ On-chain balance error: {e}", file=sys.stderr)
                cash = wallet_data.get('portfolio', {}).get('USDC', 0)
        else:
            # Paper wallet: use JSON data
            cash = wallet_data.get('portfolio', {}).get('USDC', 0)
        
        # Analyze positions for this wallet
        position_analysis = analyze_wallet_positions(wallet, tradable_tokens)
        
        # Calculate wallet totals
        positions_value = sum(p.get('current_price', p.get('avg_price', 0)) * p.get('amount', 0) 
                            for p in position_analysis if p.get('current_price') or p.get('avg_price'))
        
        # Get closed positions
        closed_positions = wallet_data.get('closed_positions', [])
        # Get last 10 closed positions
        recent_closed = closed_positions[-10:] if closed_positions else []
        
        # Calculate closed P&L stats
        total_closed_pnl = sum(p.get('pnl_usd', 0) for p in closed_positions)
        win_count = sum(1 for p in closed_positions if p.get('pnl_usd', 0) > 0)
        loss_count = sum(1 for p in closed_positions if p.get('pnl_usd', 0) < 0)
        win_rate = round(win_count / len(closed_positions) * 100, 1) if closed_positions else 0
        
        wallet_info = {
            'id': wallet['id'],
            'name': wallet['name'],
            'type': wallet['type'],
            'cash': round(cash, 2),
            'positions_value': round(positions_value, 2),
            'total_value': round(cash + positions_value, 2),
            'positions_count': len(positions),
            'max_positions': max_pos,
            'slots_available': max_pos - len(positions),
            'positions': position_analysis,
            'closed_positions': recent_closed,
            'closed_stats': {
                'total_trades': len(closed_positions),
                'wins': win_count,
                'losses': loss_count,
                'win_rate': win_rate,
                'total_pnl_usd': round(total_closed_pnl, 2),
            },
        }
        
        wallets_analysis.append(wallet_info)
        total_positions += len(positions)
        total_slots += max_pos
    
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
            'chain': main_chain,
            'profile': config.get('profile', 'moderate'),
            'tradable_count': len(tradable_tokens),
        },
        'summary': {
            'total_wallets': len(wallets),
            'total_positions': total_positions,
            'total_slots': total_slots,
            'slots_available': total_slots - total_positions,
        },
        'wallets': wallets_analysis,
        'candidates': candidates,
    }
    
    # AUTO-EXECUTE: If there are BUY recommendations and slots available, execute trades
    auto_execute = os.environ.get('AUTO_EXECUTE', 'true').lower() == 'true'
    
    # Set wallet password if not in environment (needed for real trading)
    if 'WALLET_MASTER_PASSWORD' not in os.environ:
        os.environ['WALLET_MASTER_PASSWORD'] = 'BotCow'
    slots_available = total_slots - total_positions
    
    if auto_execute and slots_available > 0:
        buy_candidates = [c for c in candidates if c.get('recommendation') == 'BUY']
        
        if buy_candidates:
            print(f"\n🤖 AUTO-EXECUTE: {len(buy_candidates)} BUY signal(s), {slots_available} slot(s) available", file=sys.stderr)
            
            # Get wallet config for position sizing
            wallet_cfg = wallets[0] if wallets else {}
            position_size_pct = 5  # Default 5%
            
            # Load wallet config for position sizing
            try:
                with open(WALLETS_CONFIG) as f:
                    wc = json.load(f)
                    for w in wc.get('wallets', []):
                        if w.get('enabled'):
                            position_size_pct = w.get('position_size_pct', 5)
                            break
            except:
                pass
            
            # Calculate position size
            total_cash = sum(w.get('cash', 0) for w in wallets_analysis)
            position_usd = min(total_cash * position_size_pct / 100, total_cash * 0.3)  # Max 30% per trade
            position_usd = max(5, min(position_usd, 50))  # Between $5 and $50
            
            # Build trade decisions
            decisions = []
            for c in buy_candidates[:slots_available]:  # Limit to available slots
                symbol = c.get('symbol', '')
                dex_pair = c.get('dex_pair', {})
                token_address = dex_pair.get('baseToken', {}).get('address', '')
                
                if not token_address:
                    print(f"  ⚠️ Skip {symbol}: no token address", file=sys.stderr)
                    continue
                
                # Calculate SL/TP based on current price
                price = c.get('cmc_data', {}).get('price', 0) or c.get('technical', {}).get('price', 0)
                if price > 0:
                    stop_loss = price * 0.85  # -15%
                    tp1 = price * 1.25  # +25%
                    tp2 = price * 1.50  # +50%
                else:
                    stop_loss = None
                    tp1 = None
                    tp2 = None
                
                decisions.append({
                    'action': 'BUY',
                    'symbol': symbol,
                    'token_address': token_address,
                    'amount_usd': round(position_usd, 2),
                    'stop_loss': stop_loss,
                    'tp1': tp1,
                    'tp2': tp2,
                    'score': c.get('score', 0),
                    'reasons': c.get('reasons', []),
                })
                print(f"  🎯 {symbol}: ${position_usd:.2f} (score {c.get('score', 0)})", file=sys.stderr)
            
            # Execute trades via execute_trades.py
            if decisions:
                print(f"\n📤 Executing {len(decisions)} trade(s)...", file=sys.stderr)
                try:
                    import subprocess
                    wallet_id = wallets[0]['id'] if wallets else 'simulation'
                    
                    result = subprocess.run(
                        ['python', 'scripts/execute_trades.py', '--wallet', wallet_id],
                        input=json.dumps(decisions),
                        capture_output=True,
                        text=True,
                        cwd=os.path.dirname(os.path.dirname(__file__)),
                        timeout=120
                    )
                    
                    if result.returncode == 0:
                        print(f"✅ Trades executed successfully", file=sys.stderr)
                        print(result.stdout, file=sys.stderr)
                    else:
                        print(f"❌ Trade execution failed: {result.stderr}", file=sys.stderr)
                        
                except Exception as e:
                    print(f"❌ Error executing trades: {e}", file=sys.stderr)
            
            output['auto_executed'] = decisions
        else:
            print(f"\n📊 No BUY signals (all candidates HOLD or below threshold)", file=sys.stderr)
    
    print(json.dumps(output, indent=2, default=str))
    
    # ========== SAVE BOT STATUS ==========
    try:
        trades_count = len(output.get('auto_executed', []))
        tokens_count = len(output.get('candidates', []))
        buy_signals = len([c for c in output.get('candidates', []) if c.get('signal') == 'BUY'])
        
        # Build summary
        summary_lines = []
        if trades_count > 0:
            summary_lines.append(f"🎯 {trades_count} trade(s) exécuté(s)")
            for t in output.get('auto_executed', []):
                summary_lines.append(f"  • {t.get('action')} {t.get('symbol')} ${t.get('amount_usd', 0):.2f}")
        elif buy_signals > 0:
            summary_lines.append(f"📊 {buy_signals} signal(s) BUY, pas de slots dispos")
        else:
            summary_lines.append(f"📊 Aucun signal BUY (seuil non atteint)")
        
        # Top tokens
        top_tokens = sorted(output.get('candidates', []), key=lambda x: x.get('score', 0), reverse=True)[:5]
        if top_tokens:
            summary_lines.append("\n🏆 Top tokens:")
            for t in top_tokens:
                change = t.get('dex_momentum', 0) or t.get('cmc_data', {}).get('change_24h', 0) or 0
                summary_lines.append(f"  • {t.get('symbol')}: {change:+.1f}% | score {t.get('score', 0)}")
        
        bot_status = {
            'last_run': datetime.now().strftime('%H:%M'),
            'last_run_ts': time.time(),
            'status': 'ok' if trades_count > 0 else 'partial' if tokens_count > 0 else 'error',
            'tokens_analyzed': tokens_count,
            'buy_signals': buy_signals,
            'trades_executed': trades_count,
            'summary': '\n'.join(summary_lines),
        }
        
        bot_status_path = os.path.join(DATA_DIR, 'bot_status.json')
        with open(bot_status_path, 'w') as f:
            json.dump(bot_status, f, indent=2)
        print(f"\n✅ Bot status saved to {bot_status_path}", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ Could not save bot status: {e}", file=sys.stderr)

if __name__ == '__main__':
    main()
