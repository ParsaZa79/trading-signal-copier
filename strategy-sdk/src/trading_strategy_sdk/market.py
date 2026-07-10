"""Release 1 market-subscription contracts."""

from enum import StrEnum

from trading_strategy_sdk._model import ContractModel


class Symbol(StrEnum):
    """Release 1 market universe."""

    XAUUSD = "XAUUSD"
    EURUSD = "EURUSD"
    GBPUSD = "GBPUSD"
    USDJPY = "USDJPY"
    AUDUSD = "AUDUSD"
    USDCAD = "USDCAD"


class Timeframe(StrEnum):
    """Supported closed-bar intervals; Release 1 starts at M5."""

    M5 = "M5"
    M6 = "M6"
    M10 = "M10"
    M12 = "M12"
    M15 = "M15"
    M20 = "M20"
    M30 = "M30"
    H1 = "H1"
    H2 = "H2"
    H3 = "H3"
    H4 = "H4"
    H6 = "H6"
    H8 = "H8"
    H12 = "H12"
    D1 = "D1"
    W1 = "W1"
    MN1 = "MN1"

    @property
    def minutes(self) -> int:
        """Return the fixed duration used for ordering and non-monthly freshness checks."""
        return _TIMEFRAME_MINUTES[self]


_TIMEFRAME_MINUTES: dict[Timeframe, int] = {
    Timeframe.M5: 5,
    Timeframe.M6: 6,
    Timeframe.M10: 10,
    Timeframe.M12: 12,
    Timeframe.M15: 15,
    Timeframe.M20: 20,
    Timeframe.M30: 30,
    Timeframe.H1: 60,
    Timeframe.H2: 120,
    Timeframe.H3: 180,
    Timeframe.H4: 240,
    Timeframe.H6: 360,
    Timeframe.H8: 480,
    Timeframe.H12: 720,
    Timeframe.D1: 1_440,
    Timeframe.W1: 10_080,
    Timeframe.MN1: 43_200,
}


class BarSubscription(ContractModel):
    """A single symbol/timeframe closed-bar subscription."""

    symbol: Symbol
    timeframe: Timeframe

    @property
    def key(self) -> tuple[str, int]:
        """Return a stable, hashable identity for maps and ordering."""
        return (self.symbol.value, self.timeframe.minutes)
