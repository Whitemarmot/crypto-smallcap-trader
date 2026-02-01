"""
Trading Engine Bridge for Streamlit Frontend
Provides synchronous wrappers for async trading functions.
"""

import asyncio
from decimal import Decimal
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import sys
import os

# Add trading-engine to path
TRADING_ENGINE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'trading-engine')
sys.path.insert(0, TRADING_ENGINE_PATH)

from dex_aggregator import (
    DexAggregator, Network, Quote, SwapResult, TokenInfo, COMMON_TOKENS
)
from strategies import (
    DCAConfig, LimitOrderConfig, StopLossConfig,
    DCAStrategy, LimitOrderStrategy, StopLossStrategy,
    StrategyRunner, OrderSide, ExecutionResult
)


# Supported networks for UI
NETWORKS = {
    "ethereum": {"name": "Ethereum", "chain_id": 1, "icon": "🔷", "native": "ETH"},
    "base": {"name": "Base", "chain_id": 8453, "icon": "🔵", "native": "ETH"},
    "arbitrum": {"name": "Arbitrum", "chain_id": 42161, "icon": "🔶", "native": "ETH"},
    "bsc": {"name": "BSC", "chain_id": 56, "icon": "🟡", "native": "BNB"},
    "polygon": {"name": "Polygon", "chain_id": 137, "icon": "🟣", "native": "MATIC"},
    "optimism": {"name": "Optimism", "chain_id": 10, "icon": "🔴", "native": "ETH"},
}


def get_event_loop():
    """Get or create event loop for async operations"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def sync_get_quote(
    token_in: str,
    token_out: str,
    amount: float,
    network: str = "ethereum"
) -> Optional[Dict[str, Any]]:
    """
    Get a swap quote (synchronous wrapper)
    
    Args:
        token_in: Source token symbol (e.g., "ETH", "USDC")
        token_out: Destination token symbol
        amount: Amount to swap (human readable)
        network: Network name (ethereum, base, arbitrum, bsc, polygon)
    
    Returns:
        Dict with quote info or None on error
    
    Example:
        quote = sync_get_quote("ETH", "USDC", 0.1, "base")
        print(f"Price: {quote['price']}")
    """
    async def _get_quote():
        try:
            async with DexAggregator() as dex:
                net = Network.from_name(network)
                quote = await dex.get_quote(
                    token_in, token_out, Decimal(str(amount)), net
                )
                return {
                    "success": True,
                    "src_token": quote.src_token.symbol,
                    "dst_token": quote.dst_token.symbol,
                    "src_amount": float(quote.src_amount_human),
                    "dst_amount": float(quote.dst_amount_human),
                    "price": float(quote.price),
                    "gas_estimate": quote.gas_estimate,
                    "quoted_at": quote.quoted_at.isoformat(),
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    loop = get_event_loop()
    return loop.run_until_complete(_get_quote())


def sync_simulate_swap(
    token_in: str,
    token_out: str,
    amount: float,
    slippage: float = 1.0,
    network: str = "ethereum"
) -> Dict[str, Any]:
    """
    Simulate a swap (dry run only - never executes real transactions)
    
    Args:
        token_in: Source token symbol
        token_out: Destination token symbol
        amount: Amount to swap
        slippage: Max slippage percentage
        network: Network name
    
    Returns:
        Dict with simulation result
    """
    async def _simulate():
        try:
            async with DexAggregator(dry_run=True) as dex:
                net = Network.from_name(network)
                
                # Get quote first
                quote = await dex.get_quote(
                    token_in, token_out, Decimal(str(amount)), net
                )
                
                # Simulate swap (dry run)
                result = await dex.execute_swap(
                    wallet_address="0x0000000000000000000000000000000000000000",
                    private_key="0x" + "00" * 32,
                    token_in=token_in,
                    token_out=token_out,
                    amount=Decimal(str(amount)),
                    slippage=Decimal(str(slippage)),
                    network=net,
                )
                
                return {
                    "success": result.success,
                    "is_dry_run": True,
                    "src_amount": float(quote.src_amount_human),
                    "dst_amount": float(quote.dst_amount_human),
                    "price": float(quote.price),
                    "gas_estimate": quote.gas_estimate,
                    "slippage": slippage,
                    "error": result.error,
                }
        except Exception as e:
            return {"success": False, "is_dry_run": True, "error": str(e)}
    
    loop = get_event_loop()
    return loop.run_until_complete(_simulate())


def get_tokens_for_network(network: str) -> List[Dict[str, Any]]:
    """
    Get list of common tokens for a network
    
    Args:
        network: Network name
    
    Returns:
        List of token dicts with symbol, address, decimals
    """
    chain_id = NETWORKS.get(network, {}).get("chain_id", 1)
    tokens = COMMON_TOKENS.get(chain_id, {})
    
    return [
        {
            "symbol": token.symbol,
            "name": token.name,
            "address": token.address,
            "decimals": token.decimals,
            "is_native": token.is_native,
        }
        for token in tokens.values()
    ]


def create_dca_strategy(
    strategy_id: str,
    name: str,
    wallet_id: int,
    network: str,
    token_in: str,
    token_out: str,
    amount_per_buy: float,
    frequency_hours: int,
    total_budget: Optional[float] = None,
    max_executions: Optional[int] = None,
    slippage: float = 1.0,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Create a DCA strategy configuration
    
    Returns:
        Dict with strategy config for database storage
    """
    config = DCAConfig(
        id=strategy_id,
        name=name,
        wallet_id=wallet_id,
        network=network,
        token_in=token_in,
        token_out=token_out,
        amount_per_buy=Decimal(str(amount_per_buy)),
        frequency_hours=frequency_hours,
        total_budget=Decimal(str(total_budget)) if total_budget else None,
        max_executions=max_executions,
        max_slippage=Decimal(str(slippage)),
        dry_run=dry_run,
    )
    return config.to_dict()


def create_limit_order(
    strategy_id: str,
    name: str,
    wallet_id: int,
    network: str,
    side: str,  # "buy" or "sell"
    token_in: str,
    token_out: str,
    target_price: float,
    amount: float,
    slippage: float = 1.0,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Create a Limit Order strategy configuration
    
    Returns:
        Dict with strategy config for database storage
    """
    config = LimitOrderConfig(
        id=strategy_id,
        name=name,
        wallet_id=wallet_id,
        network=network,
        side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
        token_in=token_in,
        token_out=token_out,
        target_price=Decimal(str(target_price)),
        amount=Decimal(str(amount)),
        max_slippage=Decimal(str(slippage)),
        dry_run=dry_run,
    )
    return config.to_dict()


def create_stop_loss(
    strategy_id: str,
    name: str,
    wallet_id: int,
    network: str,
    token_in: str,  # Token to sell
    token_out: str,  # Token to receive
    reference_price: float,
    trigger_percent: float,
    amount: float,
    trailing: bool = False,
    slippage: float = 1.0,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Create a Stop Loss strategy configuration
    
    Returns:
        Dict with strategy config for database storage
    """
    config = StopLossConfig(
        id=strategy_id,
        name=name,
        wallet_id=wallet_id,
        network=network,
        token_in=token_in,
        token_out=token_out,
        reference_price=Decimal(str(reference_price)),
        trigger_percent=Decimal(str(trigger_percent)),
        amount=Decimal(str(amount)),
        trailing=trailing,
        max_slippage=Decimal(str(slippage)),
        dry_run=dry_run,
    )
    return config.to_dict()


def run_dca_check(config_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Check and execute a DCA strategy once
    
    Args:
        config_dict: DCA config from database
    
    Returns:
        Execution result dict or None if not executed
    """
    async def _run():
        try:
            config = DCAConfig.from_dict(config_dict)
            strategy = DCAStrategy(config)
            result = await strategy.check_and_execute()
            if result:
                return result.to_dict()
            return None
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    loop = get_event_loop()
    return loop.run_until_complete(_run())


def calculate_dca_projection(
    amount_per_buy: float,
    frequency_hours: int,
    duration_days: int,
    estimated_price: float,
) -> Dict[str, Any]:
    """
    Calculate DCA projections
    
    Returns:
        Dict with projection stats
    """
    hours_total = duration_days * 24
    num_buys = hours_total // frequency_hours
    total_invested = amount_per_buy * num_buys
    
    # Simple projection (assuming stable price)
    tokens_acquired = total_invested / estimated_price if estimated_price > 0 else 0
    
    return {
        "num_buys": num_buys,
        "total_invested": total_invested,
        "tokens_acquired": tokens_acquired,
        "avg_price": estimated_price,
        "duration_days": duration_days,
        "frequency_label": _frequency_label(frequency_hours),
    }


def _frequency_label(hours: int) -> str:
    """Convert hours to human readable label"""
    if hours == 1:
        return "Hourly"
    elif hours == 4:
        return "Every 4 hours"
    elif hours == 12:
        return "Twice daily"
    elif hours == 24:
        return "Daily"
    elif hours == 168:
        return "Weekly"
    elif hours == 720:
        return "Monthly"
    else:
        return f"Every {hours}h"


def get_price_for_stop_loss(
    token: str,
    network: str = "ethereum"
) -> Optional[float]:
    """
    Get current price for stop loss setup
    
    Args:
        token: Token symbol (e.g., "ETH")
        network: Network name
    
    Returns:
        Price in USDC or None
    """
    quote = sync_get_quote(token, "USDC", 1.0, network)
    if quote and quote.get("success"):
        return quote.get("price")
    return None


# Export all
__all__ = [
    "NETWORKS",
    "sync_get_quote",
    "sync_simulate_swap",
    "get_tokens_for_network",
    "create_dca_strategy",
    "create_limit_order",
    "create_stop_loss",
    "run_dca_check",
    "calculate_dca_projection",
    "get_price_for_stop_loss",
]
