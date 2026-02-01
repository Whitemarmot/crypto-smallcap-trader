# Social Sentiment Analysis for Crypto Trading

Détection de hype et génération de signaux BUY/SELL basés sur l'analyse des réseaux sociaux.

## 🎯 Features

- **Twitter Scraping** - Via Nitter instances (pas besoin d'API officielle)
- **Telegram Monitoring** - Surveillance des channels crypto en temps réel
- **Sentiment Analysis** - FinBERT + lexique crypto custom
- **Viral Detection** - Détection de propagation virale
- **Influencer Tracking** - Suivi des influenceurs crypto
- **Hype Alerts** - Alertes avant pump potentiel

## 📦 Installation

```bash
cd packages/social-sentiment
pip install -r requirements.txt
```

### Configuration Telegram (optionnel)

Pour le monitoring Telegram en temps réel:
1. Créer une app sur https://my.telegram.org/apps
2. Définir les variables d'environnement:

```bash
export TELEGRAM_API_ID="your_api_id"
export TELEGRAM_API_HASH="your_api_hash"
```

## 🚀 Usage

### Signal Generator

```python
import asyncio
from social_sentiment import SocialSignalGenerator, SignalType

async def main():
    generator = SocialSignalGenerator()
    
    # Générer un signal pour un token
    signal = await generator.generate_signal("PEPE")
    
    print(f"Signal: {signal.signal_type.value}")
    print(f"Confidence: {signal.confidence:.1%}")
    print(f"Sentiment: {signal.sentiment_score:+.3f}")
    print(f"Viral Score: {signal.viral_score:.3f}")
    
    if signal.signal_type == SignalType.STRONG_BUY:
        print("🚀 Potential pump detected!")

asyncio.run(main())
```

### Hype Detection

```python
async def monitor_hype():
    generator = SocialSignalGenerator()
    
    tokens = ["PEPE", "WIF", "BONK", "DOGE"]
    
    alerts = await generator.detect_hype(tokens)
    
    for alert in alerts:
        if alert.alert_level in ["high", "critical"]:
            print(f"🚨 {alert.token}: {alert.reasons}")

asyncio.run(monitor_hype())
```

### Sentiment Analysis

```python
from social_sentiment import CryptoSentimentAnalyzer

analyzer = CryptoSentimentAnalyzer()

result = analyzer.analyze("$PEPE is mooning! 🚀🚀🚀 LFG!")
print(f"Score: {result.score:+.3f} ({result.label})")
# Score: +0.823 (Very Bullish)

result = analyzer.analyze("This looks like a rug pull, be careful")
print(f"Score: {result.score:+.3f} ({result.label})")
# Score: -0.712 (Very Bearish)
```

## 📊 Signal Components

Le signal final combine plusieurs métriques:

| Component | Weight | Description |
|-----------|--------|-------------|
| Sentiment | 25% | Score de sentiment moyen |
| Volume | 20% | Volume de mentions vs baseline |
| Viral | 30% | Vitesse de propagation |
| Influencer | 25% | Activité des influenceurs |

### Signal Types

- **STRONG_BUY** - Score composite ≥ 75%
- **BUY** - Score composite ≥ 60%
- **NEUTRAL** - Score entre 40-60%
- **SELL** - Score composite ≤ 40%
- **STRONG_SELL** - Score composite ≤ 25%

## 🔍 Manipulation Detection

Le système détecte les signaux de manipulation:

- **Author Concentration** - Même auteurs qui spamment
- **Timing Clustering** - Posts coordonnés dans le temps
- **Content Similarity** - Messages identiques/similaires

Un score de `manipulation_risk` (0-1) ajuste la confiance du signal.

## 📡 Data Sources

### Twitter/X
- Nitter instances publiques (rotation automatique)
- snscrape (optionnel, backup)
- Pas besoin d'API officielle

### Telegram
- Telethon client
- Channels crypto populaires
- Real-time via handlers

## 🎯 Influencers Suivis

Le système track automatiquement les influenceurs crypto majeurs:
- @VitalikButerin, @elonmusk
- @CryptoCapo_, @Pentosh1, @loomdart
- @CryptoKaleo, @inversebrah
- Et plus...

## ⚠️ Disclaimer

Ce package est fourni à titre éducatif. Le trading de cryptomonnaies comporte des risques significatifs. Ne tradez jamais plus que ce que vous pouvez vous permettre de perdre.

## 📝 License

MIT
