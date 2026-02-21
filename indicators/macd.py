"""MACD 指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame

from indicators.base import BaseIndicator, IndicatorOutput, SignalDirection


class MACDIndicator(BaseIndicator):
    """MACD (Moving Average Convergence Divergence) 指数平滑异同移动平均线"""
    
    name = "macd"
    display_name = "MACD"
    fast_period = 12
    slow_period = 26
    signal_period = 9
    
    def calculate(self, df: DataFrame) -> DataFrame:
        close = df['close'].values.astype(np.float64)
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
    
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> IndicatorOutput:
        current = df.iloc[latest_idx]
        macd = float(current['macd'])
        macd_signal = float(current['macd_signal'])
        macd_hist = float(current['macd_hist'])
        
        # 判断金叉死叉
        if macd > macd_signal and macd_hist > 0:
            direction = SignalDirection.LONG
            desc = "金叉，多头信号"
        elif macd < macd_signal and macd_hist < 0:
            direction = SignalDirection.SHORT
            desc = "死叉，空头信号"
        elif macd > macd_signal:
            direction = SignalDirection.LONG
            desc = "多头排列，但需关注动能"
        else:
            direction = SignalDirection.SHORT
            desc = "空头排列，但需关注动能"
        
        return {
            "name": self.name,
            "display_name": self.display_name,
            "values": {
                "macd": round(macd, 6),
                "macd_signal": round(macd_signal, 6),
                "macd_hist": round(macd_hist, 6),
                "fast_period": self.fast_period,
                "slow_period": self.slow_period,
                "signal_period": self.signal_period,
            },
            "signal": {
                "direction": direction,
                "strength": None,
                "description": desc,
            },
            "summary": f"MACD=({macd:.4f},{macd_signal:.4f},{macd_hist:.4f})，{desc}",
        }
    
    def get_column_names(self) -> list[str]:
        return ['macd', 'macd_signal', 'macd_hist']
