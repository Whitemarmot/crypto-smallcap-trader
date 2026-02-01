import {
  type RiskConfig,
  type Portfolio,
  type OnChainData,
  type Decision,
  type DecisionAction,
  RiskConfigSchema,
} from './types.js';

export interface RiskAssessment {
  canTrade: boolean;
  maxPositionSizeUSD: number;
  maxPositionSizePercent: number;
  suggestedStopLoss: number;
  suggestedTakeProfit: number;
  riskScore: number; // 0-1, higher = riskier
  warnings: string[];
  blockers: string[];
}

export class RiskManager {
  private config: RiskConfig;

  constructor(config?: Partial<RiskConfig>) {
    this.config = RiskConfigSchema.parse(config ?? {});
  }

  /**
   * Assess the risk of a potential trade
   */
  assessRisk(
    action: DecisionAction,
    onChainData: OnChainData,
    portfolio: Portfolio
  ): RiskAssessment {
    const warnings: string[] = [];
    const blockers: string[] = [];
    let riskScore = 0;

    // Check daily loss limit
    if (portfolio.dailyPnLPercent <= -this.config.dailyLossLimitPercent) {
      blockers.push(`Daily loss limit reached (${portfolio.dailyPnLPercent.toFixed(2)}%)`);
    }

    // Check liquidity
    if (onChainData.liquidityUSD < this.config.minLiquidityUSD) {
      blockers.push(
        `Insufficient liquidity: $${onChainData.liquidityUSD.toFixed(0)} < $${this.config.minLiquidityUSD}`
      );
      riskScore += 0.3;
    }

    // Check holder concentration
    if (onChainData.top10HoldersPercent > 80) {
      blockers.push(`Extreme holder concentration: top 10 hold ${onChainData.top10HoldersPercent}%`);
      riskScore += 0.3;
    } else if (onChainData.top10HoldersPercent > 60) {
      warnings.push(`High holder concentration: top 10 hold ${onChainData.top10HoldersPercent}%`);
      riskScore += 0.15;
    }

    // Check if we already have a position
    const existingPosition = portfolio.positions.find(
      (p) => p.tokenAddress === onChainData.tokenAddress
    );

    if (action === 'BUY') {
      // Check max positions
      if (portfolio.positions.length >= portfolio.maxPositions && !existingPosition) {
        blockers.push(`Max positions reached (${portfolio.maxPositions})`);
      }

      // Check total exposure
      const currentExposure =
        ((portfolio.totalValueUSD - portfolio.availableCashUSD) / portfolio.totalValueUSD) * 100;
      if (currentExposure >= this.config.maxTotalExposurePercent) {
        blockers.push(`Max exposure reached (${currentExposure.toFixed(1)}%)`);
      }

      // Check buy/sell ratio (potential dump)
      const buySellRatio =
        onChainData.sellCount24h > 0
          ? onChainData.buyCount24h / onChainData.sellCount24h
          : onChainData.buyCount24h;
      if (buySellRatio < 0.5) {
        warnings.push(`Unfavorable buy/sell ratio: ${buySellRatio.toFixed(2)}`);
        riskScore += 0.1;
      }

      // Check for pump (might be followed by dump)
      if (onChainData.priceChange24h > 100) {
        warnings.push(`Significant price increase (${onChainData.priceChange24h.toFixed(0)}%) - potential pump`);
        riskScore += 0.2;
      }

      // Volume spike check
      if (onChainData.volumeChange24h > 500) {
        warnings.push(`Abnormal volume spike (${onChainData.volumeChange24h.toFixed(0)}%)`);
        riskScore += 0.1;
      }
    }

    if (action === 'SELL' && !existingPosition) {
      blockers.push('No position to sell');
    }

    // Calculate max position size
    const maxByPortfolioPercent =
      (portfolio.totalValueUSD * this.config.maxPositionSizePercent) / 100;
    const maxByCash = portfolio.availableCashUSD;
    const maxByLiquidity = onChainData.liquidityUSD * 0.02; // Max 2% of liquidity
    
    let maxPositionSizeUSD = Math.min(maxByPortfolioPercent, maxByCash, maxByLiquidity);
    
    // Reduce position size based on risk
    if (riskScore > 0.3) {
      maxPositionSizeUSD *= 0.5;
      warnings.push('Position size reduced due to elevated risk');
    }

    const maxPositionSizePercent = (maxPositionSizeUSD / portfolio.totalValueUSD) * 100;

    // Calculate stop loss and take profit
    const volatilityMultiplier = Math.min(2, 1 + Math.abs(onChainData.priceChange24h) / 100);
    const suggestedStopLoss = this.config.stopLossPercent * volatilityMultiplier;
    const suggestedTakeProfit = this.config.takeProfitPercent;

    return {
      canTrade: blockers.length === 0,
      maxPositionSizeUSD,
      maxPositionSizePercent,
      suggestedStopLoss,
      suggestedTakeProfit,
      riskScore: Math.min(1, riskScore),
      warnings,
      blockers,
    };
  }

  /**
   * Calculate optimal position size using Kelly Criterion variant
   */
  calculatePositionSize(
    confidence: number,
    portfolio: Portfolio,
    riskAssessment: RiskAssessment
  ): { percent: number; amountUSD: number } {
    // Modified Kelly: f = (bp - q) / b
    // where b = win/loss ratio, p = win probability, q = 1-p
    const winProbability = 0.5 + confidence * 0.3; // confidence shifts win probability
    const avgWin = this.config.takeProfitPercent / 100;
    const avgLoss = this.config.stopLossPercent / 100;
    const b = avgWin / avgLoss;

    let kellyFraction = (b * winProbability - (1 - winProbability)) / b;
    kellyFraction = Math.max(0, kellyFraction);

    // Use half-Kelly for safety
    const halfKelly = kellyFraction / 2;

    // Apply constraints
    const maxPercent = Math.min(
      halfKelly * 100,
      riskAssessment.maxPositionSizePercent,
      this.config.maxPositionSizePercent
    );

    const percent = Math.max(0, maxPercent);
    const amountUSD = (portfolio.totalValueUSD * percent) / 100;

    return { percent, amountUSD };
  }

  /**
   * Check if existing position should be closed due to stop loss or take profit
   */
  checkExitConditions(portfolio: Portfolio): Decision[] {
    const exitDecisions: Decision[] = [];
    const now = Date.now();

    for (const position of portfolio.positions) {
      const shouldExit =
        position.unrealizedPnLPercent <= -this.config.stopLossPercent ||
        position.unrealizedPnLPercent >= this.config.takeProfitPercent;

      if (shouldExit) {
        const isStopLoss = position.unrealizedPnLPercent < 0;
        
        exitDecisions.push({
          tokenAddress: position.tokenAddress,
          tokenSymbol: position.tokenSymbol,
          action: 'SELL',
          confidence: 'VERY_HIGH',
          confidenceScore: 1,
          suggestedPositionPercent: 100, // Sell entire position
          reasoning: [
            isStopLoss
              ? `Stop loss triggered at ${position.unrealizedPnLPercent.toFixed(2)}%`
              : `Take profit triggered at ${position.unrealizedPnLPercent.toFixed(2)}%`,
          ],
          rulesTriggers: [isStopLoss ? 'STOP_LOSS' : 'TAKE_PROFIT'],
          timestamp: now,
          priority: 'URGENT',
        });
      }
    }

    return exitDecisions;
  }

  /**
   * Update config at runtime
   */
  updateConfig(newConfig: Partial<RiskConfig>): void {
    this.config = RiskConfigSchema.parse({ ...this.config, ...newConfig });
  }

  getConfig(): RiskConfig {
    return { ...this.config };
  }
}
