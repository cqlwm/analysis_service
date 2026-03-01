"""MACD 指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame
from dataclasses import dataclass

from indicators import BaseIndicator, SignalDirection, IndicatorSummaryOutput, IndicatorSignal


@dataclass
class MACDOutput(IndicatorSummaryOutput):
    """MACD 指标输出"""
    name: str
    display_name: str
    
    macd: float
    signal_line: float
    hist: float
    fast_period: int
    slow_period: int
    signal_period: int
    cross_type: str
    zero_axis: str
    hist_momentum: str
    momentum_support: str
    divergence_warning: bool
    bullish_divergence: bool
    bearish_divergence: bool

    signal_obj: IndicatorSignal

    @property
    def signal(self) -> IndicatorSignal:
        return self.signal_obj
    
    @property
    def direction(self) -> str | None:
        return self.signal_obj["direction"]
    
    @property
    def description(self) -> str | None:
        return self.signal_obj["description"]


class MACDIndicator(BaseIndicator):
    """MACD (Moving Average Convergence Divergence) 指数平滑异同移动平均线"""
    
    name = "macd"
    display_name = "MACD"
    fast_period = 12
    slow_period = 26
    signal_period = 9
    divergence_lookback = 30
    divergence_pivot_n = 5
    
    def calculate(self, df: DataFrame) -> DataFrame:
        close = np.asarray(df['close'].values, dtype=np.float64)
        macd, signal, hist = ta.MACD(
            close,
            fastperiod=self.fast_period,
            slowperiod=self.slow_period,
            signalperiod=self.signal_period
        )
        df['macd'] = macd
        df['macd_signal'] = signal
        df['macd_hist'] = hist
        return df

    @staticmethod
    def _find_pivots(values: np.ndarray, n: int) -> tuple[list[int], list[int]]:
        peaks: list[int] = []
        troughs: list[int] = []

        if len(values) < (2 * n + 1):
            return peaks, troughs

        for i in range(n, len(values) - n):
            window = values[i - n:i + n + 1]
            if np.isnan(window).any():
                continue

            center = values[i]
            if center == np.max(window) and center > values[i - 1] and center > values[i + 1]:
                peaks.append(i)
            if center == np.min(window) and center < values[i - 1] and center < values[i + 1]:
                troughs.append(i)

        return peaks, troughs

    def _detect_divergence(self, df: DataFrame, idx: int) -> tuple[bool, bool]:
        start = max(0, idx - self.divergence_lookback)
        window_df = df.iloc[start:idx + 1]

        close_values = window_df['close'].to_numpy(dtype=np.float64)
        hist_values = window_df['macd_hist'].to_numpy(dtype=np.float64)

        n = self.divergence_pivot_n
        price_peaks, price_troughs = self._find_pivots(close_values, n)
        hist_peaks, hist_troughs = self._find_pivots(hist_values, n)

        bearish = False
        bullish = False

        if len(price_peaks) >= 2 and len(hist_peaks) >= 2:
            pp1, pp2 = price_peaks[-2], price_peaks[-1]

            def nearest_peak(target: int) -> int | None:
                candidates = [p for p in hist_peaks if abs(p - target) <= n]
                if not candidates:
                    return None
                return min(candidates, key=lambda p: abs(p - target))

            hp1 = nearest_peak(pp1)
            hp2 = nearest_peak(pp2)

            if hp1 is not None and hp2 is not None:
                if close_values[pp2] > close_values[pp1] and hist_values[hp2] < hist_values[hp1]:
                    bearish = True

        if len(price_troughs) >= 2 and len(hist_troughs) >= 2:
            pt1, pt2 = price_troughs[-2], price_troughs[-1]

            def nearest_trough(target: int) -> int | None:
                candidates = [t for t in hist_troughs if abs(t - target) <= n]
                if not candidates:
                    return None
                return min(candidates, key=lambda t: abs(t - target))

            ht1 = nearest_trough(pt1)
            ht2 = nearest_trough(pt2)

            if ht1 is not None and ht2 is not None:
                if close_values[pt2] < close_values[pt1] and hist_values[ht2] > hist_values[ht1]:
                    bullish = True

        return bullish, bearish
    
    def summarize(self, df: DataFrame) -> IndicatorSummaryOutput:
        current = df.iloc[-1]
        macd = float(current['macd'])
        macd_signal = float(current['macd_signal'])
        macd_hist = float(current['macd_hist'])
        prev = df.iloc[-2] if len(df) >= 2 else current
        prev_hist = float(prev['macd_hist'])

        hist_abs_now = abs(macd_hist)
        hist_abs_prev = abs(prev_hist)

        if hist_abs_now > hist_abs_prev + 1e-9:
            hist_momentum = "expanding"
        elif hist_abs_now + 1e-9 < hist_abs_prev:
            hist_momentum = "shrinking"
        else:
            hist_momentum = "flat"

        if macd > 0 and macd_signal > 0:
            zero_axis = "above"
        elif macd < 0 and macd_signal < 0:
            zero_axis = "below"
        else:
            zero_axis = "crossing"

        bullish_divergence, bearish_divergence = self._detect_divergence(df.reset_index(drop=True), len(df) - 1)
        divergence_warning = bool(bullish_divergence or bearish_divergence)
        
        if macd > macd_signal and macd_hist > 0:
            direction = SignalDirection.LONG
            cross_type = "golden_cross"
            desc = "金叉，多头信号"
        elif macd < macd_signal and macd_hist < 0:
            direction = SignalDirection.SHORT
            cross_type = "death_cross"
            desc = "死叉，空头信号"
        elif macd > macd_signal:
            direction = SignalDirection.LONG
            cross_type = "bullish_alignment"
            desc = "多头排列，但需关注动能"
        else:
            direction = SignalDirection.SHORT
            cross_type = "bearish_alignment"
            desc = "空头排列，但需关注动能"

        if divergence_warning:
            momentum_support = "warning"
        elif (direction == SignalDirection.LONG and macd_hist > 0 and hist_momentum != "shrinking") or (
            direction == SignalDirection.SHORT and macd_hist < 0 and hist_momentum != "shrinking"
        ):
            momentum_support = "support"
        else:
            momentum_support = "neutral"
        
        return MACDOutput(
            name=self.name,
            display_name=self.display_name,
            macd=round(macd, 6),
            signal_line=round(macd_signal, 6),
            hist=round(macd_hist, 6),
            fast_period=self.fast_period,
            slow_period=self.slow_period,
            signal_period=self.signal_period,
            cross_type=cross_type,
            zero_axis=zero_axis,
            hist_momentum=hist_momentum,
            momentum_support=momentum_support,
            divergence_warning=divergence_warning,
            bullish_divergence=bullish_divergence,
            bearish_divergence=bearish_divergence,
            signal_obj={
                "direction": direction,
                "strength": None,
                "description": desc,
            },
        )
    
    def get_column_names(self) -> list[str]:
        return ['macd', 'macd_signal', 'macd_hist']
