# 🤖 AI Decision Module

Rule-based scoring and trading signal system for Crypto SmallCap Trader.

## ⚠️ DISCLAIMER

**THIS MODULE IS EXPERIMENTAL - NOT FINANCIAL ADVICE**

- Uses rule-based heuristics, NOT machine learning
- Past results do not predict future performance
- Never invest more than you can afford to lose
- Always DYOR (Do Your Own Research)

## Features

### 1. Token Scoring (0-100)
Combines multiple signals into a unified score:
- **Sentiment** (35%): Social media sentiment (-1 to +1)
- **Volume** (35%): 24h volume change
- **Price** (30%): Price momentum (24h + 7d)

### 2. Trading Prediction
Rule-based signal generation:
- **BUY**: Score ≥ 70, sentiment ≥ 0.3, volume ≥ +50%
- **SELL**: Score ≤ 30, sentiment ≤ -0.3, volume ≤ -30%
- **HOLD**: Mixed signals or low confidence
- **INSUFFICIENT_DATA**: Not enough data points

### 3. Decision Logging
All decisions are logged to SQLite for tracking:
- Symbol, network, action, confidence
- All input scores
- Optional outcome tracking for accuracy measurement

## Usage

### Quick Analysis
```python
from analyzer import analyze_token

result = analyze_token(
    'PEPE', 'base',
    sentiment_data={'score': 0.6, 'sample_count': 15},
    volume_data={'change_24h': 80},
    price_data={'change_24h': 12, 'change_7d': 25}
)

print(result.action)      # TradingAction.BUY
print(result.confidence)  # 1.0
print(result.summary)     # Full summary string
```

### With Custom Config
```python
from analyzer import TokenAnalyzer
from predictor import PredictorConfig

config = PredictorConfig(
    buy_score_threshold=75,  # More conservative
    min_buy_signals=3        # Need more confirmation
)

analyzer = TokenAnalyzer(predictor_config=config)
result = analyzer.analyze_with_data(...)
```

### Logging Decisions
```python
from database import get_ai_db

db = get_ai_db()
decision_id = db.log_analysis_result(result)

# Later, track outcome
db.update_outcome(decision_id, outcome='profit', outcome_pct=15.5)
```

## Components

| File | Description |
|------|-------------|
| `scorer.py` | Token scoring system (0-100) |
| `predictor.py` | Rule-based BUY/SELL/HOLD predictor |
| `analyzer.py` | Main interface combining scorer + predictor |
| `database.py` | SQLite logging for decisions |

## Configuration

### Scoring Weights
```python
sentiment_weight = 0.35  # 35%
volume_weight = 0.35     # 35%
price_weight = 0.30      # 30%
```

### Prediction Thresholds
```python
buy_score_threshold = 70.0
buy_sentiment_min = 0.3
buy_volume_increase_min = 50.0

sell_score_threshold = 30.0
sell_sentiment_max = -0.3
sell_volume_decrease_max = -30.0

min_confidence_to_act = 0.5
require_multiple_signals = True
min_buy_signals = 2
```

## Integration with Streamlit

The module integrates with the Streamlit dashboard:
- Navigate to **🤖 AI Analysis** page
- Enter token data manually or connect to data sources
- View historical decisions and accuracy stats
- Configure thresholds in real-time

## Future Improvements

- [ ] Connect to real-time data sources
- [ ] Machine learning model training
- [ ] Backtesting with historical data
- [ ] Automated trade execution
- [ ] Multi-token portfolio analysis
