import type { SocialSignal, OnChainData, Portfolio, DecisionAction, ConfidenceLevel } from './types.js';

export interface RuleResult {
  triggered: boolean;
  action: DecisionAction;
  confidence: number;
  reason: string;
  ruleName: string;
}

export interface RuleContext {
  socialSignal: SocialSignal;
  onChainData: OnChainData;
  portfolio: Portfolio;
}

export type TradingRule = (context: RuleContext) => RuleResult | null;

// ============================================================================
// BUY Rules
// ============================================================================

/**
 * Strong positive sentiment with rising trend
 */
export const strongSentimentBuy: TradingRule = ({ socialSignal, onChainData }) => {
  if (
    socialSignal.sentimentScore > 0.6 &&
    socialSignal.trendDirection === 'rising' &&
    onChainData.priceChange24h < 50 // Not already pumped too much
  ) {
    return {
      triggered: true,
      action: 'BUY',
      confidence: 0.7 + socialSignal.sentimentScore * 0.2,
      reason: `Strong bullish sentiment (${(socialSignal.sentimentScore * 100).toFixed(0)}%) with rising trend`,
      ruleName: 'STRONG_SENTIMENT_BUY',
    };
  }
  return null;
};

/**
 * Influencer mentions with volume confirmation
 */
export const influencerMentionBuy: TradingRule = ({ socialSignal, onChainData }) => {
  if (
    socialSignal.influencerMentions >= 2 &&
    socialSignal.sentimentScore > 0.3 &&
    onChainData.volumeChange24h > 50 &&
    onChainData.buyCount24h > onChainData.sellCount24h
  ) {
    return {
      triggered: true,
      action: 'BUY',
      confidence: 0.65 + Math.min(socialSignal.influencerMentions * 0.05, 0.2),
      reason: `${socialSignal.influencerMentions} influencer mentions with ${onChainData.volumeChange24h.toFixed(0)}% volume increase`,
      ruleName: 'INFLUENCER_MENTION_BUY',
    };
  }
  return null;
};

/**
 * Volume spike with positive sentiment (potential breakout)
 */
export const volumeBreakoutBuy: TradingRule = ({ socialSignal, onChainData }) => {
  if (
    onChainData.volumeChange24h > 200 &&
    onChainData.buyCount24h > onChainData.sellCount24h * 1.5 &&
    socialSignal.sentimentScore > 0.2 &&
    onChainData.holderChange24h > 0
  ) {
    return {
      triggered: true,
      action: 'BUY',
      confidence: 0.6,
      reason: `Volume breakout (${onChainData.volumeChange24h.toFixed(0)}%) with positive buy pressure`,
      ruleName: 'VOLUME_BREAKOUT_BUY',
    };
  }
  return null;
};

/**
 * Accumulation pattern: steady holder increase, low price volatility
 */
export const accumulationBuy: TradingRule = ({ socialSignal, onChainData }) => {
  if (
    onChainData.holderChange24h > 5 &&
    Math.abs(onChainData.priceChange24h) < 10 &&
    onChainData.liquidityChange24h > 0 &&
    socialSignal.sentimentScore > 0 &&
    socialSignal.trendDirection !== 'falling'
  ) {
    return {
      triggered: true,
      action: 'BUY',
      confidence: 0.55,
      reason: `Accumulation pattern: ${onChainData.holderChange24h.toFixed(1)}% holder increase with stable price`,
      ruleName: 'ACCUMULATION_BUY',
    };
  }
  return null;
};

// ============================================================================
// SELL Rules
// ============================================================================

/**
 * Strong negative sentiment with falling trend
 */
export const strongSentimentSell: TradingRule = ({ socialSignal, portfolio, onChainData }) => {
  const hasPosition = portfolio.positions.some(
    (p) => p.tokenAddress === onChainData.tokenAddress
  );

  if (
    hasPosition &&
    socialSignal.sentimentScore < -0.5 &&
    socialSignal.trendDirection === 'falling'
  ) {
    return {
      triggered: true,
      action: 'SELL',
      confidence: 0.7 + Math.abs(socialSignal.sentimentScore) * 0.2,
      reason: `Strong bearish sentiment (${(socialSignal.sentimentScore * 100).toFixed(0)}%) with falling trend`,
      ruleName: 'STRONG_SENTIMENT_SELL',
    };
  }
  return null;
};

/**
 * Liquidity drain - major red flag
 */
export const liquidityDrainSell: TradingRule = ({ onChainData, portfolio }) => {
  const hasPosition = portfolio.positions.some(
    (p) => p.tokenAddress === onChainData.tokenAddress
  );

  if (hasPosition && onChainData.liquidityChange24h < -30) {
    return {
      triggered: true,
      action: 'SELL',
      confidence: 0.9,
      reason: `Liquidity drain detected: ${onChainData.liquidityChange24h.toFixed(1)}% decrease`,
      ruleName: 'LIQUIDITY_DRAIN_SELL',
    };
  }
  return null;
};

/**
 * Whale dump - high concentration holders selling
 */
export const whaleDumpSell: TradingRule = ({ onChainData, portfolio }) => {
  const hasPosition = portfolio.positions.some(
    (p) => p.tokenAddress === onChainData.tokenAddress
  );

  if (
    hasPosition &&
    onChainData.sellCount24h > onChainData.buyCount24h * 2 &&
    onChainData.priceChange24h < -20 &&
    onChainData.volumeChange24h > 100
  ) {
    return {
      triggered: true,
      action: 'SELL',
      confidence: 0.85,
      reason: `Potential whale dump: sells 2x buys with ${onChainData.priceChange24h.toFixed(1)}% price drop`,
      ruleName: 'WHALE_DUMP_SELL',
    };
  }
  return null;
};

/**
 * Holder exodus - people leaving
 */
export const holderExodusSell: TradingRule = ({ onChainData, portfolio }) => {
  const hasPosition = portfolio.positions.some(
    (p) => p.tokenAddress === onChainData.tokenAddress
  );

  if (hasPosition && onChainData.holderChange24h < -10) {
    return {
      triggered: true,
      action: 'SELL',
      confidence: 0.75,
      reason: `Holder exodus: ${onChainData.holderChange24h.toFixed(1)}% decrease in holders`,
      ruleName: 'HOLDER_EXODUS_SELL',
    };
  }
  return null;
};

// ============================================================================
// HOLD Rules (explicit hold signals)
// ============================================================================

/**
 * Uncertain conditions - wait for clarity
 */
export const uncertainHold: TradingRule = ({ socialSignal, onChainData }) => {
  const sentimentNeutral = Math.abs(socialSignal.sentimentScore) < 0.2;
  const priceStable = Math.abs(onChainData.priceChange24h) < 5;
  const volumeNormal = Math.abs(onChainData.volumeChange24h) < 50;

  if (sentimentNeutral && priceStable && volumeNormal) {
    return {
      triggered: true,
      action: 'HOLD',
      confidence: 0.6,
      reason: 'Market conditions unclear - no strong signals',
      ruleName: 'UNCERTAIN_HOLD',
    };
  }
  return null;
};

/**
 * Conflicting signals - wait for resolution
 */
export const conflictingSignalsHold: TradingRule = ({ socialSignal, onChainData }) => {
  const sentimentBullish = socialSignal.sentimentScore > 0.3;
  const priceBearish = onChainData.priceChange24h < -10;
  
  const sentimentBearish = socialSignal.sentimentScore < -0.3;
  const priceBullish = onChainData.priceChange24h > 10;

  if ((sentimentBullish && priceBearish) || (sentimentBearish && priceBullish)) {
    return {
      triggered: true,
      action: 'HOLD',
      confidence: 0.5,
      reason: 'Conflicting signals between sentiment and price action',
      ruleName: 'CONFLICTING_SIGNALS_HOLD',
    };
  }
  return null;
};

// ============================================================================
// Rule Engine
// ============================================================================

export const ALL_RULES: TradingRule[] = [
  // Critical sell rules (check first)
  liquidityDrainSell,
  whaleDumpSell,
  holderExodusSell,
  strongSentimentSell,
  
  // Buy rules
  strongSentimentBuy,
  influencerMentionBuy,
  volumeBreakoutBuy,
  accumulationBuy,
  
  // Hold rules (fallback)
  conflictingSignalsHold,
  uncertainHold,
];

export interface RulesEngineResult {
  suggestedAction: DecisionAction;
  confidence: number;
  confidenceLevel: ConfidenceLevel;
  triggeredRules: RuleResult[];
  reasoning: string[];
}

export function evaluateRules(context: RuleContext): RulesEngineResult {
  const triggeredRules: RuleResult[] = [];

  for (const rule of ALL_RULES) {
    const result = rule(context);
    if (result?.triggered) {
      triggeredRules.push(result);
    }
  }

  // If no rules triggered, default to HOLD
  if (triggeredRules.length === 0) {
    return {
      suggestedAction: 'HOLD',
      confidence: 0.3,
      confidenceLevel: 'LOW',
      triggeredRules: [],
      reasoning: ['No trading rules triggered - defaulting to HOLD'],
    };
  }

  // Prioritize by action type: SELL (safety) > BUY > HOLD
  const sellRules = triggeredRules.filter((r) => r.action === 'SELL');
  const buyRules = triggeredRules.filter((r) => r.action === 'BUY');
  const holdRules = triggeredRules.filter((r) => r.action === 'HOLD');

  let selectedRules: RuleResult[];
  let action: DecisionAction;

  if (sellRules.length > 0) {
    // Safety first - if any sell signal, prioritize it
    selectedRules = sellRules;
    action = 'SELL';
  } else if (buyRules.length > 0 && holdRules.length === 0) {
    selectedRules = buyRules;
    action = 'BUY';
  } else if (holdRules.length > 0) {
    selectedRules = holdRules;
    action = 'HOLD';
  } else {
    selectedRules = buyRules;
    action = 'BUY';
  }

  // Average confidence from selected rules
  const avgConfidence =
    selectedRules.reduce((sum, r) => sum + r.confidence, 0) / selectedRules.length;

  // Determine confidence level
  let confidenceLevel: ConfidenceLevel;
  if (avgConfidence >= 0.85) {
    confidenceLevel = 'VERY_HIGH';
  } else if (avgConfidence >= 0.7) {
    confidenceLevel = 'HIGH';
  } else if (avgConfidence >= 0.5) {
    confidenceLevel = 'MEDIUM';
  } else {
    confidenceLevel = 'LOW';
  }

  return {
    suggestedAction: action,
    confidence: avgConfidence,
    confidenceLevel,
    triggeredRules,
    reasoning: selectedRules.map((r) => r.reason),
  };
}
