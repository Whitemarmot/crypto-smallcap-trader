#!/usr/bin/env python3
"""
💼 Wallet Manager CLI
Manage wallets: list, enable, disable, create
"""

import json
import os
import sys
import argparse
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
WALLETS_DIR = os.path.join(DATA_DIR, 'wallets')
CONFIG_PATH = os.path.join(WALLETS_DIR, 'config.json')

def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except:
        return {'wallets': [], 'active_wallet': None}

def save_config(config):
    os.makedirs(WALLETS_DIR, exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

def list_wallets():
    config = load_config()
    print("\n💼 WALLETS\n")
    for w in config.get('wallets', []):
        status = "✅" if w.get('enabled', True) else "❌"
        active = "⭐" if w.get('id') == config.get('active_wallet') else "  "
        print(f"{active} {status} {w['name']} ({w['id']}) - {w.get('type', 'paper')} - max {w.get('max_positions', 10)} positions")
    print()

def enable_wallet(wallet_id):
    config = load_config()
    for w in config.get('wallets', []):
        if w['id'] == wallet_id:
            w['enabled'] = True
            save_config(config)
            print(f"✅ Wallet '{wallet_id}' enabled")
            return
    print(f"❌ Wallet '{wallet_id}' not found")

def disable_wallet(wallet_id):
    config = load_config()
    for w in config.get('wallets', []):
        if w['id'] == wallet_id:
            w['enabled'] = False
            save_config(config)
            print(f"❌ Wallet '{wallet_id}' disabled")
            return
    print(f"❌ Wallet '{wallet_id}' not found")

def create_wallet(wallet_id, name, wallet_type='paper', initial_capital=10000, max_positions=10):
    config = load_config()
    
    # Check if exists
    for w in config.get('wallets', []):
        if w['id'] == wallet_id:
            print(f"❌ Wallet '{wallet_id}' already exists")
            return
    
    # Create wallet config
    new_wallet = {
        'id': wallet_id,
        'name': name,
        'type': wallet_type,
        'enabled': True,
        'initial_capital': initial_capital,
        'max_positions': max_positions,
        'created_at': datetime.now().isoformat()
    }
    config['wallets'].append(new_wallet)
    save_config(config)
    
    # Create wallet data file
    wallet_data = {
        'portfolio': {'USDC': initial_capital},
        'positions': {},
        'history': [],
        'settings': {
            'initial_capital': initial_capital,
            'max_positions': max_positions
        }
    }
    wallet_path = os.path.join(WALLETS_DIR, f"{wallet_id}.json")
    with open(wallet_path, 'w') as f:
        json.dump(wallet_data, f, indent=2)
    
    print(f"✅ Wallet '{name}' ({wallet_id}) created with ${initial_capital}")

def set_active(wallet_id):
    config = load_config()
    for w in config.get('wallets', []):
        if w['id'] == wallet_id:
            config['active_wallet'] = wallet_id
            save_config(config)
            print(f"⭐ Wallet '{wallet_id}' is now active")
            return
    print(f"❌ Wallet '{wallet_id}' not found")

def main():
    parser = argparse.ArgumentParser(description='Wallet Manager')
    parser.add_argument('action', choices=['list', 'enable', 'disable', 'create', 'active'], 
                       help='Action to perform')
    parser.add_argument('--id', type=str, help='Wallet ID')
    parser.add_argument('--name', type=str, help='Wallet name (for create)')
    parser.add_argument('--type', type=str, default='paper', help='Wallet type (paper/live)')
    parser.add_argument('--capital', type=float, default=10000, help='Initial capital')
    parser.add_argument('--max-positions', type=int, default=10, help='Max positions')
    
    args = parser.parse_args()
    
    if args.action == 'list':
        list_wallets()
    elif args.action == 'enable':
        if not args.id:
            print("❌ --id required")
            return
        enable_wallet(args.id)
    elif args.action == 'disable':
        if not args.id:
            print("❌ --id required")
            return
        disable_wallet(args.id)
    elif args.action == 'create':
        if not args.id or not args.name:
            print("❌ --id and --name required")
            return
        create_wallet(args.id, args.name, args.type, args.capital, args.max_positions)
    elif args.action == 'active':
        if not args.id:
            print("❌ --id required")
            return
        set_active(args.id)

if __name__ == '__main__':
    main()
