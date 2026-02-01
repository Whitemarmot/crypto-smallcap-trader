"""
Filters for copy-trading decisions.
Determines whether a detected trade should be copied.
"""
import logging
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from .models import DetectedTrade, CopyConfig, TradeType

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of applying filters to a trade."""
    should_copy: bool
    passed_filters: List[str]
    failed_filters: List[str]
    adjusted_size: float  # Adjusted size multiplier based on confidence
    delay_seconds: float  # Recommended delay before copying
    reason: str  # Human-readable summary


class TradeFilter:
    """Applies filters to determine if a trade should be copied."""
    
    def __init__(self, config: CopyConfig):
        self.config = config
        self._recent_copies: List[Tuple[str, datetime]] = []  # (token, time)
    
    def apply_filters(self, trade: DetectedTrade) -> FilterResult:
        """
        Apply all filters to a detected trade.
        Returns FilterResult with decision and details.
        """
        passed = []
        failed = []
        
        # Check if copy-trading is enabled
        if not self.config.enabled:
            return FilterResult(
                should_copy=False,
                passed_filters=[],
                failed_filters=["global_disabled"],
                adjusted_size=0.0,
                delay_seconds=0.0,
                reason="Copy-trading is globally disabled"
            )
        
        # 1. Check trade age
        if self._check_trade_age(trade):
            passed.append("trade_age")
        else:
            failed.append("trade_age")
        
        # 2. Check minimum trade size
        if self._check_min_size(trade):
            passed.append("min_size")
        else:
            failed.append("min_size")
        
        # 3. Check wallet weight
        if self._check_wallet_weight(trade):
            passed.append("wallet_weight")
        else:
            failed.append("wallet_weight")
        
        # 4. Check confidence score
        if self._check_confidence(trade):
            passed.append("confidence")
        else:
            failed.append("confidence")
        
        # 5. Check price impact
        if self._check_price_impact(trade):
            passed.append("price_impact")
        else:
            failed.append("price_impact")
        
        # 6. Check token whitelist/blacklist
        token_result = self._check_token_filters(trade)
        if token_result:
            passed.append("token_filter")
        else:
            failed.append("token_filter")
        
        # 7. Check chain allowed
        if self._check_chain(trade):
            passed.append("chain")
        else:
            failed.append("chain")
        
        # 8. Check DEX allowed
        if self._check_dex(trade):
            passed.append("dex")
        else:
            failed.append("dex")
        
        # 9. Check anti-spam (don't copy same token too frequently)
        if self._check_anti_spam(trade):
            passed.append("anti_spam")
        else:
            failed.append("anti_spam")
        
        # Calculate adjusted size based on confidence
        adjusted_size = self._calculate_adjusted_size(trade)
        
        # Calculate delay
        delay = self._calculate_delay(trade)
        
        should_copy = len(failed) == 0
        
        if should_copy:
            reason = f"All {len(passed)} filters passed"
        else:
            reason = f"Failed filters: {', '.join(failed)}"
        
        return FilterResult(
            should_copy=should_copy,
            passed_filters=passed,
            failed_filters=failed,
            adjusted_size=adjusted_size,
            delay_seconds=delay,
            reason=reason
        )
    
    def _check_trade_age(self, trade: DetectedTrade) -> bool:
        """Check if trade is recent enough to copy."""
        age = (datetime.utcnow() - trade.timestamp).total_seconds()
        max_age = self.config.max_copy_age_seconds
        
        if age > max_age:
            logger.debug(f"Trade too old: {age:.1f}s > {max_age}s")
            return False
        return True
    
    def _check_min_size(self, trade: DetectedTrade) -> bool:
        """Check if trade meets minimum size requirement."""
        if trade.amount_usd < self.config.min_amount_usd:
            logger.debug(f"Trade too small: ${trade.amount_usd:.2f} < ${self.config.min_amount_usd}")
            return False
        return True
    
    def _check_wallet_weight(self, trade: DetectedTrade) -> bool:
        """Check if wallet weight meets threshold."""
        if trade.wallet_weight < self.config.min_wallet_weight:
            logger.debug(f"Wallet weight too low: {trade.wallet_weight} < {self.config.min_wallet_weight}")
            return False
        return True
    
    def _check_confidence(self, trade: DetectedTrade) -> bool:
        """Check if trade confidence score meets threshold."""
        if trade.confidence_score < self.config.min_confidence_score:
            logger.debug(f"Confidence too low: {trade.confidence_score} < {self.config.min_confidence_score}")
            return False
        return True
    
    def _check_price_impact(self, trade: DetectedTrade) -> bool:
        """Check if price impact is acceptable."""
        if trade.price_impact > self.config.max_price_impact:
            logger.debug(f"Price impact too high: {trade.price_impact}% > {self.config.max_price_impact}%")
            return False
        return True
    
    def _check_token_filters(self, trade: DetectedTrade) -> bool:
        """Check token whitelist and blacklist."""
        # Get the token being bought
        if trade.trade_type == TradeType.BUY:
            target_token = trade.token_out.lower()
        else:
            target_token = trade.token_in.lower()
        
        # Check blacklist first
        if self.config.token_blacklist:
            blacklist_lower = [t.lower() for t in self.config.token_blacklist]
            if target_token in blacklist_lower:
                logger.debug(f"Token {target_token} is blacklisted")
                return False
        
        # Check whitelist (if empty, all tokens allowed)
        if self.config.token_whitelist:
            whitelist_lower = [t.lower() for t in self.config.token_whitelist]
            if target_token not in whitelist_lower:
                logger.debug(f"Token {target_token} not in whitelist")
                return False
        
        return True
    
    def _check_chain(self, trade: DetectedTrade) -> bool:
        """Check if chain is allowed."""
        if trade.chain.lower() not in [c.lower() for c in self.config.allowed_chains]:
            logger.debug(f"Chain {trade.chain} not allowed")
            return False
        return True
    
    def _check_dex(self, trade: DetectedTrade) -> bool:
        """Check if DEX is allowed."""
        if trade.dex.lower() not in [d.lower() for d in self.config.allowed_dexes]:
            logger.debug(f"DEX {trade.dex} not allowed")
            return False
        return True
    
    def _check_anti_spam(self, trade: DetectedTrade) -> bool:
        """
        Prevent copying the same token too frequently.
        Avoids being front-run or manipulated.
        """
        target_token = trade.token_out if trade.trade_type == TradeType.BUY else trade.token_in
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)
        
        # Clean old entries
        self._recent_copies = [
            (token, time) for token, time in self._recent_copies 
            if time > cutoff_time
        ]
        
        # Check if we recently copied this token
        recent_same_token = sum(1 for token, _ in self._recent_copies if token.lower() == target_token.lower())
        
        if recent_same_token >= 2:  # Max 2 copies of same token in 5 min
            logger.debug(f"Anti-spam: Already copied {target_token} {recent_same_token} times recently")
            return False
        
        return True
    
    def record_copy(self, trade: DetectedTrade):
        """Record a copy for anti-spam tracking."""
        target_token = trade.token_out if trade.trade_type == TradeType.BUY else trade.token_in
        self._recent_copies.append((target_token, datetime.utcnow()))
    
    def _calculate_adjusted_size(self, trade: DetectedTrade) -> float:
        """
        Calculate adjusted size multiplier based on trade characteristics.
        Higher confidence/weight = larger size.
        """
        base_size = self.config.default_size_multiplier
        
        # Adjust based on confidence (0.7 - 1.0 -> 0.7x - 1.0x)
        confidence_factor = trade.confidence_score
        
        # Adjust based on wallet weight
        weight_factor = trade.wallet_weight
        
        # Adjust based on price impact (lower is better)
        impact_factor = max(0.5, 1.0 - (trade.price_impact / 10.0))
        
        adjusted = base_size * confidence_factor * weight_factor * impact_factor
        
        # Clamp to reasonable range
        adjusted = max(0.01, min(1.0, adjusted))
        
        return adjusted
    
    def _calculate_delay(self, trade: DetectedTrade) -> float:
        """
        Calculate delay before copying to avoid front-running.
        Uses random delay within configured range, adjusted by factors.
        """
        import random
        
        min_delay = self.config.min_delay_seconds
        max_delay = self.config.max_delay_seconds
        
        # Base random delay
        delay = random.uniform(min_delay, max_delay)
        
        # Adjust based on trade size (larger trades = longer delay)
        if trade.amount_usd > 50000:
            delay *= 1.5
        elif trade.amount_usd > 10000:
            delay *= 1.2
        
        # Adjust based on confidence (higher confidence = shorter delay)
        delay *= (2.0 - trade.confidence_score)
        
        # Add jitter to prevent pattern detection
        jitter = random.uniform(-2.0, 2.0)
        delay += jitter
        
        return max(min_delay, delay)


class AdvancedFilters:
    """Additional advanced filters for sophisticated copy-trading."""
    
    @staticmethod
    def check_wallet_history(wallet_address: str, min_win_rate: float = 0.5) -> bool:
        """
        Check wallet's historical performance.
        Requires historical data to be available.
        """
        # TODO: Implement with historical data
        return True
    
    @staticmethod
    def check_market_conditions(token_address: str) -> Tuple[bool, str]:
        """
        Check current market conditions for the token.
        - Liquidity depth
        - Recent volatility
        - Trading volume
        """
        # TODO: Implement with market data APIs
        return True, "Market conditions acceptable"
    
    @staticmethod
    def check_token_safety(token_address: str, chain: str) -> Tuple[bool, str]:
        """
        Check if token is safe to trade.
        - Honeypot detection
        - Contract verification
        - Ownership renounced
        - Liquidity locked
        """
        # TODO: Implement with token safety APIs (honeypot.is, tokensniffer, etc.)
        return True, "Token appears safe"
    
    @staticmethod
    def check_correlated_trades(trade: DetectedTrade, recent_trades: List[DetectedTrade]) -> bool:
        """
        Check if multiple tracked wallets are making the same trade.
        Higher correlation = higher confidence in the trade.
        """
        same_token_trades = [
            t for t in recent_trades 
            if t.token_out.lower() == trade.token_out.lower()
            and t.trade_type == trade.trade_type
            and t.wallet_address.lower() != trade.wallet_address.lower()
            and (trade.timestamp - t.timestamp).total_seconds() < 300  # Within 5 min
        ]
        
        # If multiple whales buying same token, it's a stronger signal
        return len(same_token_trades) >= 1
