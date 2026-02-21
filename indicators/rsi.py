"""RSI 指标实现"""
import talib as ta
import numpy as np
from pandas import DataFrame

from indicators.base import BaseIndicator, IndicatorOutput, SignalDirection


class RSIIndicator(BaseIndicator):
    """RSI (Relative Strength Index) 相对强弱指标"""
    
    name = "rsi"
    display_name = "RSI"
    period = 14
    overbought = 70
    oversold = 30
    
    def calculate(self, df: DataFrame) -> DataFrame:
        close = np.asarray(df['close'].values, dtype=np.float64)
        df['rsi'] = ta.RSI(close, timeperiod=self.period)
        return df
    
    def summarize(self, df: DataFrame, latest_idx: int = -1) -> IndicatorOutput:
        current = df.iloc[latest_idx]
        rsi = float(current['rsi'])
        
        # 判断信号
        if rsi > self.overbought:
            direction = SignalDirection.SHORT
            desc = f"超买区域({rsi:.2f})，注意回调风险"
        elif rsi < self.oversold:
            direction = SignalDirection.LONG
            desc = f"超卖区域({rsi:.2f})，注意反弹机会"
        else:
            direction = SignalDirection.NEUTRAL
            desc = f"中性区域({rsi:.2f})"
        
        return {
            "name": self.name,
            "display_name": self.display_name,
            "values": {
                "rsi": round(rsi, 2),
                "period": self.period,
                "overbought": self.overbought,
                "oversold": self.oversold,
            },
            "signal": {
                "direction": direction,
                "strength": None,
                "description": desc,
            },
        }
    
    def get_column_names(self) -> list[str]:
        return ['rsi']
