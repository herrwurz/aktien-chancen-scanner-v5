from dataclasses import dataclass
from decimal import Decimal

from scanner.domain import Candle


@dataclass(frozen=True)
class Decision:
    is_signal: bool
    reason: str
    baseline_volume: Decimal | None = None
    ratio: Decimal | None = None


class VolumeDetector:
    version = 'volume-v1'

    def __init__(self, lookback=20, threshold=Decimal('3'), min_quote_volume=Decimal('100000')):
        if not 1 <= lookback <= 999 or not threshold.is_finite() or threshold <= 1:
            raise ValueError('Invalid detector parameters')
        if not min_quote_volume.is_finite() or min_quote_volume < 0:
            raise ValueError('Invalid minimum quote volume')
        self.lookback = lookback
        self.threshold = threshold
        self.min_quote_volume = min_quote_volume

    @property
    def config_key(self):
        return f'{self.version}:{self.lookback}:{self.threshold}:{self.min_quote_volume}'

    def evaluate(self, history: list[Candle], target: Candle) -> Decision:
        previous = sorted(
            (c for c in history if c.market == target.market and c.close_time <= target.open_time),
            key=lambda c: c.open_time,
        )[-self.lookback:]
        if len(previous) < self.lookback:
            return Decision(False, 'insufficient_history')
        sequence = [*previous, target]
        if any(a.close_time != b.open_time for a, b in zip(sequence, sequence[1:])):
            return Decision(False, 'history_gap')
        baseline = sum((c.volume for c in previous), Decimal(0)) / self.lookback
        if baseline == 0:
            return Decision(False, 'zero_baseline', baseline)
        ratio = target.volume / baseline
        if target.quote_volume < self.min_quote_volume:
            return Decision(False, 'low_quote_volume', baseline, ratio)
        if ratio < self.threshold:
            return Decision(False, 'normal_volume', baseline, ratio)
        return Decision(True, 'volume_spike', baseline, ratio)
