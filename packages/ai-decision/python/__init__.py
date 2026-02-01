"""
AI Decision Module for Crypto SmallCap Trader
Rule-based scoring and prediction system for trading signals

⚠️ DISCLAIMER: This module is EXPERIMENTAL. 
- It uses rule-based heuristics, NOT machine learning
- Past performance does not guarantee future results
- Never invest more than you can afford to lose
- Always DYOR (Do Your Own Research)
"""

# Support both package and direct imports
try:
    from .scorer import TokenScorer, ScoreResult
    from .predictor import TradingPredictor, Prediction, TradingAction
    from .analyzer import TokenAnalyzer, AnalysisResult, analyze_token
    from .database import AIDecisionDB, get_ai_db
except ImportError:
    from scorer import TokenScorer, ScoreResult
    from predictor import TradingPredictor, Prediction, TradingAction
    from analyzer import TokenAnalyzer, AnalysisResult, analyze_token
    from database import AIDecisionDB, get_ai_db

__all__ = [
    'TokenScorer', 
    'ScoreResult',
    'TradingPredictor', 
    'Prediction', 
    'TradingAction',
    'TokenAnalyzer',
    'AnalysisResult',
    'analyze_token',
    'AIDecisionDB',
    'get_ai_db'
]

__version__ = '0.1.0'
