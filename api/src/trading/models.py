"""Broker-neutral order types used by the MT5 execution adapter."""

from dataclasses import dataclass, field
from enum import Enum


class OrderType(Enum):
    BUY = "buy"
    SELL = "sell"
    BUY_LIMIT = "buy_limit"
    SELL_LIMIT = "sell_limit"
    BUY_STOP = "buy_stop"
    SELL_STOP = "sell_stop"


class MessageType(Enum):
    """Lifecycle classification retained for executor compatibility."""

    NEW_SIGNAL_COMPLETE = "new_signal_complete"


class TradeRole(Enum):
    SCALP = "scalp"
    RUNNER = "runner"
    SINGLE = "single"


@dataclass
class TradeSignal:
    symbol: str
    order_type: OrderType
    entry_price: float | None
    stop_loss: float | None
    take_profits: list[float] = field(default_factory=list)
    lot_size: float | None = None
    comment: str = ""
    confidence: float = 0.5
    message_type: MessageType = MessageType.NEW_SIGNAL_COMPLETE
    is_complete: bool = True


@dataclass
class TradeConfig:
    """One broker order derived from a source trade."""

    role: TradeRole
    tp: float | None
    sl: float | None = None
    lot_size: float | None = None
    lot_multiplier: float = 1.0
