"""
Sentiment analyzer for crypto social media content.
Uses FinBERT, Crypto-BERT, and custom crypto lexicon.
"""
import re
import asyncio
from datetime import datetime
from typing import Optional
from collections import defaultdict
import logging

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    pipeline
)
import numpy as np

from models import SentimentScore, SocialPost

logger = logging.getLogger(__name__)


# Crypto-specific sentiment lexicon
BULLISH_TERMS = {
    # Strong bullish
    "moon": 2.0, "mooning": 2.0, "moonshot": 2.0,
    "pump": 1.5, "pumping": 1.5, "pumped": 1.5,
    "bullish": 1.5, "bull": 1.0, "bulls": 1.0,
    "ath": 1.5, "breakout": 1.5, "breaking out": 1.5,
    "gem": 1.5, "hidden gem": 2.0,
    "100x": 2.0, "1000x": 2.0, "10x": 1.5,
    "lambo": 1.5, "wagmi": 1.5, "lfg": 1.5,
    "buy": 1.0, "buying": 1.0, "accumulate": 1.0,
    "hodl": 1.0, "hold": 0.5, "holding": 0.5,
    "send it": 1.5, "sending": 1.0,
    "green": 1.0, "rocket": 1.5, "🚀": 1.5,
    "parabolic": 2.0, "vertical": 1.5,
    "undervalued": 1.5, "cheap": 1.0,
    "alpha": 1.5, "early": 1.0,
    "partnership": 1.0, "listing": 1.5,
    "binance": 1.0, "coinbase": 1.0,
    
    # Moderate bullish
    "bullrun": 1.0, "uptrend": 1.0,
    "support": 0.5, "bounce": 0.5,
    "recovery": 0.5, "recovering": 0.5,
    "adoption": 0.5, "mainstream": 0.5,
}

BEARISH_TERMS = {
    # Strong bearish
    "dump": -1.5, "dumping": -1.5, "dumped": -1.5,
    "crash": -2.0, "crashing": -2.0, "crashed": -2.0,
    "scam": -2.0, "rug": -2.0, "rugpull": -2.0, "rugged": -2.0,
    "bearish": -1.5, "bear": -1.0, "bears": -1.0,
    "rekt": -1.5, "liquidated": -1.5,
    "sell": -1.0, "selling": -1.0, "sold": -1.0,
    "exit": -1.0, "exiting": -1.0,
    "ngmi": -1.5, "dead": -1.5, "dying": -1.5,
    "red": -1.0, "blood": -1.5, "bloodbath": -2.0,
    "ponzi": -2.0, "fraud": -2.0,
    "hack": -2.0, "hacked": -2.0, "exploit": -2.0,
    "warning": -1.0, "careful": -0.5,
    "overvalued": -1.5, "bubble": -1.5,
    "fud": -0.5,  # Can be used defensively
    
    # Moderate bearish
    "downtrend": -1.0, "resistance": -0.5,
    "correction": -0.5, "pullback": -0.5,
    "fear": -1.0, "panic": -1.5,
    "delist": -1.5, "delisting": -1.5,
}


class CryptoSentimentAnalyzer:
    """
    Multi-model sentiment analyzer optimized for crypto content.
    Combines transformer models with crypto-specific lexicon.
    """
    
    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        device: str = None,
        use_lexicon: bool = True
    ):
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.use_lexicon = use_lexicon
        
        # Lazy loading
        self._model = None
        self._tokenizer = None
        self._pipeline = None
        
        # Alternative models
        self.available_models = {
            "finbert": "ProsusAI/finbert",
            "finbert-tone": "yiyanghkust/finbert-tone",
            "twitter-roberta": "cardiffnlp/twitter-roberta-base-sentiment-latest",
            "distilbert": "distilbert-base-uncased-finetuned-sst-2-english",
        }
        
        # Cache for repeated texts
        self._cache: dict[str, SentimentScore] = {}
        self._cache_max_size = 1000
        
        logger.info(f"Initializing sentiment analyzer with {model_name} on {self.device}")
    
    def _load_model(self):
        """Lazy load the model and tokenizer."""
        if self._pipeline is not None:
            return
        
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name
            ).to(self.device)
            
            self._pipeline = pipeline(
                "sentiment-analysis",
                model=self._model,
                tokenizer=self._tokenizer,
                device=0 if self.device == "cuda" else -1,
                max_length=512,
                truncation=True
            )
            
            logger.info(f"Model {self.model_name} loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            # Fallback to simpler model
            self._pipeline = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=-1
            )
            self.model_name = "distilbert-fallback"
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and preprocess text for analysis."""
        # Remove URLs
        text = re.sub(r'http\S+|www\.\S+', '', text)
        
        # Remove contract addresses
        text = re.sub(r'0x[a-fA-F0-9]{40}', '', text)
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Limit length
        if len(text) > 500:
            text = text[:500]
        
        return text.strip()
    
    def _lexicon_score(self, text: str) -> tuple[float, list[str]]:
        """Calculate sentiment score using crypto lexicon."""
        text_lower = text.lower()
        total_score = 0.0
        tokens_found = []
        
        # Check bullish terms
        for term, weight in BULLISH_TERMS.items():
            if term in text_lower:
                total_score += weight
                tokens_found.append(f"+{term}")
        
        # Check bearish terms
        for term, weight in BEARISH_TERMS.items():
            if term in text_lower:
                total_score += weight
                tokens_found.append(f"-{term}")
        
        # Normalize to -1 to 1
        if tokens_found:
            normalized = np.tanh(total_score / 3)  # Soft normalization
        else:
            normalized = 0.0
        
        return normalized, tokens_found
    
    def _model_score(self, text: str) -> tuple[float, float]:
        """Get sentiment score from transformer model."""
        self._load_model()
        
        try:
            result = self._pipeline(text)[0]
            label = result['label'].lower()
            score = result['score']
            
            # Convert to -1 to 1 scale
            if 'positive' in label or 'bullish' in label:
                sentiment = score
            elif 'negative' in label or 'bearish' in label:
                sentiment = -score
            else:
                sentiment = 0.0
            
            return sentiment, score  # sentiment and confidence
            
        except Exception as e:
            logger.error(f"Model inference error: {e}")
            return 0.0, 0.0
    
    def analyze(self, text: str) -> SentimentScore:
        """
        Analyze sentiment of a single text.
        Combines transformer model with crypto lexicon.
        """
        # Check cache
        cache_key = text[:100]
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Preprocess
        clean_text = self._preprocess_text(text)
        
        if not clean_text:
            return SentimentScore(
                text=text,
                score=0.0,
                confidence=0.0,
                model_used="none"
            )
        
        # Get model score
        model_sentiment, model_confidence = self._model_score(clean_text)
        
        # Get lexicon score
        lexicon_sentiment, tokens_found = self._lexicon_score(text)
        
        # Combine scores (weighted average)
        if self.use_lexicon and tokens_found:
            # Lexicon gets more weight when crypto terms are found
            lexicon_weight = min(len(tokens_found) * 0.1, 0.5)
            model_weight = 1 - lexicon_weight
            
            combined_score = (
                model_sentiment * model_weight +
                lexicon_sentiment * lexicon_weight
            )
            
            # Boost confidence if model and lexicon agree
            if (model_sentiment > 0 and lexicon_sentiment > 0) or \
               (model_sentiment < 0 and lexicon_sentiment < 0):
                combined_confidence = min(model_confidence + 0.1, 1.0)
            else:
                combined_confidence = model_confidence * 0.8
        else:
            combined_score = model_sentiment
            combined_confidence = model_confidence
        
        result = SentimentScore(
            text=text,
            score=combined_score,
            confidence=combined_confidence,
            tokens_detected=tokens_found,
            model_used=self.model_name,
            timestamp=datetime.utcnow()
        )
        
        # Cache result
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entries
            keys_to_remove = list(self._cache.keys())[:self._cache_max_size // 2]
            for k in keys_to_remove:
                del self._cache[k]
        self._cache[cache_key] = result
        
        return result
    
    def analyze_batch(
        self,
        texts: list[str],
        batch_size: int = 32
    ) -> list[SentimentScore]:
        """Analyze multiple texts efficiently."""
        self._load_model()
        
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            clean_batch = [self._preprocess_text(t) for t in batch]
            
            # Filter empty texts
            valid_indices = [j for j, t in enumerate(clean_batch) if t]
            valid_texts = [clean_batch[j] for j in valid_indices]
            
            if not valid_texts:
                results.extend([
                    SentimentScore(text=t, score=0.0, confidence=0.0)
                    for t in batch
                ])
                continue
            
            try:
                model_results = self._pipeline(valid_texts)
            except Exception as e:
                logger.error(f"Batch inference error: {e}")
                model_results = [{'label': 'neutral', 'score': 0.0}] * len(valid_texts)
            
            # Process results
            batch_results = []
            valid_idx = 0
            
            for j, original_text in enumerate(batch):
                if j in valid_indices:
                    result = model_results[valid_idx]
                    valid_idx += 1
                    
                    # Convert label to score
                    label = result['label'].lower()
                    confidence = result['score']
                    
                    if 'positive' in label or 'bullish' in label:
                        model_sentiment = confidence
                    elif 'negative' in label or 'bearish' in label:
                        model_sentiment = -confidence
                    else:
                        model_sentiment = 0.0
                    
                    # Add lexicon
                    lexicon_sentiment, tokens = self._lexicon_score(original_text)
                    
                    if self.use_lexicon and tokens:
                        weight = min(len(tokens) * 0.1, 0.5)
                        final_score = model_sentiment * (1 - weight) + lexicon_sentiment * weight
                    else:
                        final_score = model_sentiment
                    
                    batch_results.append(SentimentScore(
                        text=original_text,
                        score=final_score,
                        confidence=confidence,
                        tokens_detected=tokens,
                        model_used=self.model_name
                    ))
                else:
                    batch_results.append(SentimentScore(
                        text=original_text,
                        score=0.0,
                        confidence=0.0,
                        model_used="skipped"
                    ))
            
            results.extend(batch_results)
        
        return results
    
    async def analyze_async(self, text: str) -> SentimentScore:
        """Async wrapper for analyze."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.analyze, text)
    
    async def analyze_batch_async(
        self,
        texts: list[str],
        batch_size: int = 32
    ) -> list[SentimentScore]:
        """Async wrapper for batch analysis."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: self.analyze_batch(texts, batch_size)
        )


class TokenSentimentAggregator:
    """
    Aggregates sentiment scores for a specific token.
    Tracks sentiment over time and calculates trends.
    """
    
    def __init__(self, analyzer: CryptoSentimentAnalyzer = None):
        self.analyzer = analyzer or CryptoSentimentAnalyzer()
        self.token_sentiments: dict[str, list[SentimentScore]] = defaultdict(list)
        self.max_history = 1000
    
    async def analyze_posts(
        self,
        token: str,
        posts: list[SocialPost]
    ) -> dict:
        """Analyze sentiment of posts for a token."""
        if not posts:
            return {
                "token": token,
                "count": 0,
                "average_sentiment": 0.0,
                "sentiment_label": "Neutral",
                "positive_ratio": 0.0,
                "negative_ratio": 0.0
            }
        
        # Extract texts
        texts = [p.content for p in posts]
        
        # Batch analyze
        sentiments = await self.analyzer.analyze_batch_async(texts)
        
        # Store results
        self.token_sentiments[token].extend(sentiments)
        
        # Trim history
        if len(self.token_sentiments[token]) > self.max_history:
            self.token_sentiments[token] = self.token_sentiments[token][-self.max_history:]
        
        # Calculate aggregates
        scores = [s.score for s in sentiments]
        avg_sentiment = np.mean(scores)
        
        positive = sum(1 for s in scores if s > 0.2)
        negative = sum(1 for s in scores if s < -0.2)
        total = len(scores)
        
        return {
            "token": token,
            "count": total,
            "average_sentiment": float(avg_sentiment),
            "sentiment_label": self._get_label(avg_sentiment),
            "positive_ratio": positive / total if total > 0 else 0.0,
            "negative_ratio": negative / total if total > 0 else 0.0,
            "confidence": float(np.mean([s.confidence for s in sentiments])),
            "top_bullish_terms": self._get_top_terms(sentiments, positive=True),
            "top_bearish_terms": self._get_top_terms(sentiments, positive=False),
        }
    
    def _get_label(self, score: float) -> str:
        """Convert score to label."""
        if score > 0.5:
            return "Very Bullish"
        elif score > 0.2:
            return "Bullish"
        elif score > -0.2:
            return "Neutral"
        elif score > -0.5:
            return "Bearish"
        else:
            return "Very Bearish"
    
    def _get_top_terms(
        self,
        sentiments: list[SentimentScore],
        positive: bool = True
    ) -> list[str]:
        """Get most common sentiment terms."""
        term_counts = defaultdict(int)
        prefix = '+' if positive else '-'
        
        for s in sentiments:
            for term in s.tokens_detected:
                if term.startswith(prefix):
                    term_counts[term[1:]] += 1
        
        sorted_terms = sorted(term_counts.items(), key=lambda x: x[1], reverse=True)
        return [term for term, count in sorted_terms[:5]]
    
    def get_sentiment_trend(
        self,
        token: str,
        window_size: int = 10
    ) -> dict:
        """Calculate sentiment trend for a token."""
        sentiments = self.token_sentiments.get(token, [])
        
        if len(sentiments) < window_size * 2:
            return {"trend": "insufficient_data", "change": 0.0}
        
        # Recent vs older sentiment
        recent = sentiments[-window_size:]
        older = sentiments[-window_size * 2:-window_size]
        
        recent_avg = np.mean([s.score for s in recent])
        older_avg = np.mean([s.score for s in older])
        
        change = recent_avg - older_avg
        
        if change > 0.2:
            trend = "improving"
        elif change < -0.2:
            trend = "declining"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "change": float(change),
            "recent_sentiment": float(recent_avg),
            "older_sentiment": float(older_avg)
        }


async def main():
    """Example usage."""
    # Initialize analyzer
    analyzer = CryptoSentimentAnalyzer(model_name="ProsusAI/finbert")
    
    # Test texts
    test_texts = [
        "$PEPE is absolutely mooning! 🚀🚀🚀 LFG!",
        "Warning: $SCAM looks like a rug pull, be careful",
        "Just bought some $BTC, looks like a good entry point",
        "$ETH holding support, could bounce from here",
        "This project is dead, devs abandoned it. Exit now.",
        "$SOL to $1000 is inevitable, most undervalued L1",
        "Market looking bearish, expecting more blood tomorrow",
    ]
    
    print("=" * 60)
    print("CRYPTO SENTIMENT ANALYZER")
    print("=" * 60)
    
    for text in test_texts:
        result = analyzer.analyze(text)
        print(f"\n📝 {text}")
        print(f"   Score: {result.score:+.3f} ({result.label})")
        print(f"   Confidence: {result.confidence:.3f}")
        if result.tokens_detected:
            print(f"   Tokens: {', '.join(result.tokens_detected)}")
    
    # Batch analysis
    print("\n" + "=" * 60)
    print("BATCH ANALYSIS")
    print("=" * 60)
    
    batch_results = analyzer.analyze_batch(test_texts)
    
    avg_sentiment = np.mean([r.score for r in batch_results])
    print(f"\nAverage sentiment: {avg_sentiment:+.3f}")
    print(f"Bullish texts: {sum(1 for r in batch_results if r.score > 0.2)}")
    print(f"Bearish texts: {sum(1 for r in batch_results if r.score < -0.2)}")
    print(f"Neutral texts: {sum(1 for r in batch_results if -0.2 <= r.score <= 0.2)}")


if __name__ == "__main__":
    asyncio.run(main())
