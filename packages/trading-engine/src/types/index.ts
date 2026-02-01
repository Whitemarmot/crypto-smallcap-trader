/**
 * Trading Engine Types
 */

export interface TokenInfo {
  address: string;
  symbol: string;
  decimals: number;
  name?: string;
}

export interface SwapParams {
  inputMint: string;
  outputMint: string;
  amount: bigint;
  slippageBps: number;
  userPublicKey: string;
}

export interface SwapQuote {
  inputMint: string;
  outputMint: string;
  inAmount: string;
  outAmount: string;
  priceImpactPct: number;
  slippageBps: number;
  routePlan: RoutePlanStep[];
  estimatedFeesSol: number;
}

export interface RoutePlanStep {
  ammKey: string;
  label: string;
  inputMint: string;
  outputMint: string;
  inAmount: string;
  outAmount: string;
  feeAmount: string;
  feeMint: string;
}

export interface SwapResult {
  success: boolean;
  signature?: string;
  inputAmount: string;
  outputAmount: string;
  inputMint: string;
  outputMint: string;
  priceImpactPct: number;
  error?: string;
  timestamp: Date;
}

export interface TradeOrder {
  id: string;
  type: 'buy' | 'sell';
  inputMint: string;
  outputMint: string;
  amount: bigint;
  slippageBps: number;
  maxRetries: number;
  status: OrderStatus;
  createdAt: Date;
  executedAt?: Date;
  result?: SwapResult;
}

export type OrderStatus = 'pending' | 'executing' | 'completed' | 'failed' | 'cancelled';

export interface TradingConfig {
  rpcEndpoint: string;
  defaultSlippageBps: number;
  maxSlippageBps: number;
  priorityFeeLamports: number;
  maxRetries: number;
  retryDelayMs: number;
  confirmationTimeout: number;
}

export interface TransactionLog {
  id: string;
  orderId: string;
  signature: string;
  type: 'swap';
  inputMint: string;
  outputMint: string;
  inputAmount: string;
  outputAmount: string;
  priceImpactPct: number;
  feesSol: number;
  status: 'pending' | 'confirmed' | 'failed';
  blockTime?: number;
  slot?: number;
  error?: string;
  createdAt: Date;
  confirmedAt?: Date;
}

export interface BalanceInfo {
  mint: string;
  amount: bigint;
  decimals: number;
  uiAmount: number;
}

// Common Solana token addresses
export const TOKENS = {
  SOL: 'So11111111111111111111111111111111111111112',
  USDC: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
  USDT: 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
  RAY: '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R',
  BONK: 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
} as const;

export type TokenSymbol = keyof typeof TOKENS;
