/**
 * Sentiment Analyzer
 * Calculates sentiment score from text using multiple signals
 */

import Sentiment from 'sentiment';
import { SentimentResult } from '../types';

// Crypto-specific lexicon additions
const CRYPTO_LEXICON: Record<string, number> = {
  // Bullish terms
  'moon': 4,
  'mooning': 5,
  'bullish': 4,
  'pump': 3,
  'pumping': 4,
  'gem': 3,
  'diamond': 3,
  'hodl': 2,
  'lfg': 3,
  'wagmi': 3,
  'dyor': 1,
  'alpha': 3,
  'undervalued': 3,
  'breakout': 3,
  'accumulate': 2,
  'accumulating': 2,
  'bullrun': 4,
  'lambo': 2,
  'rocket': 3,
  '100x': 5,
  '10x': 4,
  '1000x': 5,
  'massive': 2,
  'explode': 3,
  'exploding': 4,
  'launch': 2,
  'launching': 2,
  'airdrop': 2,
  'whale': 1,
  'whales': 1,
  
  // Bearish terms
  'dump': -4,
  'dumping': -5,
  'rug': -5,
  'rugpull': -5,
  'scam': -5,
  'ponzi': -5,
  'bearish': -4,
  'crash': -4,
  'crashing': -5,
  'dead': -3,
  'rekt': -4,
  'ngmi': -3,
  'sell': -2,
  'selling': -2,
  'exit': -2,
  'bottom': -1,
  'bleeding': -3,
  'bleed': -3,
  'overvalued': -3,
  'bubble': -3,
  'correction': -2,
  'bagholders': -3,
  'bagholder': -3,
  'honeypot': -5,
  'fake': -4,
  'fraud': -5,
};

// Bullish signal patterns
const BULLISH_PATTERNS = [
  /\b(easy|ez)\s*(100|1000|10)x\b/i,
  /going\s+to\s+(the\s+)?moon/i,
  /next\s+(100|1000)x/i,
  /don'?t\s+miss/i,
  /early\s+(on|entry|bird)/i,
  /buy\s+(the\s+)?dip/i,
  /load(ing)?\s+up/i,
  /huge\s+(potential|gains)/i,
  /about\s+to\s+(explode|pump|moon)/i,
  /sleeping\s+giant/i,
  /hidden\s+gem/i,
  /still\s+(early|undervalued)/i,
  /breaking\s+(out|resistance)/i,
];

// Bearish signal patterns
const BEARISH_PATTERNS = [
  /get\s+out(\s+now)?/i,
  /stay\s+away/i,
  /obvious\s+(scam|rug)/i,
  /don'?t\s+buy/i,
  /about\s+to\s+(dump|crash|rug)/i,
  /team\s+(dumping|selling)/i,
  /dev\s+(abandoned|rugged)/i,
  /no\s+liquidity/i,
  /locked\s+liquidity\s*(fake|not)/i,
  /red\s+flag/i,
  /ponzi\s+scheme/i,
  /exit\s+scam/i,
  /dead\s+(project|coin|token)/i,
];

export class SentimentAnalyzer {
  private sentiment: Sentiment;
  
  constructor() {
    this.sentiment = new Sentiment();
    // Register crypto-specific words
    this.sentiment.registerLanguage('crypto', {
      labels: CRYPTO_LEXICON
    });
  }
  
  /**
   * Analyze sentiment of a single text
   */
  analyze(text: string): SentimentResult {
    // Clean text
    const cleanText = this.preprocessText(text);
    
    // Base sentiment analysis
    const result = this.sentiment.analyze(cleanText, {
      extras: CRYPTO_LEXICON
    });
    
    // Extract crypto-specific signals
    const bullishSignals = this.findPatterns(cleanText, BULLISH_PATTERNS);
    const bearishSignals = this.findPatterns(cleanText, BEARISH_PATTERNS);
    
    // Calculate adjusted score
    const patternBonus = (bullishSignals.length * 10) - (bearishSignals.length * 10);
    const rawScore = result.comparative * 100 + patternBonus;
    
    // Clamp to -100 to +100
    const score = Math.max(-100, Math.min(100, rawScore));
    
    // Calculate magnitude (how strong is the sentiment)
    const magnitude = Math.min(100, Math.abs(result.score) + (bullishSignals.length + bearishSignals.length) * 5);
    
    return {
      score: Math.round(score),
      magnitude: Math.round(magnitude),
      keywords: [...result.positive, ...result.negative],
      bullishSignals,
      bearishSignals,
    };
  }
  
  /**
   * Analyze multiple texts and return aggregate sentiment
   */
  analyzeMultiple(texts: string[]): SentimentResult {
    if (texts.length === 0) {
      return {
        score: 0,
        magnitude: 0,
        keywords: [],
        bullishSignals: [],
        bearishSignals: [],
      };
    }
    
    const results = texts.map(t => this.analyze(t));
    
    // Weighted average based on magnitude
    const totalMagnitude = results.reduce((sum, r) => sum + r.magnitude, 0);
    const weightedScore = totalMagnitude > 0
      ? results.reduce((sum, r) => sum + r.score * r.magnitude, 0) / totalMagnitude
      : results.reduce((sum, r) => sum + r.score, 0) / results.length;
    
    // Aggregate keywords and signals
    const allKeywords = new Set<string>();
    const allBullish = new Set<string>();
    const allBearish = new Set<string>();
    
    results.forEach(r => {
      r.keywords.forEach(k => allKeywords.add(k));
      r.bullishSignals.forEach(s => allBullish.add(s));
      r.bearishSignals.forEach(s => allBearish.add(s));
    });
    
    return {
      score: Math.round(weightedScore),
      magnitude: Math.round(totalMagnitude / results.length),
      keywords: Array.from(allKeywords).slice(0, 20),
      bullishSignals: Array.from(allBullish),
      bearishSignals: Array.from(allBearish),
    };
  }
  
  /**
   * Preprocess text for analysis
   */
  private preprocessText(text: string): string {
    return text
      .toLowerCase()
      // Remove URLs
      .replace(/https?:\/\/\S+/g, '')
      // Remove mentions but keep @ indicator
      .replace(/@(\w+)/g, 'user_$1')
      // Keep cashtags
      .replace(/\$([a-zA-Z]+)/g, 'token_$1')
      // Remove extra whitespace
      .replace(/\s+/g, ' ')
      .trim();
  }
  
  /**
   * Find matching patterns in text
   */
  private findPatterns(text: string, patterns: RegExp[]): string[] {
    const matches: string[] = [];
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match) {
        matches.push(match[0]);
      }
    }
    return matches;
  }
}

export const sentimentAnalyzer = new SentimentAnalyzer();
