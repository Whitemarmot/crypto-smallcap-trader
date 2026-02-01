/**
 * Jupiter DEX Integration
 * Uses @jup-ag/api for swap aggregation on Solana
 */

import { createJupiterApiClient, QuoteResponse, SwapResponse } from '@jup-ag/api';
import { 
  Connection, 
  Keypair, 
  VersionedTransaction,
  TransactionMessage,
  AddressLookupTableAccount,
  PublicKey,
  SendTransactionError,
} from '@solana/web3.js';
import { SwapParams, SwapQuote, SwapResult, TradingConfig, TOKENS } from '../types/index.js';
import { logger, txLogger } from '../logger/index.js';

const DEFAULT_CONFIG: TradingConfig = {
  rpcEndpoint: 'https://api.mainnet-beta.solana.com',
  defaultSlippageBps: 50, // 0.5%
  maxSlippageBps: 500, // 5%
  priorityFeeLamports: 10000, // 0.00001 SOL
  maxRetries: 3,
  retryDelayMs: 1000,
  confirmationTimeout: 60000, // 60 seconds
};

export class JupiterClient {
  private jupiter: ReturnType<typeof createJupiterApiClient>;
  private connection: Connection;
  private config: TradingConfig;

  constructor(config: Partial<TradingConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.connection = new Connection(this.config.rpcEndpoint, 'confirmed');
    this.jupiter = createJupiterApiClient();
    
    logger.info('Jupiter client initialized', {
      rpcEndpoint: this.config.rpcEndpoint,
      defaultSlippageBps: this.config.defaultSlippageBps,
    });
  }

  /**
   * Get a swap quote from Jupiter
   */
  async getQuote(params: SwapParams): Promise<SwapQuote> {
    const { inputMint, outputMint, amount, slippageBps } = params;
    
    const effectiveSlippage = Math.min(
      slippageBps || this.config.defaultSlippageBps,
      this.config.maxSlippageBps
    );

    logger.debug('Requesting quote', {
      inputMint,
      outputMint,
      amount: amount.toString(),
      slippageBps: effectiveSlippage,
    });

    try {
      const quoteResponse = await this.jupiter.quoteGet({
        inputMint,
        outputMint,
        amount: Number(amount),
        slippageBps: effectiveSlippage,
        onlyDirectRoutes: false,
        asLegacyTransaction: false,
      });

      if (!quoteResponse) {
        throw new Error('No quote returned from Jupiter');
      }

      const quote = this.parseQuoteResponse(quoteResponse);
      
      txLogger.logQuote({
        inputMint,
        outputMint,
        inAmount: quote.inAmount,
        outAmount: quote.outAmount,
        priceImpactPct: quote.priceImpactPct,
        routes: quote.routePlan.length,
      });

      return quote;
    } catch (error) {
      txLogger.logError('getQuote', error as Error, { inputMint, outputMint, amount: amount.toString() });
      throw error;
    }
  }

  /**
   * Execute a swap transaction
   */
  async executeSwap(
    params: SwapParams,
    wallet: Keypair
  ): Promise<SwapResult> {
    const startTime = Date.now();
    
    try {
      // Step 1: Get quote
      logger.info('Getting swap quote...');
      const quote = await this.getQuote(params);

      // Check price impact
      if (quote.priceImpactPct > 5) {
        logger.warn('High price impact detected', { priceImpactPct: quote.priceImpactPct });
      }

      // Step 2: Get swap transaction
      logger.info('Building swap transaction...');
      const swapResponse = await this.jupiter.swapPost({
        swapRequest: {
          quoteResponse: await this.jupiter.quoteGet({
            inputMint: params.inputMint,
            outputMint: params.outputMint,
            amount: Number(params.amount),
            slippageBps: params.slippageBps || this.config.defaultSlippageBps,
          }) as QuoteResponse,
          userPublicKey: wallet.publicKey.toBase58(),
          wrapAndUnwrapSol: true,
          dynamicComputeUnitLimit: true,
          prioritizationFeeLamports: this.config.priorityFeeLamports,
        },
      });

      if (!swapResponse?.swapTransaction) {
        throw new Error('No swap transaction returned');
      }

      // Step 3: Deserialize and sign transaction
      logger.info('Signing transaction...');
      const swapTransactionBuf = Buffer.from(swapResponse.swapTransaction, 'base64');
      const transaction = VersionedTransaction.deserialize(swapTransactionBuf);
      transaction.sign([wallet]);

      // Step 4: Send transaction
      logger.info('Sending transaction...');
      const signature = await this.sendAndConfirmTransaction(transaction);

      const result: SwapResult = {
        success: true,
        signature,
        inputAmount: quote.inAmount,
        outputAmount: quote.outAmount,
        inputMint: params.inputMint,
        outputMint: params.outputMint,
        priceImpactPct: quote.priceImpactPct,
        timestamp: new Date(),
      };

      logger.info('Swap executed successfully', {
        signature,
        duration: Date.now() - startTime,
        ...result,
      });

      return result;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      txLogger.logError('executeSwap', error as Error, {
        inputMint: params.inputMint,
        outputMint: params.outputMint,
        amount: params.amount.toString(),
      });

      return {
        success: false,
        inputAmount: params.amount.toString(),
        outputAmount: '0',
        inputMint: params.inputMint,
        outputMint: params.outputMint,
        priceImpactPct: 0,
        error: errorMessage,
        timestamp: new Date(),
      };
    }
  }

  /**
   * Send and confirm a transaction with retries
   */
  private async sendAndConfirmTransaction(
    transaction: VersionedTransaction
  ): Promise<string> {
    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= this.config.maxRetries; attempt++) {
      try {
        logger.debug(`Transaction attempt ${attempt}/${this.config.maxRetries}`);

        const rawTransaction = transaction.serialize();
        const signature = await this.connection.sendRawTransaction(rawTransaction, {
          skipPreflight: false,
          preflightCommitment: 'confirmed',
          maxRetries: 2,
        });

        logger.info('Transaction sent', { signature, attempt });

        // Wait for confirmation
        const confirmation = await this.connection.confirmTransaction(
          {
            signature,
            blockhash: transaction.message.recentBlockhash,
            lastValidBlockHeight: (await this.connection.getLatestBlockhash()).lastValidBlockHeight,
          },
          'confirmed'
        );

        if (confirmation.value.err) {
          throw new Error(`Transaction failed: ${JSON.stringify(confirmation.value.err)}`);
        }

        logger.info('Transaction confirmed', { signature });
        return signature;
      } catch (error) {
        lastError = error as Error;
        
        if (error instanceof SendTransactionError) {
          logger.warn(`Transaction attempt ${attempt} failed`, {
            error: error.message,
            logs: error.logs,
          });
        } else {
          logger.warn(`Transaction attempt ${attempt} failed`, {
            error: (error as Error).message,
          });
        }

        if (attempt < this.config.maxRetries) {
          await this.delay(this.config.retryDelayMs * attempt);
        }
      }
    }

    throw lastError || new Error('Transaction failed after all retries');
  }

  /**
   * Get token balance for a wallet
   */
  async getTokenBalance(walletAddress: string, tokenMint: string): Promise<bigint> {
    try {
      const walletPubkey = new PublicKey(walletAddress);
      
      // Handle SOL balance
      if (tokenMint === TOKENS.SOL) {
        const balance = await this.connection.getBalance(walletPubkey);
        return BigInt(balance);
      }

      // Handle SPL token balance
      const tokenMintPubkey = new PublicKey(tokenMint);
      const tokenAccounts = await this.connection.getTokenAccountsByOwner(
        walletPubkey,
        { mint: tokenMintPubkey }
      );

      if (tokenAccounts.value.length === 0) {
        return BigInt(0);
      }

      // Parse the account data to get balance
      const accountInfo = tokenAccounts.value[0].account;
      const data = accountInfo.data;
      // Token amount is stored at offset 64, as a u64
      const amount = data.readBigUInt64LE(64);
      
      return amount;
    } catch (error) {
      logger.error('Error getting token balance', {
        walletAddress,
        tokenMint,
        error: (error as Error).message,
      });
      return BigInt(0);
    }
  }

  /**
   * Parse Jupiter quote response to our format
   */
  private parseQuoteResponse(response: QuoteResponse): SwapQuote {
    return {
      inputMint: response.inputMint,
      outputMint: response.outputMint,
      inAmount: response.inAmount,
      outAmount: response.outAmount,
      priceImpactPct: parseFloat(response.priceImpactPct || '0'),
      slippageBps: response.slippageBps,
      routePlan: response.routePlan.map(step => ({
        ammKey: step.swapInfo.ammKey,
        label: step.swapInfo.label || 'Unknown',
        inputMint: step.swapInfo.inputMint,
        outputMint: step.swapInfo.outputMint,
        inAmount: step.swapInfo.inAmount,
        outAmount: step.swapInfo.outAmount,
        feeAmount: step.swapInfo.feeAmount,
        feeMint: step.swapInfo.feeMint,
      })),
      estimatedFeesSol: 0.000005, // Approximate, actual fees depend on transaction
    };
  }

  /**
   * Helper to delay execution
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Get connection instance (for external use)
   */
  getConnection(): Connection {
    return this.connection;
  }

  /**
   * Update RPC endpoint
   */
  setRpcEndpoint(endpoint: string): void {
    this.config.rpcEndpoint = endpoint;
    this.connection = new Connection(endpoint, 'confirmed');
    logger.info('RPC endpoint updated', { endpoint });
  }
}
