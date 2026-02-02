#!/usr/bin/env python3
"""
🧰 Analysis Tools for Jean-Michel Trading Bot
Tools for technical analysis, sentiment analysis, and data gathering.
"""

import json
import os
import sys
from datetime import datetime, timedelta

# Technical Analysis
def get_technical_indicators(symbol: str, days: int = 30) -> dict:
    """Get technical indicators for a symbol using yfinance + ta"""
    try:
        import yfinance as yf
        import ta
        import pandas as pd
        
        # Map crypto symbols to yfinance format
        ticker = f"{symbol}-USD"
        
        # Fetch data
        end = datetime.now()
        start = end - timedelta(days=days)
        df = yf.download(ticker, start=start, end=end, progress=False)
        
        # Flatten multi-index columns if present
        if hasattr(df.columns, 'levels'):
            df.columns = df.columns.get_level_values(0)
        
        if df.empty or len(df) < 14:
            return {'symbol': symbol, 'error': 'Insufficient data'}
        
        # Calculate indicators
        # RSI
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff()
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df['Close'])
        df['BB_Upper'] = bb.bollinger_hband()
        df['BB_Lower'] = bb.bollinger_lband()
        df['BB_Middle'] = bb.bollinger_mavg()
        
        # SMA
        df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50)
        
        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # Determine signals
        rsi = latest['RSI']
        rsi_signal = 'OVERSOLD' if rsi < 30 else 'OVERBOUGHT' if rsi > 70 else 'NEUTRAL'
        
        macd_signal = 'BULLISH' if latest['MACD'] > latest['MACD_Signal'] else 'BEARISH'
        macd_cross = 'CROSS_UP' if prev['MACD'] <= prev['MACD_Signal'] and latest['MACD'] > latest['MACD_Signal'] else \
                     'CROSS_DOWN' if prev['MACD'] >= prev['MACD_Signal'] and latest['MACD'] < latest['MACD_Signal'] else None
        
        price = latest['Close']
        bb_position = 'UPPER' if price > latest['BB_Upper'] else 'LOWER' if price < latest['BB_Lower'] else 'MIDDLE'
        
        trend = 'BULLISH' if latest['SMA_20'] > latest['SMA_50'] else 'BEARISH'
        
        return {
            'symbol': symbol,
            'price': round(float(price), 6),
            'rsi': round(float(rsi), 2),
            'rsi_signal': rsi_signal,
            'macd': round(float(latest['MACD']), 6),
            'macd_signal_line': round(float(latest['MACD_Signal']), 6),
            'macd_signal': macd_signal,
            'macd_cross': macd_cross,
            'bb_upper': round(float(latest['BB_Upper']), 6),
            'bb_lower': round(float(latest['BB_Lower']), 6),
            'bb_position': bb_position,
            'sma_20': round(float(latest['SMA_20']), 6),
            'sma_50': round(float(latest['SMA_50']), 6),
            'trend': trend,
            'summary': f"RSI={rsi:.0f}({rsi_signal}) MACD={macd_signal} Trend={trend}"
        }
    except Exception as e:
        return {'symbol': symbol, 'error': str(e)}


def analyze_sentiment_text(text: str) -> dict:
    """Analyze sentiment of text using VADER"""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        
        analyzer = SentimentIntensityAnalyzer()
        scores = analyzer.polarity_scores(text)
        
        compound = scores['compound']
        if compound >= 0.05:
            sentiment = 'POSITIVE'
        elif compound <= -0.05:
            sentiment = 'NEGATIVE'
        else:
            sentiment = 'NEUTRAL'
        
        return {
            'sentiment': sentiment,
            'compound': round(compound, 3),
            'positive': round(scores['pos'], 3),
            'negative': round(scores['neg'], 3),
            'neutral': round(scores['neu'], 3),
        }
    except Exception as e:
        return {'sentiment': 'UNKNOWN', 'error': str(e)}


def get_crypto_news_rss(limit: int = 10) -> list:
    """Get latest crypto news from RSS feeds"""
    try:
        import feedparser
        
        feeds = [
            'https://cointelegraph.com/rss',
            'https://decrypt.co/feed',
            'https://bitcoinmagazine.com/.rss/full/',
        ]
        
        articles = []
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    articles.append({
                        'title': entry.get('title', ''),
                        'link': entry.get('link', ''),
                        'published': entry.get('published', ''),
                        'source': feed.feed.get('title', feed_url),
                    })
            except:
                continue
        
        # Sort by date and limit
        articles = sorted(articles, key=lambda x: x.get('published', ''), reverse=True)[:limit]
        return articles
    except Exception as e:
        return [{'error': str(e)}]


def get_exchange_data(symbol: str, exchange: str = 'binance') -> dict:
    """Get detailed exchange data using ccxt"""
    try:
        import ccxt
        
        ex = getattr(ccxt, exchange)()
        
        # Fetch ticker
        ticker_symbol = f"{symbol}/USDT"
        ticker = ex.fetch_ticker(ticker_symbol)
        
        # Fetch order book
        orderbook = ex.fetch_order_book(ticker_symbol, limit=10)
        
        bid_volume = sum([b[1] for b in orderbook['bids'][:5]])
        ask_volume = sum([a[1] for a in orderbook['asks'][:5]])
        
        return {
            'symbol': symbol,
            'exchange': exchange,
            'price': ticker.get('last'),
            'change_24h': ticker.get('percentage'),
            'volume_24h': ticker.get('quoteVolume'),
            'high_24h': ticker.get('high'),
            'low_24h': ticker.get('low'),
            'bid': ticker.get('bid'),
            'ask': ticker.get('ask'),
            'spread_pct': round((ticker['ask'] - ticker['bid']) / ticker['bid'] * 100, 4) if ticker.get('bid') else None,
            'bid_volume_top5': round(bid_volume, 2),
            'ask_volume_top5': round(ask_volume, 2),
            'buy_pressure': round(bid_volume / (bid_volume + ask_volume) * 100, 1) if (bid_volume + ask_volume) > 0 else 50,
        }
    except Exception as e:
        return {'symbol': symbol, 'error': str(e)}


def analyze_multiple_symbols(symbols: list) -> dict:
    """Analyze multiple symbols and return summary"""
    results = {}
    for symbol in symbols:
        results[symbol] = {
            'technical': get_technical_indicators(symbol),
        }
    return results


# Main for testing
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--technical', type=str, help='Get technical indicators for symbol')
    parser.add_argument('--sentiment', type=str, help='Analyze sentiment of text')
    parser.add_argument('--news', action='store_true', help='Get crypto news')
    parser.add_argument('--exchange', type=str, help='Get exchange data for symbol')
    args = parser.parse_args()
    
    if args.technical:
        print(json.dumps(get_technical_indicators(args.technical), indent=2))
    elif args.sentiment:
        print(json.dumps(analyze_sentiment_text(args.sentiment), indent=2))
    elif args.news:
        print(json.dumps(get_crypto_news_rss(), indent=2))
    elif args.exchange:
        print(json.dumps(get_exchange_data(args.exchange), indent=2))
    else:
        print("Use --technical SYMBOL, --sentiment TEXT, --news, or --exchange SYMBOL")
