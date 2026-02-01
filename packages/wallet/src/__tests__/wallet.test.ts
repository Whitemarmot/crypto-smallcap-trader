import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import {
  generateWallet,
  createAndSaveWallet,
  encryptWallet,
  decryptWallet,
  loadEncryptedWallet,
  loadWallet,
  importWallet,
} from '../wallet';
import { encrypt, decrypt, generateSecurePassword } from '../crypto';

const TEST_WALLET_PATH = './test-wallet.json';
const TEST_PASSWORD = 'test-password-123!';

describe('Wallet Generation', () => {
  it('should generate a new wallet', () => {
    const wallet = generateWallet();
    
    expect(wallet).toBeDefined();
    expect(wallet.publicKey).toBeDefined();
    expect(wallet.secretKey).toBeInstanceOf(Uint8Array);
    expect(wallet.secretKey.length).toBe(64);
  });

  it('should generate unique wallets each time', () => {
    const wallet1 = generateWallet();
    const wallet2 = generateWallet();
    
    expect(wallet1.publicKey.toBase58()).not.toBe(wallet2.publicKey.toBase58());
  });
});

describe('Encryption/Decryption', () => {
  it('should encrypt and decrypt data correctly', () => {
    const originalData = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);
    const password = 'my-secure-password';
    
    const { encrypted, iv, salt } = encrypt(originalData, password);
    const decrypted = decrypt(encrypted, iv, salt, password);
    
    expect(decrypted).toEqual(originalData);
  });

  it('should fail decryption with wrong password', () => {
    const originalData = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);
    const { encrypted, iv, salt } = encrypt(originalData, 'correct-password');
    
    expect(() => {
      decrypt(encrypted, iv, salt, 'wrong-password');
    }).toThrow();
  });

  it('should generate secure passwords', () => {
    const password1 = generateSecurePassword();
    const password2 = generateSecurePassword();
    
    expect(password1).not.toBe(password2);
    expect(password1.length).toBeGreaterThan(20);
  });
});

describe('Wallet Encryption', () => {
  it('should encrypt and decrypt a wallet', () => {
    const wallet = generateWallet();
    const encrypted = encryptWallet(wallet, TEST_PASSWORD);
    
    expect(encrypted.publicKey).toBe(wallet.publicKey.toBase58());
    expect(encrypted.encryptedPrivateKey).toBeDefined();
    expect(encrypted.iv).toBeDefined();
    expect(encrypted.salt).toBeDefined();
    
    const decrypted = decryptWallet(encrypted, TEST_PASSWORD);
    
    expect(decrypted.publicKey).toBe(wallet.publicKey.toBase58());
    expect(decrypted.secretKey).toEqual(wallet.secretKey);
  });

  it('should fail decryption with wrong password', () => {
    const wallet = generateWallet();
    const encrypted = encryptWallet(wallet, TEST_PASSWORD);
    
    expect(() => {
      decryptWallet(encrypted, 'wrong-password');
    }).toThrow();
  });
});

describe('Wallet File Operations', () => {
  afterEach(() => {
    // Clean up test files
    if (fs.existsSync(TEST_WALLET_PATH)) {
      fs.unlinkSync(TEST_WALLET_PATH);
    }
  });

  it('should create and save a wallet to file', () => {
    const publicKey = createAndSaveWallet(TEST_PASSWORD, TEST_WALLET_PATH);
    
    expect(publicKey).toBeDefined();
    expect(publicKey.length).toBeGreaterThan(30); // Base58 public key
    expect(fs.existsSync(TEST_WALLET_PATH)).toBe(true);
    
    const fileContent = JSON.parse(fs.readFileSync(TEST_WALLET_PATH, 'utf-8'));
    expect(fileContent.publicKey).toBe(publicKey);
  });

  it('should load an encrypted wallet from file', () => {
    createAndSaveWallet(TEST_PASSWORD, TEST_WALLET_PATH);
    
    const loaded = loadEncryptedWallet(TEST_WALLET_PATH);
    
    expect(loaded.publicKey).toBeDefined();
    expect(loaded.encryptedPrivateKey).toBeDefined();
  });

  it('should load and decrypt a wallet from file', () => {
    const publicKey = createAndSaveWallet(TEST_PASSWORD, TEST_WALLET_PATH);
    
    const wallet = loadWallet(TEST_WALLET_PATH, TEST_PASSWORD);
    
    expect(wallet.publicKey).toBe(publicKey);
    expect(wallet.secretKey).toBeInstanceOf(Uint8Array);
  });

  it('should throw error for non-existent wallet file', () => {
    expect(() => {
      loadEncryptedWallet('./non-existent-wallet.json');
    }).toThrow('Wallet file not found');
  });
});

describe('Wallet Import', () => {
  afterEach(() => {
    if (fs.existsSync(TEST_WALLET_PATH)) {
      fs.unlinkSync(TEST_WALLET_PATH);
    }
  });

  it('should import a wallet from secret key', () => {
    // Generate a wallet and export its secret key
    const original = generateWallet();
    const secretKey = original.secretKey;
    
    // Import it back
    const publicKey = importWallet(secretKey, TEST_PASSWORD, TEST_WALLET_PATH);
    
    expect(publicKey).toBe(original.publicKey.toBase58());
    
    // Load and verify
    const loaded = loadWallet(TEST_WALLET_PATH, TEST_PASSWORD);
    expect(loaded.publicKey).toBe(publicKey);
  });

  it('should import a wallet from number array', () => {
    const original = generateWallet();
    const secretKeyArray = Array.from(original.secretKey);
    
    const publicKey = importWallet(secretKeyArray, TEST_PASSWORD);
    
    expect(publicKey).toBe(original.publicKey.toBase58());
  });
});
