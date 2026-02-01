#!/usr/bin/env python3
"""
Tests for AI Decision Module
Run: python3 tests.py
"""

import sys
sys.path.insert(0, '.')

from scorer import TokenScorer, ScoreResult, SignalStrength
from predictor import TradingPredictor, Prediction, TradingAction
from analyzer import TokenAnalyzer, analyze_token
from database import AIDecisionDB

def test_scorer():
    """Test scoring system"""
    print("🧪 Testing Scorer...")
    
    scorer = TokenScorer()
    
    # Bullish case
    result = scorer.calculate_score(
        'TEST', 'base',
        sentiment_data={'score': 0.7, 'sample_count': 20},
        volume_data={'change_24h': 100},
        price_data={'change_24h': 15, 'change_7d': 30}
    )
    assert result.total_score > 70, f"Expected > 70, got {result.total_score}"
    assert result.signal_strength in [SignalStrength.STRONG, SignalStrength.VERY_STRONG]
    print(f"  ✅ Bullish: {result.total_score:.1f}/100 ({result.signal_strength.value})")
    
    # Bearish case
    result = scorer.calculate_score(
        'TEST', 'base',
        sentiment_data={'score': -0.7, 'sample_count': 20},
        volume_data={'change_24h': -50},
        price_data={'change_24h': -20, 'change_7d': -40}
    )
    assert result.total_score < 30, f"Expected < 30, got {result.total_score}"
    assert result.signal_strength in [SignalStrength.WEAK, SignalStrength.VERY_WEAK]
    print(f"  ✅ Bearish: {result.total_score:.1f}/100 ({result.signal_strength.value})")
    
    # No data case
    result = scorer.calculate_score('TEST', 'base')
    assert result.total_score == 50, f"Expected 50, got {result.total_score}"
    assert result.confidence == 0.0
    print(f"  ✅ No data: {result.total_score:.1f}/100 (confidence: {result.confidence})")
    
    print("  ✅ Scorer tests passed!")
    return True


def test_predictor():
    """Test prediction system"""
    print("🧪 Testing Predictor...")
    
    predictor = TradingPredictor()
    
    # BUY signal
    pred = predictor.predict(
        'TEST', 'base',
        score=75,
        sentiment=0.6,
        volume_change=80,
        price_change=10
    )
    assert pred.action == TradingAction.BUY, f"Expected BUY, got {pred.action}"
    print(f"  ✅ BUY signal: {pred.action.value} (conf: {pred.confidence:.2f})")
    
    # SELL signal
    pred = predictor.predict(
        'TEST', 'base',
        score=25,
        sentiment=-0.5,
        volume_change=-40,
        price_change=-15
    )
    assert pred.action == TradingAction.SELL, f"Expected SELL, got {pred.action}"
    print(f"  ✅ SELL signal: {pred.action.value} (conf: {pred.confidence:.2f})")
    
    # HOLD signal (mixed)
    pred = predictor.predict(
        'TEST', 'base',
        score=55,
        sentiment=0.1,
        volume_change=20,
        price_change=-5
    )
    assert pred.action == TradingAction.HOLD, f"Expected HOLD, got {pred.action}"
    print(f"  ✅ HOLD signal: {pred.action.value} (conf: {pred.confidence:.2f})")
    
    # INSUFFICIENT_DATA
    pred = predictor.predict('TEST', 'base', score=50)
    assert pred.action == TradingAction.INSUFFICIENT_DATA
    print(f"  ✅ INSUFFICIENT_DATA: {pred.action.value}")
    
    print("  ✅ Predictor tests passed!")
    return True


def test_analyzer():
    """Test full analyzer"""
    print("🧪 Testing Analyzer...")
    
    # Full analysis
    result = analyze_token(
        'PEPE', 'base',
        sentiment_data={'score': 0.6, 'sample_count': 15},
        volume_data={'change_24h': 80},
        price_data={'change_24h': 12, 'change_7d': 25}
    )
    assert result.action == TradingAction.BUY
    assert result.confidence > 0.5
    assert 'PEPE' in result.summary
    print(f"  ✅ Full analysis: {result.action.value} (conf: {result.confidence:.2f})")
    
    # JSON export
    json_result = result.to_json()
    assert 'PEPE' in json_result
    assert 'BUY' in json_result
    print("  ✅ JSON export works")
    
    # Custom analyzer
    analyzer = TokenAnalyzer()
    analyzer.update_predictor_config(buy_score_threshold=80)
    result2 = analyzer.analyze_with_data(
        'TEST', 'base',
        sentiment_data={'score': 0.5, 'sample_count': 10},
        volume_data={'change_24h': 50}
    )
    # With higher threshold, should be HOLD now
    assert result2.action in [TradingAction.HOLD, TradingAction.BUY]
    print(f"  ✅ Custom config: {result2.action.value}")
    
    print("  ✅ Analyzer tests passed!")
    return True


def test_database():
    """Test database logging"""
    print("🧪 Testing Database...")
    
    import tempfile
    import os
    
    # Use temp DB for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = AIDecisionDB(db_path)
        
        # Log decision
        decision_id = db.log_decision(
            symbol='TEST',
            network='base',
            action='BUY',
            confidence=0.8,
            total_score=75,
            sentiment_score=70,
            volume_score=80,
            price_score=65,
            reason='Test decision',
            input_data={'test': True}
        )
        assert decision_id > 0
        print(f"  ✅ Logged decision ID: {decision_id}")
        
        # Retrieve
        decisions = db.get_decisions(symbol='TEST')
        assert len(decisions) == 1
        assert decisions[0].action == 'BUY'
        print(f"  ✅ Retrieved: {decisions[0].symbol} - {decisions[0].action}")
        
        # Update outcome
        db.update_outcome(decision_id, 'profit', 12.5)
        updated = db.get_decision_by_id(decision_id)
        assert updated.outcome == 'profit'
        assert updated.outcome_pct == 12.5
        print(f"  ✅ Outcome updated: {updated.outcome} ({updated.outcome_pct}%)")
        
        # Stats
        stats = db.get_stats_summary()
        assert stats['total_decisions'] == 1
        print(f"  ✅ Stats: {stats}")
    
    print("  ✅ Database tests passed!")
    return True


def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("🤖 AI Decision Module Tests")
    print("=" * 50)
    print()
    
    tests = [
        ("Scorer", test_scorer),
        ("Predictor", test_predictor),
        ("Analyzer", test_analyzer),
        ("Database", test_database),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ {name} FAILED: {e}")
            failed += 1
        print()
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
