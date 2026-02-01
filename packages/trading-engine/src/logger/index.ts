/**
 * Trading Engine Logger
 * Centralized logging for all trading operations
 */

import winston from 'winston';
import { TransactionLog, SwapResult, TradeOrder } from '../types/index.js';

const { combine, timestamp, printf, colorize, json } = winston.format;

// Custom format for console output
const consoleFormat = printf(({ level, message, timestamp, ...meta }) => {
  const metaStr = Object.keys(meta).length ? JSON.stringify(meta, null, 2) : '';
  return `${timestamp} [${level}] ${message} ${metaStr}`;
});

// Create logger instance
export const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: combine(
    timestamp({ format: 'YYYY-MM-DD HH:mm:ss.SSS' }),
    json()
  ),
  defaultMeta: { service: 'trading-engine' },
  transports: [
    // Console transport with colors for development
    new winston.transports.Console({
      format: combine(
        colorize(),
        timestamp({ format: 'YYYY-MM-DD HH:mm:ss.SSS' }),
        consoleFormat
      ),
    }),
    // File transport for all logs
    new winston.transports.File({
      filename: 'logs/trading-engine.log',
      maxsize: 10 * 1024 * 1024, // 10MB
      maxFiles: 5,
    }),
    // Separate file for errors
    new winston.transports.File({
      filename: 'logs/trading-engine-error.log',
      level: 'error',
      maxsize: 10 * 1024 * 1024,
      maxFiles: 5,
    }),
    // Separate file for transactions
    new winston.transports.File({
      filename: 'logs/transactions.log',
      maxsize: 50 * 1024 * 1024, // 50MB for transaction history
      maxFiles: 10,
    }),
  ],
});

/**
 * Transaction Logger - specialized logging for trades
 */
export class TransactionLogger {
  private logs: TransactionLog[] = [];

  /**
   * Log a new transaction
   */
  logTransaction(log: TransactionLog): void {
    this.logs.push(log);
    
    logger.info('Transaction logged', {
      transactionId: log.id,
      orderId: log.orderId,
      signature: log.signature,
      type: log.type,
      inputMint: log.inputMint,
      outputMint: log.outputMint,
      inputAmount: log.inputAmount,
      outputAmount: log.outputAmount,
      priceImpactPct: log.priceImpactPct,
      status: log.status,
    });
  }

  /**
   * Update transaction status
   */
  updateTransactionStatus(
    id: string, 
    status: TransactionLog['status'], 
    extra?: Partial<TransactionLog>
  ): void {
    const log = this.logs.find(l => l.id === id);
    if (log) {
      log.status = status;
      if (extra) {
        Object.assign(log, extra);
      }
      
      logger.info('Transaction status updated', {
        transactionId: id,
        status,
        ...extra,
      });
    }
  }

  /**
   * Log swap execution start
   */
  logSwapStart(order: TradeOrder): void {
    logger.info('Swap execution started', {
      orderId: order.id,
      type: order.type,
      inputMint: order.inputMint,
      outputMint: order.outputMint,
      amount: order.amount.toString(),
      slippageBps: order.slippageBps,
    });
  }

  /**
   * Log swap result
   */
  logSwapResult(orderId: string, result: SwapResult): void {
    const logLevel = result.success ? 'info' : 'error';
    
    logger[logLevel]('Swap execution completed', {
      orderId,
      success: result.success,
      signature: result.signature,
      inputAmount: result.inputAmount,
      outputAmount: result.outputAmount,
      priceImpactPct: result.priceImpactPct,
      error: result.error,
      timestamp: result.timestamp,
    });
  }

  /**
   * Log quote received
   */
  logQuote(params: {
    inputMint: string;
    outputMint: string;
    inAmount: string;
    outAmount: string;
    priceImpactPct: number;
    routes: number;
  }): void {
    logger.debug('Quote received', params);
  }

  /**
   * Log error with context
   */
  logError(context: string, error: Error, meta?: Record<string, unknown>): void {
    logger.error(`Error in ${context}`, {
      error: error.message,
      stack: error.stack,
      ...meta,
    });
  }

  /**
   * Get all transaction logs
   */
  getTransactionLogs(): TransactionLog[] {
    return [...this.logs];
  }

  /**
   * Get transactions by status
   */
  getTransactionsByStatus(status: TransactionLog['status']): TransactionLog[] {
    return this.logs.filter(l => l.status === status);
  }

  /**
   * Get transactions for an order
   */
  getTransactionsByOrderId(orderId: string): TransactionLog[] {
    return this.logs.filter(l => l.orderId === orderId);
  }

  /**
   * Export logs to JSON
   */
  exportLogs(): string {
    return JSON.stringify(this.logs, null, 2);
  }
}

// Singleton instance
export const txLogger = new TransactionLogger();
