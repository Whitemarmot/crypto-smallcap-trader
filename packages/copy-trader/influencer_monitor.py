"""
Influencer Monitor - Track and manage wallets of known crypto influencers.
"""
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from .models import TrackedWallet, WalletType

logger = logging.getLogger(__name__)


# Known crypto influencer wallets (examples - should be verified)
# Format: address -> (name, platform, weight)
KNOWN_INFLUENCERS = {
    # Major traders/influencers (placeholder addresses - replace with real ones)
    "0x0000000000000000000000000000000000000001": {
        "name": "Cobie",
        "platform": "twitter",
        "handle": "@coaboromonkey", 
        "weight": 0.9,
        "notes": "Highly respected trader, long-term plays"
    },
    "0x0000000000000000000000000000000000000002": {
        "name": "Hsaka",
        "platform": "twitter",
        "handle": "@HsakaTrades",
        "weight": 0.85,
        "notes": "Momentum trader, quick entries/exits"
    },
    "0x0000000000000000000000000000000000000003": {
        "name": "Ansem",
        "platform": "twitter", 
        "handle": "@blaborchain",
        "weight": 0.8,
        "notes": "Solana ecosystem, memecoins"
    },
    "0x0000000000000000000000000000000000000004": {
        "name": "GCR",
        "platform": "twitter",
        "handle": "@GCRClassic",
        "weight": 0.95,
        "notes": "Macro trader, contrarian"
    },
    "0x0000000000000000000000000000000000000005": {
        "name": "Loomdart",
        "platform": "twitter",
        "handle": "@loomdart",
        "weight": 0.75,
        "notes": "DeFi focus"
    },
}

# Smart money / VC wallets
SMART_MONEY_WALLETS = {
    "0xa16e02e87b7454126e5e10d957a927a7f5b5d2be": {
        "name": "Paradigm",
        "type": "vc",
        "weight": 0.9,
        "notes": "Top crypto VC, early-stage investments"
    },
    "0x9b0615e4d3c0f9d92a0c71e1c9f8e1d9c0a8b7c6": {
        "name": "a16z",
        "type": "vc",
        "weight": 0.85,
        "notes": "Andreessen Horowitz crypto fund"
    },
    "0x1a2b3c4d5e6f7890abcdef1234567890abcdef12": {
        "name": "Alameda Research",
        "type": "market_maker",
        "weight": 0.0,  # Disabled - defunct
        "notes": "DEFUNCT - Do not follow"
    },
}


class InfluencerMonitor:
    """
    Manages a list of influencer wallets to track.
    Supports loading/saving from file and categorization.
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path("./data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.influencers: Dict[str, TrackedWallet] = {}
        self.smart_money: Dict[str, TrackedWallet] = {}
        self.custom_wallets: Dict[str, TrackedWallet] = {}
        
        self._influencers_file = self.data_dir / "influencers.json"
        self._custom_wallets_file = self.data_dir / "custom_wallets.json"
    
    def load_known_influencers(self):
        """Load the built-in list of known influencers."""
        for address, info in KNOWN_INFLUENCERS.items():
            wallet = TrackedWallet(
                address=address,
                name=info["name"],
                wallet_type=WalletType.INFLUENCER,
                weight=info["weight"],
                notes=info.get("notes", ""),
                tags=[info.get("platform", ""), info.get("handle", "")]
            )
            self.influencers[address.lower()] = wallet
            logger.debug(f"Loaded influencer: {info['name']}")
        
        for address, info in SMART_MONEY_WALLETS.items():
            wallet = TrackedWallet(
                address=address,
                name=info["name"],
                wallet_type=WalletType.SMART_MONEY,
                weight=info["weight"],
                notes=info.get("notes", ""),
                tags=[info.get("type", "")]
            )
            self.smart_money[address.lower()] = wallet
            logger.debug(f"Loaded smart money: {info['name']}")
        
        logger.info(f"Loaded {len(self.influencers)} influencers and {len(self.smart_money)} smart money wallets")
    
    def load_from_file(self):
        """Load wallets from saved files."""
        # Load influencers
        if self._influencers_file.exists():
            try:
                with open(self._influencers_file) as f:
                    data = json.load(f)
                    for wallet_data in data:
                        wallet = TrackedWallet.from_dict(wallet_data)
                        self.influencers[wallet.address] = wallet
                logger.info(f"Loaded {len(self.influencers)} influencers from file")
            except Exception as e:
                logger.error(f"Error loading influencers file: {e}")
        
        # Load custom wallets
        if self._custom_wallets_file.exists():
            try:
                with open(self._custom_wallets_file) as f:
                    data = json.load(f)
                    for wallet_data in data:
                        wallet = TrackedWallet.from_dict(wallet_data)
                        self.custom_wallets[wallet.address] = wallet
                logger.info(f"Loaded {len(self.custom_wallets)} custom wallets from file")
            except Exception as e:
                logger.error(f"Error loading custom wallets file: {e}")
    
    def save_to_file(self):
        """Save wallets to files."""
        # Save influencers
        try:
            data = [w.to_dict() for w in self.influencers.values()]
            with open(self._influencers_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving influencers: {e}")
        
        # Save custom wallets
        try:
            data = [w.to_dict() for w in self.custom_wallets.values()]
            with open(self._custom_wallets_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving custom wallets: {e}")
    
    def add_influencer(
        self,
        address: str,
        name: str,
        weight: float = 0.7,
        platform: str = "",
        handle: str = "",
        notes: str = ""
    ) -> TrackedWallet:
        """Add a new influencer to track."""
        wallet = TrackedWallet(
            address=address,
            name=name,
            wallet_type=WalletType.INFLUENCER,
            weight=weight,
            notes=notes,
            tags=[platform, handle] if platform or handle else []
        )
        self.influencers[address.lower()] = wallet
        self.save_to_file()
        logger.info(f"Added influencer: {name} ({address[:10]}...)")
        return wallet
    
    def add_custom_wallet(
        self,
        address: str,
        name: str,
        weight: float = 0.5,
        notes: str = "",
        tags: Optional[List[str]] = None
    ) -> TrackedWallet:
        """Add a custom wallet to track."""
        wallet = TrackedWallet(
            address=address,
            name=name,
            wallet_type=WalletType.CUSTOM,
            weight=weight,
            notes=notes,
            tags=tags or []
        )
        self.custom_wallets[address.lower()] = wallet
        self.save_to_file()
        logger.info(f"Added custom wallet: {name} ({address[:10]}...)")
        return wallet
    
    def remove_wallet(self, address: str) -> bool:
        """Remove a wallet from all lists."""
        address = address.lower()
        removed = False
        
        if address in self.influencers:
            del self.influencers[address]
            removed = True
        if address in self.smart_money:
            del self.smart_money[address]
            removed = True
        if address in self.custom_wallets:
            del self.custom_wallets[address]
            removed = True
        
        if removed:
            self.save_to_file()
            logger.info(f"Removed wallet: {address[:10]}...")
        
        return removed
    
    def set_weight(self, address: str, weight: float) -> bool:
        """Update the weight of a tracked wallet."""
        address = address.lower()
        weight = max(0.0, min(1.0, weight))  # Clamp to 0-1
        
        for wallet_dict in [self.influencers, self.smart_money, self.custom_wallets]:
            if address in wallet_dict:
                wallet_dict[address].weight = weight
                self.save_to_file()
                logger.info(f"Updated weight for {address[:10]}... to {weight}")
                return True
        
        return False
    
    def enable_wallet(self, address: str, enabled: bool = True) -> bool:
        """Enable or disable a wallet."""
        address = address.lower()
        
        for wallet_dict in [self.influencers, self.smart_money, self.custom_wallets]:
            if address in wallet_dict:
                wallet_dict[address].enabled = enabled
                self.save_to_file()
                logger.info(f"{'Enabled' if enabled else 'Disabled'} wallet: {address[:10]}...")
                return True
        
        return False
    
    def get_all_wallets(self, enabled_only: bool = True) -> List[TrackedWallet]:
        """Get all tracked wallets."""
        all_wallets = []
        
        for wallet_dict in [self.influencers, self.smart_money, self.custom_wallets]:
            for wallet in wallet_dict.values():
                if not enabled_only or wallet.enabled:
                    all_wallets.append(wallet)
        
        return all_wallets
    
    def get_wallet(self, address: str) -> Optional[TrackedWallet]:
        """Get a specific wallet by address."""
        address = address.lower()
        
        for wallet_dict in [self.influencers, self.smart_money, self.custom_wallets]:
            if address in wallet_dict:
                return wallet_dict[address]
        
        return None
    
    def get_by_weight(self, min_weight: float = 0.0) -> List[TrackedWallet]:
        """Get wallets filtered by minimum weight."""
        return [w for w in self.get_all_wallets() if w.weight >= min_weight]
    
    def get_by_type(self, wallet_type: WalletType) -> List[TrackedWallet]:
        """Get wallets of a specific type."""
        return [w for w in self.get_all_wallets() if w.wallet_type == wallet_type]
    
    def get_by_tag(self, tag: str) -> List[TrackedWallet]:
        """Get wallets with a specific tag."""
        tag = tag.lower()
        return [w for w in self.get_all_wallets() if tag in [t.lower() for t in w.tags]]
    
    def update_stats(self, address: str, profitable: bool):
        """Update trading stats for a wallet."""
        wallet = self.get_wallet(address)
        if wallet:
            wallet.total_trades_detected += 1
            if profitable:
                wallet.profitable_trades += 1
            wallet.win_rate = wallet.profitable_trades / wallet.total_trades_detected
            self.save_to_file()
    
    def get_top_performers(self, limit: int = 10) -> List[TrackedWallet]:
        """Get top performing wallets by win rate."""
        wallets = [w for w in self.get_all_wallets() if w.total_trades_detected >= 5]
        wallets.sort(key=lambda w: w.win_rate, reverse=True)
        return wallets[:limit]
    
    def export_to_json(self) -> str:
        """Export all wallets to JSON string."""
        data = {
            "influencers": [w.to_dict() for w in self.influencers.values()],
            "smart_money": [w.to_dict() for w in self.smart_money.values()],
            "custom": [w.to_dict() for w in self.custom_wallets.values()]
        }
        return json.dumps(data, indent=2)
    
    def import_from_json(self, json_str: str):
        """Import wallets from JSON string."""
        data = json.loads(json_str)
        
        for wallet_data in data.get("influencers", []):
            wallet = TrackedWallet.from_dict(wallet_data)
            self.influencers[wallet.address] = wallet
        
        for wallet_data in data.get("smart_money", []):
            wallet = TrackedWallet.from_dict(wallet_data)
            self.smart_money[wallet.address] = wallet
        
        for wallet_data in data.get("custom", []):
            wallet = TrackedWallet.from_dict(wallet_data)
            self.custom_wallets[wallet.address] = wallet
        
        self.save_to_file()
        logger.info("Imported wallets from JSON")
    
    def summary(self) -> Dict[str, Any]:
        """Get a summary of tracked wallets."""
        all_wallets = self.get_all_wallets(enabled_only=False)
        enabled = [w for w in all_wallets if w.enabled]
        
        return {
            "total_wallets": len(all_wallets),
            "enabled_wallets": len(enabled),
            "influencers": len(self.influencers),
            "smart_money": len(self.smart_money),
            "custom": len(self.custom_wallets),
            "avg_weight": sum(w.weight for w in enabled) / len(enabled) if enabled else 0,
            "top_performers": [
                {"name": w.name, "win_rate": w.win_rate}
                for w in self.get_top_performers(5)
            ]
        }
