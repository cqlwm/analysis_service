"""MACD 指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame
from dataclasses import dataclass

from indicators.base import BaseIndicator, IndicatorOutputProtocol, IndicatorSignal, SignalDirection


@dataclass
class MACDOutput:
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
    
    def summarize(self, df: DataFrame) -> IndicatorOutputProtocol:
        current = df.iloc[-1]
        macd = float(current['macd'])
        macd_signal = float(current['macd_signal'])
        macd_hist = float(current['macd_hist'])
        prev = df.iloc[-2] if len(df) >= 2 else current
        prev_hist = float(prev['macd_hist'])
        prev_close = float(prev['close'])
        close = float(current['close'])

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

        bullish_divergence = close < prev_close and macd_hist > prev_hist
        bearish_divergence = close > prev_close and macd_hist < prev_hist
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
            signal_obj={
                "direction": direction,
                "strength": None,
                "description": desc,
            },
        )
    
    def get_column_names(self) -> list[str]:
        return ['macd', 'macd_signal', 'macd_hist']
