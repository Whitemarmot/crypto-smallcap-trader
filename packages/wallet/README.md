# @crypto-trader/wallet

Solana wallet management module for crypto-smallcap-trader.

## Features

- 🔐 Generate new Solana wallets
- 🔒 Securely encrypt and store private keys (AES-256-GCM)
- 💰 Retrieve SOL and SPL token balances
- 📊 List all token positions

## Installation

```bash
npm install @crypto-trader/wallet
# or
yarn add @crypto-trader/wallet
```

## Usage

### Generate a New Wallet

```typescript
import { createAndSaveWallet, loadWallet } from '@crypto-trader/wallet';

// Create a new wallet and save it encrypted
const publicKey = createAndSaveWallet('my-secure-password', './my-wallet.json');
console.log('Wallet created:', publicKey);

// Load the wallet later
const wallet = loadWallet('./my-wallet.json', 'my-secure-password');
console.log('Loaded wallet:', wallet.publicKey);
```

### Check Balances

```typescript
import { getPosition, createConnection, getSolBalance } from '@crypto-trader/wallet';

// Quick way - get everything at once
const position = await getPosition('YOUR_PUBLIC_KEY', 'mainnet-beta');
console.log('SOL Balance:', position.sol.sol);
console.log('Tokens:', position.tokens);

// Or more granular control
const connection = createConnection('devnet');
const solBalance = await getSolBalance(connection, 'YOUR_PUBLIC_KEY');
console.log('SOL:', solBalance.sol);
```

### Import an Existing Wallet

```typescript
import { importWallet } from '@crypto-trader/wallet';

// From a secret key (e.g., exported from Phantom)
const secretKey = [/* your 64-byte secret key array */];
const publicKey = importWallet(secretKey, 'my-password', './imported-wallet.json');
```

### Get Token Balances

```typescript
import { createConnection, getTokenBalances, getTokenBalance } from '@crypto-trader/wallet';

const connection = createConnection('mainnet-beta');

// Get all tokens
const tokens = await getTokenBalances(connection, 'YOUR_PUBLIC_KEY');
for (const token of tokens) {
  console.log(`${token.mint}: ${token.uiAmount}`);
}

// Get specific token
const usdc = await getTokenBalance(
  connection,
  'YOUR_PUBLIC_KEY',
  'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v' // USDC mint
);
```

## API Reference

### Wallet Management

| Function | Description |
|----------|-------------|
| `generateWallet()` | Generate a new Solana Keypair |
| `createAndSaveWallet(password, filePath?)` | Create and save an encrypted wallet |
| `loadWallet(filePath, password)` | Load and decrypt a wallet |
| `importWallet(secretKey, password, filePath?)` | Import from existing secret key |
| `encryptWallet(keypair, password)` | Encrypt a keypair |
| `decryptWallet(encrypted, password)` | Decrypt wallet data |

### Balance Functions

| Function | Description |
|----------|-------------|
| `createConnection(cluster?, rpcUrl?)` | Create a Solana connection |
| `getSolBalance(connection, publicKey)` | Get SOL balance |
| `getTokenBalances(connection, publicKey)` | Get all SPL token balances |
| `getTokenBalance(connection, publicKey, mint)` | Get specific token balance |
| `getWalletPosition(connection, publicKey)` | Get complete position (SOL + tokens) |
| `getPosition(publicKey, cluster?, rpcUrl?)` | Quick position check |

## Security

- Private keys are encrypted using **AES-256-GCM**
- Key derivation uses **PBKDF2** with SHA-512 (100,000 iterations)
- Each wallet has a unique random salt and IV
- Authentication tag prevents tampering

⚠️ **Important:** Store your password securely. Without it, encrypted wallets cannot be recovered.

## Types

```typescript
interface WalletPosition {
  publicKey: string;
  sol: { lamports: number; sol: number };
  tokens: TokenBalance[];
}

interface TokenBalance {
  mint: string;
  tokenAccount: string;
  amount: bigint;
  decimals: number;
  uiAmount: number;
}

type Cluster = 'mainnet-beta' | 'devnet' | 'testnet';
```

## License

MIT
