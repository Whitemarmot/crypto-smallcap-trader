/**
 * @crypto-trader/wallet
 * 
 * Solana wallet management module for crypto-smallcap-trader
 * 
 * Features:
 * - Generate new Solana wallets
 * - Encrypt and securely store private keys
 * - Retrieve SOL and SPL token balances
 * - List all token positions
 */

// Types
export * from './types';

// Wallet management
export {
  generateWallet,
  createAndSaveWallet,
  encryptWallet,
  loadEncryptedWallet,
  decryptWallet,
  loadWallet,
  getKeypair,
  importWallet,
} from './wallet';

// Crypto utilities
export {
  encrypt,
  decrypt,
  generateSecurePassword,
} from './crypto';

// Balance and positions
export {
  createConnection,
  getSolBalance,
  getTokenBalances,
  getTokenBalance,
  getWalletPosition,
  getPosition,
} from './balance';

// Re-export useful types from Solana
export { Keypair, PublicKey, Connection } from '@solana/web3.js';
