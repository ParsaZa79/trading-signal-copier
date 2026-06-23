"""Background broadcaster for real-time updates."""

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .manager import ConnectionManager


async def start_broadcaster(
    get_executor: Callable[[str], Any],
    manager: ConnectionManager,
    interval: float = 1.0,
) -> None:
    """Background task that broadcasts position and account updates.

    Args:
        get_executor: Resolver for the subscribed account's MT5 executor.
        manager: The WebSocket connection manager.
        interval: Broadcast interval in seconds.
    """
    print(f"Starting WebSocket broadcaster with {interval}s interval")

    while True:
        try:
            # Skip if no connections
            if manager.connection_count == 0:
                await asyncio.sleep(interval)
                continue

            for account_id in manager.account_ids:
                executor = get_executor(account_id)
                message = await _build_update_message(executor, account_id)
                await manager.broadcast(account_id, message)

        except asyncio.CancelledError:
            print("Broadcaster task cancelled")
            raise
        except Exception as e:
            print(f"Broadcaster error: {e}")

        await asyncio.sleep(interval)


async def _build_update_message(executor: Any, account_id: str) -> dict:
    """Build the update message with positions and account info.

    Args:
        executor: The MT5 executor instance.

    Returns:
        dict: The update message.
    """
    positions_data = []
    account_data = None

    try:
        if executor._mt5:
            # Get positions
            positions = executor._mt5.positions_get()
            if positions:
                positions_data = [
                    {
                        "ticket": pos.ticket,
                        "symbol": pos.symbol,
                        "type": "buy" if pos.type == 0 else "sell",
                        "volume": pos.volume,
                        "price_open": pos.price_open,
                        "price_current": getattr(pos, "price_current", None),
                        "sl": pos.sl,
                        "tp": pos.tp,
                        "profit": pos.profit,
                        "swap": getattr(pos, "swap", 0.0),
                        "time": pos.time if hasattr(pos, "time") else None,
                    }
                    for pos in positions
                ]

            # Get account info
            account = executor._mt5.account_info()
            if account:
                account_data = {
                    "balance": account.balance,
                    "equity": account.equity,
                    "margin": account.margin,
                    "free_margin": account.margin_free,
                    "profit": account.profit,
                }

    except Exception as e:
        print(f"Error building update message: {e}")

    return {
        "type": "update",
        "account_id": account_id,
        "timestamp": datetime.now().isoformat(),
        "positions": positions_data,
        "account": account_data,
    }
